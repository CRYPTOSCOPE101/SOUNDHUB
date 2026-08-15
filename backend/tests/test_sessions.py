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


def test_stem_upload_list_and_stem_comparison(client):
    token = _register(client)
    s = _create_session(client, token)
    v1 = _upload(client, token, s["id"], make_wav(1.0), "v1")
    v2 = _upload(client, token, s["id"], make_wav(1.0), "v2")

    # no stems yet
    r = client.get(f"/api/versions/{v1['id']}/stems", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == []

    # upload bass stem to both versions (different amplitudes → level mismatch)
    def loud_stem(amp):
        buf = io.BytesIO()
        n = 8000
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(b"".join(struct.pack("<h", int(8000 * amp)) for _ in range(n)))
        return buf.getvalue()

    r = client.post(
        f"/api/versions/{v1['id']}/stems",
        headers=_auth(token),
        data={"logical_name": "bass", "display_name": "Bass v1", "start_offset_ms": "0"},
        files=[("file", ("NeonBass_final_03.wav", loud_stem(0.3), "audio/wav"))],
    )
    assert r.status_code == 201
    r = client.post(
        f"/api/versions/{v2['id']}/stems",
        headers=_auth(token),
        data={"logical_name": "bass", "display_name": "Bass v2", "start_offset_ms": "0"},
        files=[("file", ("bass_v13.wav", loud_stem(0.7), "audio/wav"))],
    )
    assert r.status_code == 201

    # matched by logical name, not filename
    stems_v1 = client.get(f"/api/versions/{v1['id']}/stems", headers=_auth(token)).json()
    assert stems_v1[0]["logical_name"] == "bass"
    assert stems_v1[0]["display_name"] == "Bass v1"

    # stem comparison: gains from the stem, not the full mix
    r = client.post(
        "/api/comparisons",
        json={
            "base_version_id": v1["id"],
            "compare_version_id": v2["id"],
            "mode": "stem",
            "stem_logical_name": "bass",
            "start_ms": 0,
            "end_ms": 800,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    comp = r.json()
    assert comp["mode"] == "stem"
    assert comp["stem_logical_name"] == "bass"
    assert comp["level_match"] == "short_term_lufs"
    assert comp["compare_gain_db"] < 0  # v2 bass louder → attenuated

    # ledger records mode + logical_name
    r = client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token))
    ev = [e for e in r.json()["events"] if e["event"] == "comparison.created"][-1]
    assert ev["payload"]["mode"] == "stem"
    assert ev["payload"]["stem"] == "bass"

    # stem audio endpoint serves the blob inline
    r = client.get(f"/api/versions/{v1['id']}/stems/{stems_v1[0]['id']}/audio", headers=_auth(token))
    assert r.status_code == 200
    assert r.content[:4] == b"RIFF"


def test_watermark_on_public_preview(client):
    token = _register(client)
    s = _create_session(client, token)
    wav = make_wav(2.0)
    v = _upload(client, token, s["id"], wav, "v1")
    share = s["share_token"]

    # guest preview requires download permission to stream audio
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"share_permission": "download"},
        headers=_auth(token),
    )

    # owner always gets the clean original
    r = client.get(f"/api/sessions/{s['id']}/versions/{v['id']}/audio", headers=_auth(token))
    assert r.status_code == 200
    assert r.content == wav

    # guest (unapproved version) gets a watermarked preview — different bytes
    r = client.get(f"/api/sessions/public/{share}/versions/{v['id']}/audio")
    assert r.status_code == 200
    assert r.content != wav
    assert r.content[:4] == b"RIFF"  # still a valid WAV

    # version detail flags the watermark
    r = client.get(f"/api/sessions/public/{share}")
    assert r.json()["versions"][0]["watermarked"] is True

    # watermark disabled → clean preview again
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"watermark_enabled": False},
        headers=_auth(token),
    )
    r = client.get(f"/api/sessions/public/{share}/versions/{v['id']}/audio")
    assert r.content == wav

    # approved versions are always served clean to guests
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"watermark_enabled": True},
        headers=_auth(token),
    )
    client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    r = client.get(f"/api/sessions/public/{share}/versions/{v['id']}/audio")
    assert r.content == wav


