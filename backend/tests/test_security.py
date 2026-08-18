"""Security regression tests: authz boundaries, blob ids, SSRF, CORS, secrets."""
import io
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import config, database

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "tmp")
    config.ensure_dirs()

    test_db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(config, "DATABASE_URL", test_db_url)
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(
        database, "SessionLocal", sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    )
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c


def make_wav(seconds: float = 0.2, sample_rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x10" * int(seconds * sample_rate))
    return buf.getvalue()


def _register(client, username: str) -> str:
    r = client.post("/api/auth/register", json={"username": username, "password": "secret1"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _session_with_version(client, token: str) -> tuple[int, int]:
    h = _auth(token)
    sid = client.post("/api/sessions", json={"name": "Mix"}, headers=h).json()["id"]
    vid = client.post(
        f"/api/sessions/{sid}/versions",
        headers=h,
        data={"message": "v1"},
        files=[("file", ("v1.wav", make_wav(), "audio/wav"))],
    ).json()["id"]
    return sid, vid


# --- object-level authorization ------------------------------------------


def test_other_user_cannot_upload_stem_to_foreign_version(client):
    owner = _register(client, "owner")
    attacker = _register(client, "attacker")
    _, vid = _session_with_version(client, owner)

    r = client.post(
        "/api/assets/stems",
        headers=_auth(attacker),
        params={"version_id": vid, "logical_name": "kick", "display_name": "Kick"},
        files=[("file", ("kick.wav", make_wav(), "audio/wav"))],
    )
    assert r.status_code == 404


def test_other_user_cannot_compare_foreign_versions(client):
    owner = _register(client, "owner")
    attacker = _register(client, "attacker")
    _, vid = _session_with_version(client, owner)

    r = client.post(
        "/api/comparisons/versions",
        headers=_auth(attacker),
        json={"base_version_id": vid, "compare_version_id": vid},
    )
    assert r.status_code == 404


def test_private_template_is_not_readable_by_others(client):
    owner = _register(client, "owner")
    attacker = _register(client, "attacker")
    tid = client.post(
        "/api/templates",
        headers=_auth(owner),
        json={"name": "My preset", "service_type": "mixing"},
    ).json()["id"]

    assert client.get(f"/api/templates/{tid}", headers=_auth(attacker)).status_code == 404
    assert client.get(f"/api/templates/{tid}", headers=_auth(owner)).status_code == 200


def test_activity_feed_rejects_foreign_session_id(client):
    owner = _register(client, "owner")
    attacker = _register(client, "attacker")
    sid, _ = _session_with_version(client, owner)

    r = client.get("/api/activity", headers=_auth(attacker), params={"session_id": sid})
    assert r.status_code == 404


# --- share-link gating ----------------------------------------------------


def test_share_allowlist_cannot_be_bypassed_by_omitting_actor(client):
    token = _register(client, "owner")
    h = _auth(token)
    sid, _ = _session_with_version(client, token)
    detail = client.patch(
        f"/api/sessions/{sid}/share",
        headers=h,
        json={"share_allowlist": "client@label.com"},
    ).json()
    share_token = detail["share_token"]

    assert client.get(f"/api/sessions/public/{share_token}").status_code == 403
    assert client.get(
        f"/api/sessions/public/{share_token}", params={"actor": "nope@evil.com"}
    ).status_code == 403
    assert client.get(
        f"/api/sessions/public/{share_token}", params={"actor": "client@label.com"}
    ).status_code == 200


# --- blob ids -------------------------------------------------------------


def test_blob_ids_outside_the_sha256_alphabet_are_rejected(client):
    from app.services import storage

    for bad in ["../../../../etc/passwd", "..", "abc", "", "/etc/passwd", "A" * 64]:
        assert storage.blob_exists(bad) is False
        assert storage.blob_size(bad) == 0
        with pytest.raises(FileNotFoundError):
            storage.read_blob(bad)

    r = client.get(
        "/api/files/..%2f..%2fetc%2fpasswd", headers=_auth(_register(client, "owner"))
    )
    assert r.status_code == 404


# --- SSRF ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/hook",
        "http://[::1]/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/hook",
        "file:///etc/passwd",
        "not-a-url",
    ],
)
def test_webhook_urls_on_non_public_networks_are_rejected(client, url):
    r = client.post(
        "/api/webhooks",
        headers=_auth(_register(client, "owner")),
        json={"url": url, "event": "version.created"},
    )
    assert r.status_code == 400


def test_public_webhook_url_is_accepted(client, monkeypatch):
    import socket

    from app.services import webhooks as webhooks_svc

    monkeypatch.setattr(
        webhooks_svc.socket,
        "getaddrinfo",
        lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    r = client.post(
        "/api/webhooks",
        headers=_auth(_register(client, "owner")),
        json={"url": "https://hooks.example.com/soundhub", "event": "version.created"},
    )
    assert r.status_code in (200, 201)


# --- CORS + secrets -------------------------------------------------------


def test_cors_does_not_echo_arbitrary_origins(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}

    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_production_requires_an_explicit_secret_key(monkeypatch):
    import importlib

    from app import config

    monkeypatch.setenv("SOUNDHUB_ENV", "production")
    monkeypatch.setenv("SOUNDHUB_SECRET_KEY", "")
    with pytest.raises(RuntimeError):
        importlib.reload(config)

    monkeypatch.setenv("SOUNDHUB_SECRET_KEY", "a-real-secret")
    reloaded = importlib.reload(config)
    assert reloaded.SECRET_KEY == "a-real-secret"
    monkeypatch.delenv("SOUNDHUB_ENV")
    importlib.reload(config)
