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
    # the full detail includes approval_preset + members
    r = client.get(f"/api/sessions/{r.json()['id']}", headers=_auth(token))
    assert r.status_code == 200, r.text
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


def _set_preset(client, token, sid, preset):
    r = client.put(f"/api/sessions/{sid}/approval-preset", json={"preset": preset}, headers=_auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _invite(client, token, sid, email, role):
    r = client.post(f"/api/sessions/{sid}/members", json={"email": email, "role": role}, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


def _approve(client, token, sid, share_token, version_id, scope, approver_name, approved=True):
    r = client.post(
        f"/api/sessions/public/{share_token}/versions/{version_id}/approvals",
        json={"scope": scope, "approved": approved, "note": "ok", "approver_name": approver_name},
    )
    return r


def _package_and_lock(client, token, sid, version_id, scope):
    pkg = client.post(
        "/api/release-packages",
        json={"session_id": sid, "approved_version_id": version_id, "name": "P"},
        headers=_auth(token),
    ).json()
    r = client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "master", "from_version_id": version_id},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": scope},
        headers=_auth(token),
    )


# ---------- presets & members ----------


def test_default_preset_is_solo_client(client):
    token = _register(client)
    s = _create_session(client, token)
    assert s["approval_preset"] == "solo_client"
    assert s["members"] == []


def test_set_preset_and_ledger(client):
    token = _register(client)
    s = _create_session(client, token)
    r = _set_preset(client, token, s["id"], "label_workflow")
    assert r["preset"] == "label_workflow"
    assert r["enforced"] is True
    assert "label_admin" in r["policy"]["release"]
    r = client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token))
    assert "team.preset_updated" in [e["event"] for e in r.json()["events"]]


def test_invite_list_remove_members(client):
    token = _register(client)
    s = _create_session(client, token)
    _invite(client, token, s["id"], "aisha@label.com", "artist")
    _invite(client, token, s["id"], "arnie@label.com", "a_r")
    # duplicate invite rejected
    r = client.post(
        f"/api/sessions/{s['id']}/members",
        json={"email": "AISHA@label.com", "role": "artist"},
        headers=_auth(token),
    )
    assert r.status_code == 400
    r = client.get(f"/api/sessions/{s['id']}/members", headers=_auth(token))
    assert len(r.json()) == 2
    mid = r.json()[0]["id"]
    r = client.delete(f"/api/sessions/{s['id']}/members/{mid}", headers=_auth(token))
    assert r.status_code == 204
    r = client.get(f"/api/sessions/{s['id']}/members", headers=_auth(token))
    assert len(r.json()) == 1


# ---------- enforced approval chain (label workflow) ----------


def test_label_workflow_gates_approvals_by_role(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_preset(client, token, s["id"], "label_workflow")
    v = _upload(client, token, s["id"], make_wav())
    st = s["share_token"]

    # uninvited guest cannot approve
    r = _approve(client, token, s["id"], st, v["id"], "mix", "stranger@x.io")
    assert r.status_code == 403

    _invite(client, token, s["id"], "aisha@label.com", "artist")
    _invite(client, token, s["id"], "arnie@label.com", "a_r")
    _invite(client, token, s["id"], "boss@label.com", "label_admin")

    # artist approves mix
    r = _approve(client, token, s["id"], st, v["id"], "mix", "aisha@label.com")
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "artist"

    # artist + A&R approve master
    r = _approve(client, token, s["id"], st, v["id"], "master", "aisha@label.com")
    assert r.status_code == 201
    r = _approve(client, token, s["id"], st, v["id"], "master", "arnie@label.com")
    assert r.status_code == 201

    # artist cannot sign off release — only label admin can
    r = _approve(client, token, s["id"], st, v["id"], "release", "aisha@label.com")
    assert r.status_code == 403
    r = _approve(client, token, s["id"], st, v["id"], "release", "boss@label.com")
    assert r.status_code == 201
    assert r.json()["role"] == "label_admin"


def test_lock_gated_by_approval_policy(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_preset(client, token, s["id"], "label_workflow")
    v = _upload(client, token, s["id"], make_wav())
    st = s["share_token"]
    _invite(client, token, s["id"], "aisha@label.com", "artist")
    _invite(client, token, s["id"], "arnie@label.com", "a_r")

    # only artist approved mix → master lock blocked (A&R missing)
    _approve(client, token, s["id"], st, v["id"], "mix", "aisha@label.com")
    r = _package_and_lock(client, token, s["id"], v["id"], "master")
    assert r.status_code == 403, r.text
    assert "A&R" in r.json()["detail"]

    # artist + A&R sign master → master lock passes
    _approve(client, token, s["id"], st, v["id"], "master", "aisha@label.com")
    _approve(client, token, s["id"], st, v["id"], "master", "arnie@label.com")
    r = _package_and_lock(client, token, s["id"], v["id"], "master")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready"


def test_release_lock_requires_master_prerequisite(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_preset(client, token, s["id"], "label_workflow")
    v = _upload(client, token, s["id"], make_wav())
    st = s["share_token"]
    _invite(client, token, s["id"], "boss@label.com", "label_admin")

    # label admin signs release, but master was never approved → still blocked
    _approve(client, token, s["id"], st, v["id"], "release", "boss@label.com")
    r = _package_and_lock(client, token, s["id"], v["id"], "release")
    assert r.status_code == 403, r.text


def test_new_version_does_not_inherit_approvals(client):
    token = _register(client)
    s = _create_session(client, token)
    _set_preset(client, token, s["id"], "label_workflow")
    v1 = _upload(client, token, s["id"], make_wav(), message="v1")
    st = s["share_token"]
    for email, role in (("aisha@label.com", "artist"), ("arnie@label.com", "a_r"), ("boss@label.com", "label_admin")):
        _invite(client, token, s["id"], email, role)
    # full sign-off on v1
    _approve(client, token, s["id"], st, v1["id"], "mix", "aisha@label.com")
    _approve(client, token, s["id"], st, v1["id"], "master", "aisha@label.com")
    _approve(client, token, s["id"], st, v1["id"], "master", "arnie@label.com")
    _approve(client, token, s["id"], st, v1["id"], "release", "boss@label.com")

    # v2 only carries its OWN approvals: artist signs mix, but the master
    # chain (artist + A&R) is missing → v1's sign-offs don't carry over
    v2 = _upload(client, token, s["id"], make_wav(), message="v2")
    _approve(client, token, s["id"], st, v2["id"], "mix", "aisha@label.com")
    r = _package_and_lock(client, token, s["id"], v2["id"], "master")
    assert r.status_code == 403, r.text
    assert "A&R" in r.json()["detail"]

    # ...but v1 keeps its sign-offs and still locks fine
    r = _package_and_lock(client, token, s["id"], v1["id"], "release")
    assert r.status_code == 200, r.text


# ---------- permissive default stays untouched ----------


def test_solo_client_guest_approves_without_team(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav())
    r = _approve(client, token, s["id"], s["share_token"], v["id"], "master", "client@mail.com")
    assert r.status_code == 201, r.text
    assert r.json()["role"] == ""  # no role gymnastics for solo clients
    r = _package_and_lock(client, token, s["id"], v["id"], "master")
    assert r.status_code == 200, r.text