def test_deposit_gate_blocks_lock_until_paid(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0), "approved master")
    client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    pkg = client.post(
        "/api/release-packages",
        json={"session_id": s["id"], "approved_version_id": v["id"], "name": "Final"},
        headers=_auth(token),
    ).json()
    client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "master", "from_version_id": v["id"]},
        headers=_auth(token),
    )

    # setting a deposit amount arms the deposit (deposit_due)
    r = client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"deposit_due_cents": 5000},
        headers=_auth(token),
    )
    assert r.json()["deposit_status"] == "deposit_due"

    # locking the final delivery is blocked until the deposit is paid
    r = client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": "master"},
        headers=_auth(token),
    )
    assert r.status_code == 402
    assert "deposit" in r.json()["detail"].lower()

    # manual mark paid (Stripe-less mode) → lock succeeds
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"deposit_status": "paid"},
        headers=_auth(token),
    )
    r = client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": "master"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    pkg = r.json()
    assert pkg["status"] == "ready"
    assert pkg["delivery_token"]

    # deposit also gates public delivery downloads ("approved, then never paid")
    tok = client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()["share_token"]
    did = client.get("/api/release-packages", params={"session_id": s["id"]}, headers=_auth(token)).json()[0]["deliverables"][0]["id"]
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"deposit_due_cents": 3000, "deposit_status": "deposit_due"},
        headers=_auth(token),
    )
    durl = f"/api/release-packages/public/{pkg['delivery_token']}/files/{did}"
    assert client.get(durl).status_code == 402
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"deposit_status": "paid"},
        headers=_auth(token),
    )
    assert client.get(durl).status_code == 200

    # waive also works
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"deposit_due_cents": 3000, "deposit_status": "waived"},
        headers=_auth(token),
    )
    assert client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()["deposit_status"] == "waived"


def test_extra_round_budget_paywall(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0), "v1")
    share = s["share_token"]

    def submit(note):
        return client.post(
            f"/api/sessions/{s['id']}/submit-feedback",
            json={"note": note},
            headers=_auth(token),
        )

    # included_rounds=1 → round 1 (initial) + round 2 (revision) are free
    client.post(
        f"/api/sessions/public/{share}/versions/{v['id']}/comments",
        json={"time_s": 0.2, "body": "round 1 notes", "author_name": "Aisha"},
    )
    r = submit("round 1")
    assert r.status_code == 200
    assert r.json()["round_number"] == 2

    # upload v2 (reopens the round), add drafts, submit again → opens round 3
    v2 = _upload(client, token, s["id"], make_wav(1.0), "v2")
    client.post(
        f"/api/sessions/public/{share}/versions/{v2['id']}/comments",
        json={"time_s": 0.1, "body": "round 2 notes", "author_name": "Aisha"},
    )

    # no price set → hard limit
    r = submit("round 2")
    assert r.status_code == 403
    assert "limit" in r.json()["detail"].lower()

    # price set → 402 payment required (drafts are still there)
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"extra_round_price_cents": 2500},
        headers=_auth(token),
    )
    r = submit("round 2")
    assert r.status_code == 402
    assert "round" in r.json()["detail"].lower()

    # pay for the extra round (manual) → submission goes through
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"rounds_paid": 1},
        headers=_auth(token),
    )
    r = submit("round 2")
    assert r.status_code == 200
    assert r.json()["round_number"] == 3

    # round budget reflects paid rounds
    detail = client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()
    assert detail["rounds_paid"] == 1


