"""Engineer reputation — trust signals computed from real platform data.

Reputation must be objective (derived from sessions/approvals/deliveries,
never self-reported) and `verified` must only appear when the account has a
linked wallet. The profile (bio / specialty / location) is the only
self-edit part, via PATCH /api/auth/me.
"""

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


def _register(client, username="producer") -> str:
    r = client.post("/api/auth/register", json={"username": username, "password": "secret1"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * 0.5)) for _ in range(8000)))
    return buf.getvalue()


def _approved_session(client, token, name="Neon") -> int:
    """Create a session, upload v1, approve it → returns session_id."""
    r = client.post("/api/sessions", json={"name": name}, headers=_auth(token))
    sid = r.json()["id"]
    r = client.post(
        f"/api/sessions/{sid}/versions",
        headers=_auth(token),
        data={"message": "v1"},
        files=[("file", ("v1.wav", make_wav(), "audio/wav"))],
    )
    vid = r.json()["id"]
    client.post(
        f"/api/sessions/{sid}/versions/{vid}/approvals",
        json={"scope": "master", "approved": True, "note": "", "approver_name": "Aisha"},
        headers=_auth(token),
    )
    return sid


def test_profile_patch_updates_public_profile(client):
    token = _register(client)
    r = client.patch(
        "/api/auth/me",
        json={"bio": "10 years mixing bass-heavy garage", "specialty": "mix_master", "location": "Berlin"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    u = r.json()
    assert u["bio"] == "10 years mixing bass-heavy garage"
    assert u["specialty"] == "mix_master"
    assert u["location"] == "Berlin"
    # empty patch is a no-op
    assert client.patch("/api/auth/me", json={}, headers=_auth(token)).status_code == 200


def test_reputation_is_objective_and_never_self_reported(client):
    token = _register(client)
    username = "producer"
    sid = _approved_session(client, token)

    # public portfolio carries the reputation block
    r = client.get(f"/api/portfolio/{username}")
    assert r.status_code == 200
    rep = r.json()["reputation"]
    assert rep is not None
    assert rep["approved_count"] == 1
    assert rep["session_count"] == 1
    assert rep["delivered_count"] == 0  # no locked package yet
    assert rep["verified"] is False  # no wallet linked
    assert rep["avg_rounds"] == 1.0
    assert rep["bio"] == ""  # nothing self-reported yet
    # badges only from real data — "approved sessions" present, delivery absent
    assert any("approved session" in b for b in rep["badges"])
    assert not any("delivered" in b for b in rep["badges"])
    assert not any("Wallet" in b for b in rep["badges"])

    # the session id above must belong to this engineer (sanity)
    assert rep["session_count"] == 1


def test_reputation_verified_requires_wallet(client):
    """verified badge appears only with a linked wallet (signature-checked login)."""
    import app.wallet_auth as wa

    token = _register(client, "engineer")
    # fake a wallet-bound account (real path: /api/auth/wallet/login verifies a signature)
    from app.database import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        u = db.query(User).filter(User.username == "engineer").first()
        u.wallet_address = "0x" + "cd" * 20  # distinct from the demo seed wallet
        db.add(u)
        db.commit()

    r = client.get("/api/portfolio/engineer")
    rep = r.json()["reputation"]
    assert rep["verified"] is True
    assert any("Wallet" in b for b in rep["badges"])
    assert wa is not None  # import sanity


def test_reputation_delivered_count_from_locked_package(client):
    token = _register(client)
    username = "producer"
    sid = _approved_session(client, token)
    # find approved version id
    s = client.get(f"/api/sessions/{sid}", headers=_auth(token)).json()
    vid = s["versions"][0]["id"]
    # build + lock a release package → delivered_count becomes 1
    r = client.post(
        "/api/release-packages",
        json={"session_id": sid, "approved_version_id": vid, "template": "custom"},
        headers=_auth(token),
    )
    pkg = r.json()
    client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "master", "from_version_id": vid},
        headers=_auth(token),
    )
    client.post(f"/api/release-packages/{pkg['id']}/preflight", headers=_auth(token))
    r = client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": "master", "note": "final"},
        headers=_auth(token),
    )
    assert r.status_code == 200

    rep = client.get(f"/api/portfolio/{username}").json()["reputation"]
    assert rep["delivered_count"] == 1
    assert any("delivered package" in b for b in rep["badges"])


def test_reputation_on_time_rate_with_deadline(client):
    token = _register(client)
    username = "producer"
    # deadline in the future, approval happens now → on time
    r = client.post("/api/sessions", json={"name": "OnTime"}, headers=_auth(token))
    sid = r.json()["id"]
    from datetime import datetime, timedelta, timezone

    client.patch(
        f"/api/sessions/{sid}/brief",
        json={"deadline_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()},
        headers=_auth(token),
    )
    r = client.post(
        f"/api/sessions/{sid}/versions",
        headers=_auth(token),
        data={"message": "v1"},
        files=[("file", ("v1.wav", make_wav(), "audio/wav"))],
    )
    vid = r.json()["id"]
    client.post(
        f"/api/sessions/{sid}/versions/{vid}/approvals",
        json={"scope": "master", "approved": True, "note": "", "approver_name": "Aisha"},
        headers=_auth(token),
    )

    rep = client.get(f"/api/portfolio/{username}").json()["reputation"]
    assert rep["on_time_rate"] == 1.0
    assert any("On-time" in b for b in rep["badges"])
