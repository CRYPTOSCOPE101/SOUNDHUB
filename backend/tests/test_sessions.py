import io
import struct
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

    from app import config
    from app import database

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "BLOB_DIR", tmp_path / "blobs")
    monkeypatch.setattr(config, "TMP_DIR", tmp_path / "tmp")
    config.ensure_dirs()

    test_db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(config, "DATABASE_URL", test_db_url)
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=test_engine, autoflush=False, autocommit=False),
    )
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c


def make_wav(seconds: float = 1.0, sample_rate: int = 8000) -> bytes:
    """A tiny real PCM WAV (mono 16-bit) with a sine tone."""
    buf = io.BytesIO()
    n = int(seconds * sample_rate)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = b"".join(
            struct.pack("<h", int(8000 * (0.5 + 0.5 * ((i // 400) % 2)))) for i in range(n)
        )
        w.writeframes(frames)
    return buf.getvalue()


def _register(client, username="producer") -> str:
    r = client.post("/api/auth/register", json={"username": username, "password": "secret1"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_session(client, token, name="Neon Warehouse"):
    r = client.post("/api/sessions", json={"name": name}, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, token, sid, wav, message="v1"):
    r = client.post(
        f"/api/sessions/{sid}/versions",
        headers=_auth(token),
        data={"message": message},
        files=[("file", ("track.wav", wav, "audio/wav"))],
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_session_crud_and_access_control(client):
    token = _register(client)
    other = _register(client, "other")

    s = _create_session(client, token)
    assert s["share_token"]
    assert s["version_count"] == 0

    # other users can't see it
    r = client.get(f"/api/sessions/{s['id']}", headers=_auth(other))
    assert r.status_code == 404

    # owner can
    r = client.get(f"/api/sessions/{s['id']}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["versions"] == []

    r = client.delete(f"/api/sessions/{s['id']}", headers=_auth(token))
    assert r.status_code == 204


def test_upload_version_with_real_waveform(client):
    token = _register(client)
    s = _create_session(client, token)
    wav = make_wav(seconds=2.0)
    v = _upload(client, token, s["id"], wav, "initial bounce")

    assert v["label"] == "v1"
    assert v["audio_format"] == "wav"
    assert v["duration_s"] == pytest.approx(2.0, abs=0.1)
    assert v["waveform_synthetic"] is False
    assert len(v["waveform"]) == 96
    assert all(0.0 <= p <= 1.0 for p in v["waveform"])

    # audio downloadable
    r = client.get(f"/api/sessions/{s['id']}/versions/{v['id']}/audio", headers=_auth(token))
    assert r.status_code == 200
    assert r.content == wav


def test_second_version_numbering(client):
    token = _register(client)
    s = _create_session(client, token)
    v1 = _upload(client, token, s["id"], make_wav(1.0), "take one")
    v2 = _upload(client, token, s["id"], make_wav(1.0), "bass revised")
    assert v1["label"] == "v1"
    assert v2["label"] == "v2"
    assert v2["number"] == 2


def test_comments_resolve_and_status(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(2.0))

    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/comments",
        json={"time_s": 1.2, "body": "Kick and bass clash here."},
        headers=_auth(token),
    )
    assert r.status_code == 201
    cid = r.json()["id"]
    assert r.json()["author_name"] == "producer"

    # reply
    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/comments",
        json={"time_s": 1.2, "body": "On it — replacing the bass patch.", "parent_id": cid},
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["parent_id"] == cid

    # resolve
    r = client.patch(
        f"/api/sessions/{s['id']}/versions/{v['id']}/comments/{cid}",
        params={"resolved": "true"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["resolved"] is True

    # status flow
    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "needs_changes"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "needs_changes"

    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    assert r.json()["status"] == "approved"

    # invalid status rejected
    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "bogus"},
        headers=_auth(token),
    )
    assert r.status_code == 422


def test_public_share_no_account(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0))
    share = s["share_token"]

    # guest can read the session (waveform included) without auth
    r = client.get(f"/api/sessions/public/{share}")
    assert r.status_code == 200
    assert r.json()["name"] == "Neon Warehouse"
    assert len(r.json()["versions"]) == 1
    assert len(r.json()["versions"][0]["waveform"]) == 96

    # guest can comment without an account
    r = client.post(
        f"/api/sessions/public/{share}/versions/{v['id']}/comments",
        json={"time_s": 0.5, "body": "Hats are great after the drop.", "author_name": "Aisha (A&R)"},
    )
    assert r.status_code == 201
    assert r.json()["author_name"] == "Aisha (A&R)"

    # owner sees the guest comment
    r = client.get(f"/api/sessions/{s['id']}", headers=_auth(token))
    comments = r.json()["versions"][0]["comments"]
    assert any(c["author_name"] == "Aisha (A&R)" for c in comments)

    # unknown share token → 404
    r = client.get("/api/sessions/public/nonexistent-token")
    assert r.status_code == 404


def test_reject_non_audio_upload(client):
    token = _register(client)
    s = _create_session(client, token)
    r = client.post(
        f"/api/sessions/{s['id']}/versions",
        headers=_auth(token),
        data={"message": ""},
        files=[("file", ("evil.exe", b"MZ...", "application/octet-stream"))],
    )
    assert r.status_code == 400