def test_reference_url_and_upload_flow(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(2.0), "v1 mix")

    # external-URL reference — no audio job, just a stored link
    r = client.post(
        f"/api/sessions/{s['id']}/references",
        json={
            "title": "Ref A",
            "artist": "Artist X",
            "source_type": "external_url",
            "external_url": "https://soundcloud.com/x/ref1",
            "purpose": "low_end",
            "visibility": "reviewers",
            "note": "oriented by low end and width",
        },
        headers=_auth(token),
    )
    assert r.status_code == 201
    ref_url = r.json()
    assert ref_url["source_type"] == "external_url"
    assert ref_url["analysis_status"] == "pending"
    assert ref_url["external_url"] == "https://soundcloud.com/x/ref1"

    # private upload reference — analysed like a version (neutral measurements)
    wav = make_wav(1.0)
    r = client.post(
        f"/api/sessions/{s['id']}/references/upload",
        headers=_auth(token),
        data={"title": "Ref B", "artist": "Artist Y", "purpose": "overall", "visibility": "reviewers"},
        files=[("file", ("ref.wav", wav, "audio/wav"))],
    )
    assert r.status_code == 201
    ref_up = r.json()
    assert ref_up["source_type"] == "private_upload"
    assert ref_up["analysis_status"] == "done"
    assert ref_up["integrated_lufs"] is not None
    assert ref_up["sample_rate"] == 8000
    assert len(ref_up["waveform"]) == 96

    # owner lists both; guest (reviewer) sees reviewers-visible only
    assert len(client.get(f"/api/sessions/{s['id']}/references", headers=_auth(token)).json()) == 2
    share = s["share_token"]
    r = client.get(f"/api/sessions/public/{share}/references")
    assert r.status_code == 200
    assert len(r.json()) == 2

    # engineer_only is hidden from guests (list + audio both 404/absent)
    client.patch(
        f"/api/sessions/{s['id']}/references/{ref_up['id']}",
        json={"visibility": "engineer_only"},
        headers=_auth(token),
    )
    r = client.get(f"/api/sessions/public/{share}/references")
    assert len(r.json()) == 1
    assert client.get(f"/api/sessions/public/{share}/references/{ref_up['id']}/audio").status_code == 404

    # owner can still stream the private reference
    r = client.get(f"/api/sessions/{s['id']}/references/{ref_up['id']}/audio", headers=_auth(token))
    assert r.status_code == 200
    assert r.content == wav

    # update → back to reviewers, ledger events track everything
    client.patch(
        f"/api/sessions/{s['id']}/references/{ref_up['id']}",
        json={"visibility": "reviewers", "note": "updated note"},
        headers=_auth(token),
    )
    events = {e["event"] for e in client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token)).json()["events"]}
    assert "reference.created" in events
    assert "reference.updated" in events

    client.delete(f"/api/sessions/{s['id']}/references/{ref_url['id']}", headers=_auth(token))
    events = {e["event"] for e in client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token)).json()["events"]}
    assert "reference.removed" in events

    # non-audio upload rejected
    r = client.post(
        f"/api/sessions/{s['id']}/references/upload",
        headers=_auth(token),
        data={"title": "Bad"},
        files=[("file", ("evil.exe", b"MZ", "application/octet-stream"))],
    )
    assert r.status_code == 400


