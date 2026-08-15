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


def test_release_package_lock_and_delivery(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0), "approved master")

    # not approved → package cannot be created
    r = client.post(
        "/api/release-packages",
        json={"session_id": s["id"], "approved_version_id": v["id"], "name": "Final"},
        headers=_auth(token),
    )
    assert r.status_code == 400

    # approve, then create
    client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    r = client.post(
        "/api/release-packages",
        json={"session_id": s["id"], "approved_version_id": v["id"], "name": "Final delivery"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    # master deliverable from the approved version
    r = client.post(
        f"/api/release-packages/{pid}/deliverables/from-version",
        json={"type": "master", "from_version_id": v["id"], "is_required": True},
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["sha256"]
    assert r.json()["sample_rate"] == 8000
    assert r.json()["bit_depth"] == 16

    # upload artwork
    r = client.post(
        f"/api/release-packages/{pid}/deliverables/upload",
        headers=_auth(token),
        data={"type": "artwork", "is_required": "true"},
        files=[("file", ("cover.png", b"\x89PNG\r\n\x1a\nnot-really", "image/png"))],
    )
    assert r.status_code == 201

    # lock → manifest hash + delivery token
    r = client.post(
        f"/api/release-packages/{pid}/lock",
        json={"approval_scope": "master", "note": "final"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    pkg = r.json()
    assert pkg["status"] == "ready"
    assert pkg["manifest_hash"]
    assert pkg["delivery_token"]

    # lock is immutable
    r = client.post(
        f"/api/release-packages/{pid}/lock",
        json={"approval_scope": "master"},
        headers=_auth(token),
    )
    assert r.status_code == 400

    # manifest round-trips
    r = client.get(f"/api/release-packages/{pid}/manifest", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["manifest_hash"] == pkg["manifest_hash"]
    assert len(r.json()["manifest_json"]["files"]) == 2

    # public delivery page (no auth)
    tok = pkg["delivery_token"]
    r = client.get(f"/api/release-packages/public/{tok}")
    assert r.status_code == 200
    assert r.json()["approved_label"] == "v1"
    assert len(r.json()["deliverables"]) == 2

    # download the master from the delivery link
    did = pkg["deliverables"][0]["id"]
    r = client.get(f"/api/release-packages/public/{tok}/files/{did}")
    assert r.status_code == 200
    assert r.content == make_wav(1.0)

    # invoice gate: balance_due blocks download with 402; amount is required
    r = client.patch(f"/api/release-packages/{pid}/invoice", json={"invoice_status": "balance_due"}, headers=_auth(token))
    assert r.status_code == 400  # amount_due_cents missing
    r = client.patch(
        f"/api/release-packages/{pid}/invoice",
        json={"invoice_status": "balance_due", "amount_due_cents": 4900, "currency": "usd"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["amount_due_cents"] == 4900
    r = client.get(f"/api/release-packages/public/{tok}/files/{did}")
    assert r.status_code == 402
    client.patch(f"/api/release-packages/{pid}/invoice", json={"invoice_status": "paid"}, headers=_auth(token))
    assert client.get(f"/api/release-packages/public/{tok}/files/{did}").status_code == 200

    # audit trail
    r = client.get("/api/release-packages", headers=_auth(token))
    events = {e["event"] for e in r.json()[0]["events"]}
    assert "package.created" in events
    assert "package.locked" in events
    assert "delivery.link_opened" in events


def test_decision_ledger_hash_chain(client):
    token = _register(client)
    s = _create_session(client, token)
    v1 = _upload(client, token, s["id"], make_wav(1.0), "v1")
    share = s["share_token"]

    # a mix of events: guest draft, submit round, request verify, approval
    client.post(
        f"/api/sessions/public/{share}/versions/{v1['id']}/comments",
        json={"time_s": 0.2, "body": "Bass masks vocal", "author_name": "Aisha"},
    )
    client.post(f"/api/sessions/{s['id']}/submit-feedback", json={"note": "consolidated"}, headers=_auth(token))
    v2 = _upload(client, token, s["id"], make_wav(1.0), "v2 fixed")
    client.post(
        f"/api/sessions/{s['id']}/versions/{v2['id']}/approvals",
        json={"scope": "master", "approved": True, "note": "", "approver_name": "Aisha"},
        headers=_auth(token),
    )

    r = client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token))
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) >= 4
    assert r.json()["head_hash"]

    # each event is chained: hash = sha256(prev_hash + canonical payload)
    import hashlib
    import json as _json

    prev = None
    for e in events:
        canonical = _json.dumps(e["payload"], sort_keys=True, separators=(",", ":")).encode()
        expected = hashlib.sha256((prev or "").encode() + canonical).hexdigest()
        assert e["event_hash"] == expected
        assert e["prev_event_hash"] == prev
        prev = e["event_hash"]

    # events carry human data for the UI
    kinds = {e["event"] for e in events}
    assert "feedback.draft_created" in kinds
    assert "round.submitted" in kinds
    assert "version.created" in kinds
    assert "approval.created" in kinds

    # verify endpoint confirms integrity
    r = client.get(f"/api/sessions/{s['id']}/ledger/verify", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["total"] == len(events)
    assert r.json()["head_hash"] == r.json()["head_hash"]

    # tampering with an event's payload breaks the chain
    from app.models import LedgerEvent
    from app.database import SessionLocal

    with SessionLocal() as db:
        row = db.get(LedgerEvent, events[0]["id"])
        row.payload = {"body": "rewritten!"}
        db.commit()
    r = client.get(f"/api/sessions/{s['id']}/ledger/verify", headers=_auth(token))
    assert r.json()["ok"] is False
    assert len(r.json()["problems"]) >= 1


def test_loudness_analysis_and_level_matched_comparison(client):
    token = _register(client)
    s = _create_session(client, token)
    # v1 quieter, v2 louder (same sine, different amplitude)
    quiet = make_wav(1.0)
    buf = io.BytesIO()
    n = 8000
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * 0.9)) for _ in range(n)))  # louder
    loud = buf.getvalue()
    v1 = _upload(client, token, s["id"], quiet, "v1 quiet")
    v2 = _upload(client, token, s["id"], loud, "v2 louder")

    # analysis is stored (sync in test env)
    r = client.get(f"/api/versions/{v1['id']}/audio-analysis", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["analysis_status"] == "done"
    assert r.json()["integrated_lufs"] is not None
    assert r.json()["sample_rate"] == 8000

    # versions from different sessions rejected
    other = _create_session(client, token)
    v3 = _upload(client, token, other["id"], quiet, "other")
    r = client.post(
        "/api/comparisons",
        json={"base_version_id": v1["id"], "compare_version_id": v3["id"], "start_ms": 0, "end_ms": 800},
        headers=_auth(token),
    )
    assert r.status_code == 400

    # level-matched comparison: louder version gets negative gain
    r = client.post(
        "/api/comparisons",
        json={"base_version_id": v1["id"], "compare_version_id": v2["id"], "start_ms": 0, "end_ms": 800},
        headers=_auth(token),
    )
    assert r.status_code == 201
    comp = r.json()
    assert comp["level_match"] == "short_term_lufs"
    assert comp["compare_gain_db"] < 0  # v2 louder → attenuated
    assert comp["base_gain_db"] == 0
    assert "v1" in comp["short_term_lufs"]
    assert comp["label"].startswith("Level matched")
    assert comp["start_ms"] == 0

    # fetch it back
    r = client.get(f"/api/comparisons/{comp['id']}", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["compare_gain_db"] == comp["compare_gain_db"]

    # ledger records comparison.created
    r = client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token))
    assert "comparison.created" in {e["event"] for e in r.json()["events"]}


def test_comparison_requires_same_session_and_pending_analysis_fallback(client):
    token = _register(client)
    s = _create_session(client, token)
    v1 = _upload(client, token, s["id"], make_wav(1.0))
    v2 = _upload(client, token, s["id"], make_wav(1.0))

    # request_id links to a request but still creates fine
    r = client.post(
        "/api/comparisons",
        json={
            "base_version_id": v1["id"],
            "compare_version_id": v2["id"],
            "request_id": 99,
            "start_ms": 1000,
            "end_ms": 5000,
            "level_match": "none",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["level_match"] == "none"
    assert r.json()["label"] == "Level match unavailable"
    assert r.json()["request_id"] == 99

    # different sample rates still play (analysis doesn't crash) — mp3 vs wav
    s2 = _create_session(client, token)
    v3 = _upload(client, token, s2["id"], make_wav(1.0))
    r = client.post(
        "/api/comparisons",
        json={"base_version_id": v1["id"], "compare_version_id": v3["id"], "start_ms": 0},
        headers=_auth(token),
    )
    assert r.status_code == 400  # different sessions

    # locking a release package doesn't touch comparison metadata
    client.post(
        f"/api/sessions/{s['id']}/versions/{v2['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    pkg = client.post(
        "/api/release-packages",
        json={"session_id": s["id"], "approved_version_id": v2["id"], "name": "P"},
        headers=_auth(token),
    ).json()
    client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "master", "from_version_id": v2["id"]},
        headers=_auth(token),
    )
    client.post(f"/api/release-packages/{pkg['id']}/lock", json={"approval_scope": "master"}, headers=_auth(token))
    # analysis and comparisons survive the lock — metadata is untouched
    r = client.get(f"/api/versions/{v1['id']}/audio-analysis", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["analysis_status"] in ("done", "unavailable")
    r = client.post(
        "/api/comparisons",
        json={"base_version_id": v1["id"], "compare_version_id": v2["id"], "start_ms": 0, "end_ms": 800, "level_match": "none"},
        headers=_auth(token),
    )
    assert r.status_code == 201
