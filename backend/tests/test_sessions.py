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


def test_approval_artifact(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0))

    # needs changes requires a note
    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/approvals",
        json={"scope": "mix", "approved": False, "note": "", "approver_name": "Aisha"},
        headers=_auth(token),
    )
    assert r.status_code == 400

    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/approvals",
        json={"scope": "mix", "approved": False, "note": "Bass masks the vocal", "approver_name": "Aisha"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["scope"] == "mix"
    assert r.json()["approved"] is False

    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/approvals",
        json={"scope": "master", "approved": True, "note": "", "approver_name": "Label"},
        headers=_auth(token),
    )
    assert r.status_code == 201

    # session detail carries approvals
    r = client.get(f"/api/sessions/{s['id']}", headers=_auth(token))
    detail = r.json()
    assert len(detail["approvals"]) == 2
    assert detail["versions"][0]["status"] == "approved"

    # guest can approve via share link
    share = s["share_token"]
    r = client.post(
        f"/api/sessions/public/{share}/versions/{v['id']}/approvals",
        json={"scope": "arrangement", "approved": True, "note": "", "approver_name": "Artist"},
    )
    assert r.status_code == 201


def test_carry_unresolved_comments(client):
    token = _register(client)
    s = _create_session(client, token)
    v1 = _upload(client, token, s["id"], make_wav(1.0), "v1")

    c1 = client.post(
        f"/api/sessions/{s['id']}/versions/{v1['id']}/comments",
        json={"time_s": 0.3, "body": "Still open note"},
        headers=_auth(token),
    ).json()
    c2 = client.post(
        f"/api/sessions/{s['id']}/versions/{v1['id']}/comments",
        json={"time_s": 0.7, "body": "Resolved note"},
        headers=_auth(token),
    ).json()
    client.patch(
        f"/api/sessions/{s['id']}/versions/{v1['id']}/comments/{c2['id']}",
        params={"resolved": "true"},
        headers=_auth(token),
    )

    v2 = _upload(client, token, s["id"], make_wav(1.0), "v2")
    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v1['id']}/carry",
        headers=_auth(token),
    )
    assert r.status_code == 201
    carried = r.json()["comments"]
    assert len(carried) == 1  # only the unresolved one
    assert "carried" in carried[0]["author_name"]
    assert carried[0]["body"] == "Still open note"

    # carrying onto itself is rejected
    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v2['id']}/carry",
        headers=_auth(token),
    )
    assert r.status_code == 400


def test_share_settings_password_and_permissions(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0))
    share = s["share_token"]

    # set permission to view-only + allowlist
    r = client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"share_permission": "view", "share_allowlist": "aisha@label.com"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["share_permission"] == "view"

    # view works, commenting blocked by permission
    assert client.get(f"/api/sessions/public/{share}", params={"actor": "aisha@label.com"}).status_code == 200
    assert client.get(f"/api/sessions/public/{share}", params={"actor": "stranger@x.com"}).status_code == 403
    r = client.post(
        f"/api/sessions/public/{share}/versions/{v['id']}/comments",
        json={"time_s": 0.5, "body": "nope", "author_name": "aisha@label.com"},
    )
    assert r.status_code == 403

    # download blocked at view level
    assert client.get(f"/api/sessions/public/{share}/versions/{v['id']}/audio", params={"actor": "aisha@label.com"}).status_code == 403

    # raise permission to download → allowed + audited
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"share_permission": "download", "share_allowlist": "aisha@label.com"},
        headers=_auth(token),
    )
    assert client.get(f"/api/sessions/public/{share}/versions/{v['id']}/audio", params={"actor": "aisha@label.com"}).status_code == 200

    # password protects the link
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"share_permission": "comment", "share_allowlist": "", "share_password": "hunter2"},
        headers=_auth(token),
    )
    assert client.get(f"/api/sessions/public/{share}").status_code == 401
    assert client.get(f"/api/sessions/public/{share}", params={"password": "wrong"}).status_code == 401
    assert client.get(f"/api/sessions/public/{share}", params={"password": "hunter2"}).status_code == 200

    # audit events recorded
    r = client.get(f"/api/sessions/{s['id']}", headers=_auth(token))
    actions = {e["action"] for e in r.json()["access_events"]}
    assert "opened" in actions
    assert "downloaded" in actions