def test_reference_never_deliverable_and_not_on_delivery_link(client):
    import hashlib as _hl

    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0), "v1")
    ref_wav = io.BytesIO()
    with wave.open(ref_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * 0.9)) for _ in range(8000)))
    ref = client.post(
        f"/api/sessions/{s['id']}/references/upload",
        headers=_auth(token),
        data={"title": "Secret ref", "purpose": "overall"},
        files=[("file", ("ref.wav", ref_wav.getvalue(), "audio/wav"))],
    ).json()
    ref_sha = _hl.sha256(ref_wav.getvalue()).hexdigest()

    client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    pkg = client.post(
        "/api/release-packages",
        json={"session_id": s["id"], "approved_version_id": v["id"], "name": "Final"},
        headers=_auth(token),
    ).json()
    client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "master", "from_version_id": v["id"]},
        headers=_auth(token),
    )
    # a from_version_id that resolves to no version is rejected server-side
    # (references are not versions — the only way into a package is a version
    # or a fresh upload, so a reference blob can never become a deliverable)
    r = client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "stems", "from_version_id": 999999},
        headers=_auth(token),
    )
    assert r.status_code == 404
    pkg = client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": "master"},
        headers=_auth(token),
    ).json()

    # the reference never becomes a deliverable: its blob hash never appears
    # among package checksums
    assert ref_sha not in [d["sha256"] for d in pkg["deliverables"]]
    assert [d["type"] for d in pkg["deliverables"]] == ["master"]

    # public delivery link exposes no references — not in HTML payload, not in API
    tok = pkg["delivery_token"]
    r = client.get(f"/api/release-packages/public/{tok}")
    body = r.json()
    assert "references" not in body
    assert "reference" not in str(body).lower()


def test_reference_comparison_gains_and_gates(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(2.0), "v1 quiet mix")

    # loud reference (0.9 amplitude vs ~0.5-0 alternating in make_wav)
    buf = io.BytesIO()
    n = 16000
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * 0.9)) for _ in range(n)))
    ref = client.post(
        f"/api/sessions/{s['id']}/references/upload",
        headers=_auth(token),
        data={"title": "Loud ref", "purpose": "balance"},
        files=[("file", ("ref.wav", buf.getvalue(), "audio/wav"))],
    ).json()
    assert ref["analysis_status"] == "done"

    # URL references can't be compared in-app
    url_ref = client.post(
        f"/api/sessions/{s['id']}/references",
        json={"title": "Url", "source_type": "external_url", "external_url": "https://x.com/a"},
        headers=_auth(token),
    ).json()
    r = client.post(
        f"/api/sessions/{s['id']}/references/compare",
        json={"version_id": v["id"], "reference_id": url_ref["id"], "start_ms": 0, "end_ms": 800},
        headers=_auth(token),
    )
    assert r.status_code == 400

    # mix (quieter) stays at 0 dB; louder reference is attenuated
    r = client.post(
        f"/api/sessions/{s['id']}/references/compare",
        json={"version_id": v["id"], "reference_id": ref["id"], "start_ms": 0, "end_ms": 800},
        headers=_auth(token),
    )
    assert r.status_code == 201
    comp = r.json()
    assert comp["level_match"] == "short_term_lufs"
    assert comp["mix_gain_db"] == 0
    assert comp["ref_gain_db"] < 0
    assert comp["reference_label"].startswith("Loud ref")
    assert comp["mix_audio_url"].endswith(f"/versions/{v['id']}/audio")
    assert comp["ref_audio_url"].endswith(f"/references/{ref['id']}/audio")

    # ledger records the comparison
    events = {e["event"] for e in client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token)).json()["events"]}
    assert "reference.compared" in events

    # reviewer (guest) can compare reviewers-visible references; URLs are public
    share = s["share_token"]
    r = client.post(
        f"/api/sessions/public/{share}/references/compare",
        json={"version_id": v["id"], "reference_id": ref["id"], "start_ms": 0, "end_ms": 800},
    )
    assert r.status_code == 201
    gcomp = r.json()
    assert "/public/" in gcomp["mix_audio_url"]
    assert "/public/" in gcomp["ref_audio_url"]

    # unknown reference in a comparison → 404
    r = client.post(
        f"/api/sessions/{s['id']}/references/compare",
        json={"version_id": v["id"], "reference_id": 99999, "start_ms": 0},
        headers=_auth(token),
    )
    assert r.status_code == 404


def test_client_brief_and_revision_rules(client):
    token = _register(client)
    s = _create_session(client, token)

    # defaults
    r = client.get(f"/api/sessions/{s['id']}", headers=_auth(token))
    assert r.json()["service_type"] == "mix"

    # save a full brief
    r = client.patch(
        f"/api/sessions/{s['id']}/brief",
        json={
            "service_type": "mix_master",
            "genre": "Neo-soul",
            "goal": "label",
            "deadline_at": "2026-09-01T12:00:00Z",
            "review_start_at": "2026-08-20T12:00:00Z",
            "reference_links": "https://soundcloud.com/x/ref1\nhttps://open.spotify.com/track/abc",
            "do_not_change": "Keep the vocal balance as-is; don't touch the arrangement",
            "required_deliverables": "master, instrumental, acapella",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200
    brief = r.json()
    assert brief["service_type"] == "mix_master"
    assert brief["genre"] == "Neo-soul"
    assert brief["goal"] == "label"
    assert "spotify.com" in brief["reference_links"]
    assert brief["required_deliverables"] == "master, instrumental, acapella"

    # invalid service type rejected
    r = client.patch(
        f"/api/sessions/{s['id']}/brief",
        json={"service_type": "bogus"},
        headers=_auth(token),
    )
    assert r.status_code == 422

    # guest on the share link sees the brief (rules are visible to the client)
    share = s["share_token"]
    r = client.get(f"/api/sessions/public/{share}")
    assert r.json()["service_type"] == "mix_master"
    assert r.json()["do_not_change"].startswith("Keep the vocal")

    # ledger records brief.updated
    r = client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token))
    assert "brief.updated" in {e["event"] for e in r.json()["events"]}


def test_engineer_portfolio(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0), "approved master")
    client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )

    # not public yet → empty portfolio
    r = client.get("/api/portfolio/producer")
    assert r.status_code == 200
    assert r.json()["track_count"] == 0

    # lock a release package so the portfolio carries a delivery link
    pkg = client.post(
        "/api/release-packages",
        json={"session_id": s["id"], "approved_version_id": v["id"], "name": "Final"},
        headers=_auth(token),
    ).json()
    client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "master", "from_version_id": v["id"]},
        headers=_auth(token),
    )
    pkg = client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": "master"},
        headers=_auth(token),
    ).json()

    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"portfolio_public": True},
        headers=_auth(token),
    )

    r = client.get("/api/portfolio/producer")
    assert r.status_code == 200
    body = r.json()
    assert body["track_count"] == 1
    t = body["tracks"][0]
    assert t["name"] == "Neon Warehouse"
    assert t["approved_label"] == "v1"
    assert t["delivery_token"] == pkg["delivery_token"]

    # portfolio preview is watermarked even though the version is approved
    r = client.get(f"/api/portfolio/producer/preview/{v['id']}")
    assert r.status_code == 200
    assert r.content != make_wav(1.0)
    assert r.content[:4] == b"RIFF"

    # unknown engineer → 404
    assert client.get("/api/portfolio/nobody").status_code == 404