def test_revision_rounds_consolidated_feedback(client):
    token = _register(client)
    s = _create_session(client, token)
    v1 = _upload(client, token, s["id"], make_wav(1.0))
    share = s["share_token"]

    # reviewers leave private draft notes via the share link
    for i, body in enumerate(["Bass masks vocal", "Hats too loud", "Outro needs air"]):
        r = client.post(
            f"/api/sessions/public/{share}/versions/{v1['id']}/comments",
            json={"time_s": 0.2 + i * 0.3, "body": body, "author_name": f"reviewer{i}"},
        )
        assert r.status_code == 201
        assert r.json()["status"] == "draft"  # guests always leave drafts

    # drafts are visible to the owner but not yet open requests
    r = client.get(f"/api/sessions/{s['id']}", headers=_auth(token))
    assert all(c["status"] == "draft" for c in r.json()["versions"][0]["comments"])

    # submit feedback: drafts consolidate into one round of open requests
    r = client.post(
        f"/api/sessions/{s['id']}/submit-feedback",
        json={"note": "Consolidated notes from A&R + artist"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    detail = r.json()
    assert detail["round_number"] == 2
    assert detail["rounds"][0]["number"] == 1
    assert detail["rounds"][0]["status"] == "submitted"
    assert detail["rounds"][0]["request_count"] == 3
    assert all(c["status"] == "open" for c in detail["versions"][0]["comments"])

    # round 1 closed: guests can no longer add notes
    r = client.post(
        f"/api/sessions/public/{share}/versions/{v1['id']}/comments",
        json={"time_s": 0.9, "body": "too late", "author_name": "latecomer"},
    )
    assert r.status_code == 403

    # upload v2 belongs to round 2 and auto-marks requests on v1 as fixed
    v2 = _upload(client, token, s["id"], make_wav(1.0), "v2 bass fixed")
    assert v2["round_number"] == 2
    r = client.get(f"/api/sessions/{s['id']}", headers=_auth(token))
    v1_out = next(v for v in r.json()["versions"] if v["id"] == v1["id"])
    fixed = [c for c in v1_out["comments"] if c["status"] == "fixed"]
    assert len(fixed) == 3
    assert fixed[0]["fixed_in"] == v2["id"]

    # owner can move a request through its lifecycle
    cid = fixed[0]["id"]
    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v1['id']}/requests/{cid}/status",
        json={"status": "verified"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "verified"
    assert r.json()["verified_at"]

    # approving closes it
    r = client.post(
        f"/api/sessions/{s['id']}/versions/{v1['id']}/requests/{cid}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    assert r.json()["status"] == "approved"
    assert r.json()["resolved"] is True


def test_feedback_owner_submits_via_share_link(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0))
    share = s["share_token"]

    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"feedback_owner": "aisha@label.com"},
        headers=_auth(token),
    )

    client.post(
        f"/api/sessions/public/{share}/versions/{v['id']}/comments",
        json={"time_s": 0.3, "body": "draft note", "author_name": "artist@mail.com"},
    )

    # wrong actor can't submit
    r = client.post(
        f"/api/sessions/public/{share}/submit-feedback",
        json={"note": ""},
        params={"actor": "stranger@x.com"},
    )
    assert r.status_code == 403

    # the feedback owner can
    r = client.post(
        f"/api/sessions/public/{share}/submit-feedback",
        json={"note": "Aisha's consolidated list"},
        params={"actor": "aisha@label.com"},
    )
    assert r.status_code == 200
    assert r.json()["round_number"] == 2
    assert r.json()["rounds"][0]["request_count"] == 1