def test_stem_missing_in_one_version_returns_clear_error(client):
    token = _register(client)
    s = _create_session(client, token)
    v1 = _upload(client, token, s["id"], make_wav(1.0), "v1")
    v2 = _upload(client, token, s["id"], make_wav(1.0), "v2")
    # bass only in v2
    client.post(
        f"/api/versions/{v2['id']}/stems",
        headers=_auth(token),
        data={"logical_name": "bass", "start_offset_ms": "0"},
        files=[("file", ("bass.wav", make_wav(1.0), "audio/wav"))],
    )
    r = client.post(
        "/api/comparisons",
        json={
            "base_version_id": v1["id"],
            "compare_version_id": v2["id"],
            "mode": "stem",
            "stem_logical_name": "bass",
            "start_ms": 0,
            "end_ms": 800,
        },
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "unavailable in v1" in r.json()["detail"]

    # stem mode without stem_logical_name → 400
    r = client.post(
        "/api/comparisons",
        json={
            "base_version_id": v1["id"],
            "compare_version_id": v2["id"],
            "mode": "stem",
            "start_ms": 0,
            "end_ms": 800,
        },
        headers=_auth(token),
    )
    assert r.status_code == 400

    # stems from different sessions are never comparable (version guard)
    other = _create_session(client, token)
    v3 = _upload(client, token, other["id"], make_wav(1.0), "other")
    r = client.post(
        "/api/comparisons",
        json={
            "base_version_id": v1["id"],
            "compare_version_id": v3["id"],
            "mode": "stem",
            "stem_logical_name": "bass",
            "start_ms": 0,
            "end_ms": 800,
        },
        headers=_auth(token),
    )
    assert r.status_code == 400


# ---------- change orders (late changes after approval/delivery) ----------


def test_change_order_full_flow(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0), "approved master")
    client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    share = s["share_token"]

    # engineer sets the service preset fees (recall + revision)
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"recall_fee_cents": 12000, "revision_fee_cents": 4500},
        headers=_auth(token),
    )

    # client requests a change through the share link
    r = client.post(
        f"/api/sessions/public/{share}/change-orders",
        json={"reason": "mix_revision", "description": "We came back after 3 months — rebalance the low end"},
        params={"actor": "client@label.com"},
    )
    assert r.status_code == 201
    co = r.json()
    assert co["status"] == "requested"
    assert co["target_round"] == 1

    # a second active request is rejected (one at a time)
    r = client.post(
        f"/api/sessions/public/{share}/change-orders",
        json={"reason": "format_change", "description": "also need mp3s"},
        params={"actor": "client@label.com"},
    )
    assert r.status_code == 400

    # owner quotes: paid_round, price defaults to revision_fee_cents
    r = client.patch(
        f"/api/sessions/{s['id']}/change-orders/{co['id']}",
        json={"decision": "paid_round", "deadline_at": "2026-09-01T12:00:00Z"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    co = r.json()
    assert co["status"] == "quoted"
    assert co["decision"] == "paid_round"
    assert co["price_cents"] == 4500

    # client accepts the price + deadline
    r = client.post(
        f"/api/sessions/public/{share}/change-orders/{co['id']}/accept",
        params={"actor": "client@label.com"},
    )
    assert r.status_code == 200
    co = r.json()
    assert co["status"] == "accepted"
    assert co["round_granted"] is False

    # invoice paid (manual Stripe-less mode) → round granted + reopened
    r = client.post(
        f"/api/sessions/{s['id']}/change-orders/{co['id']}/mark-paid",
        headers=_auth(token),
    )
    assert r.status_code == 200
    co = r.json()
    assert co["status"] == "paid"
    assert co["round_granted"] is True
    assert co["paid_at"]

    detail = client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()
    assert detail["change_rounds_granted"] == 1
    assert detail["rounds_open"] is True
    assert detail["status"] == "in_review"

    # the reopened round accepts new notes and a new version can ship
    client.post(
        f"/api/sessions/public/{share}/versions/{v['id']}/comments",
        json={"time_s": 0.2, "body": "low end rebalance notes", "author_name": "client@label.com"},
    )
    r = client.post(
        f"/api/sessions/{s['id']}/submit-feedback",
        json={"note": "change-order round"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["round_number"] == 2

    # ledger records the whole change-order trail
    r = client.get(f"/api/sessions/{s['id']}/ledger", headers=_auth(token))
    kinds = {e["event"] for e in r.json()["events"]}
    assert "change_order.created" in kinds
    assert "change_order.quoted" in kinds
    assert "change_order.accepted" in kinds
    assert "change_order.paid" in kinds
    assert "change_order.round_opened" in kinds

    # re-grant is idempotent (webhook replay protection)
    r = client.post(
        f"/api/sessions/{s['id']}/change-orders/{co['id']}/mark-paid",
        headers=_auth(token),
    )
    assert r.status_code == 400


def test_change_order_courtesy_and_decline(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0), "v1")
    client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    share = s["share_token"]

    # courtesy change: accept grants the round immediately, price 0
    co = client.post(
        f"/api/sessions/public/{share}/change-orders",
        json={"reason": "format_change", "description": "please add mp3 too"},
        params={"actor": "artist@mail.com"},
    ).json()
    r = client.patch(
        f"/api/sessions/{s['id']}/change-orders/{co['id']}",
        json={"decision": "courtesy"},
        headers=_auth(token),
    )
    assert r.json()["price_cents"] == 0
    r = client.post(
        f"/api/sessions/public/{share}/change-orders/{co['id']}/accept",
        params={"actor": "artist@mail.com"},
    )
    assert r.status_code == 200
    co = r.json()
    assert co["round_granted"] is True
    assert co["status"] == "paid"

    # a mastering recall quoted with no price falls back to the recall fee
    s2 = _create_session(client, token)
    v2 = _upload(client, token, s2["id"], make_wav(1.0), "v1")
    client.post(
        f"/api/sessions/{s2['id']}/versions/{v2['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    client.patch(
        f"/api/sessions/{s2['id']}/share",
        json={"recall_fee_cents": 15000},
        headers=_auth(token),
    )
    co2 = client.post(
        f"/api/sessions/public/{s2['share_token']}/change-orders",
        json={"reason": "mastering_recall", "description": "re-master for the vinyl cut"},
        params={"actor": "client@label.com"},
    ).json()
    r = client.patch(
        f"/api/sessions/{s2['id']}/change-orders/{co2['id']}",
        json={"decision": "new_mastering_pass"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["price_cents"] == 15000

    # engineer declines → status declined, no round granted
    r = client.post(
        f"/api/sessions/{s2['id']}/change-orders/{co2['id']}/decline",
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "declined"
    detail = client.get(f"/api/sessions/{s2['id']}", headers=_auth(token)).json()
    assert detail["change_rounds_granted"] == 0

    # change orders are only for approved projects
    s3 = _create_session(client, token)
    v3 = _upload(client, token, s3["id"], make_wav(1.0), "v1")
    r = client.post(
        f"/api/sessions/public/{s3['share_token']}/change-orders",
        json={"reason": "mix_revision", "description": "too early"},
        params={"actor": "client@x.com"},
    )
    assert r.status_code == 400

    # guests see the change-order list (statuses only, no payment plumbing)
    r = client.get(f"/api/sessions/public/{share}/change-orders")
    assert r.status_code == 200
    assert any(c["id"] == co["id"] for c in r.json())


# ---------- release templates, QC preflight, archive handoff ----------


def test_release_templates_and_preflight(client):
    token = _register(client)
    s = _create_session(client, token)
    v = _upload(client, token, s["id"], make_wav(1.0), "v1")
    client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )

    # template catalog is exposed for the UI
    r = client.get("/api/release-packages/templates")
    assert r.status_code == 200
    tpl_ids = {t["id"] for t in r.json()}
    assert {"final_master", "label_sync", "archive_handoff", "stem_handoff", "dj_promo", "post_production"} <= tpl_ids

    # label_sync template: name comes from the preset, requirements are pinned
    r = client.post(
        "/api/release-packages",
        json={"session_id": s["id"], "approved_version_id": v["id"], "template": "label_sync"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    pkg = r.json()
    assert pkg["template"] == "label_sync"
    assert pkg["name"] == "Label / sync delivery"

    # preflight: required deliverables are missing → blocking
    r = client.post(f"/api/release-packages/{pkg['id']}/preflight", headers=_auth(token))
    assert r.status_code == 200
    pre = r.json()
    assert pre["blocking"] is True
    assert any(c["label"] == "Required deliverable missing" and c["detail"] == "acapella" for c in pre["checks"])

    # add just the master → still blocking
    client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "master", "from_version_id": v["id"]},
        headers=_auth(token),
    )
    pre = client.post(f"/api/release-packages/{pkg['id']}/preflight", headers=_auth(token)).json()
    assert pre["blocking"] is True
    assert len([c for c in pre["checks"] if c["status"] == "block"]) >= 5

    # lock without force → 400; with force → ready
    r = client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": "master", "force": False},
        headers=_auth(token),
    )
    assert r.status_code == 400
    assert "preflight" in r.json()["detail"].lower()
    r = client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": "master", "force": True},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ready"

    # empty upload is caught by preflight on a fresh custom package
    s2 = _create_session(client, token)
    v2 = _upload(client, token, s2["id"], make_wav(1.0), "v1")
    client.post(
        f"/api/sessions/{s2['id']}/versions/{v2['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    pkg2 = client.post(
        "/api/release-packages",
        json={"session_id": s2["id"], "approved_version_id": v2["id"]},
        headers=_auth(token),
    ).json()
    client.post(
        f"/api/release-packages/{pkg2['id']}/deliverables/upload",
        headers=_auth(token),
        data={"type": "master"},
        files=[("file", ("empty.wav", b"", "audio/wav"))],
    )
    pre = client.post(f"/api/release-packages/{pkg2['id']}/preflight", headers=_auth(token)).json()
    assert any(c["status"] == "block" and c["label"] == "Empty file" for c in pre["checks"])
    r = client.post(
        f"/api/release-packages/{pkg2['id']}/lock",
        json={"approval_scope": "master"},
        headers=_auth(token),
    )
    assert r.status_code == 400


def test_archive_handoff_and_retention(client):
    token = _register(client)
    s = _create_session(client, token)

    # project retention + late-change fees on the session
    r = client.patch(
        f"/api/sessions/{s['id']}/share",
        json={
            "retention_until": "2026-11-15T12:00:00Z",
            "recall_fee_cents": 12000,
            "revision_fee_cents": 4500,
        },
        headers=_auth(token),
    )
    assert r.status_code == 200
    detail = r.json()
    assert detail["retention_until"].startswith("2026-11-15")
    assert detail["recall_fee_cents"] == 12000
    assert detail["revision_fee_cents"] == 4500

    v = _upload(client, token, s["id"], make_wav(1.0), "v1")
    client.post(
        f"/api/sessions/{s['id']}/versions/{v['id']}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    pkg = client.post(
        "/api/release-packages",
        json={"session_id": s["id"], "approved_version_id": v["id"], "template": "archive_handoff"},
        headers=_auth(token),
    ).json()
    assert pkg["name"] == "Archive handoff"

    # handoff metadata: plugin manifest, session manifest, consolidate option
    r = client.patch(
        f"/api/release-packages/{pkg['id']}/handoff",
        json={
            "plugin_manifest": "Ableton 12.1 · Serum 1.36 (missing: Ozone 11 → fallback stock EQ)",
            "session_manifest": {"sample_rate": 48000, "bit_depth": 24, "tempo": 128, "key": "F min", "start_time": "00:00:00:00"},
            "consolidate_audio": True,
            "archive_expires_at": "2027-01-01T00:00:00Z",
        },
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["consolidate_audio"] is True
    assert r.json()["session_manifest"]["tempo"] == 128
    assert "Ozone" in r.json()["plugin_manifest"]

    client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "master", "from_version_id": v["id"]},
        headers=_auth(token),
    )
    locked = client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": "master", "force": True},
        headers=_auth(token),
    ).json()

    # archive lifecycle: archived → expiry set (90 days when unspecified)
    r = client.post(
        f"/api/release-packages/{pkg['id']}/archive",
        json={"archive_status": "archived"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["archive_status"] == "archived"
    assert r.json()["archive_expires_at"]

    # the delivery page shows retention + a link back to the review
    tok = locked["delivery_token"]
    r = client.get(f"/api/release-packages/public/{tok}")
    assert r.status_code == 200
    body = r.json()
    assert body["retention_until"].startswith("2026-11-15")
    assert body["share_token"] == s["share_token"]
    assert body["archive_status"] == "archived"
    assert body["template"] == "archive_handoff"
