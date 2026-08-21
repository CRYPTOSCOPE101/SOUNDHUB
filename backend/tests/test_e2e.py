"""End-to-end smoke test — the full SoundHub journey in one pass.

This is the "can a client get from the share link to a paid download without
the engineer explaining anything" check. It exercises:

    public review → draft note → submit round → new version → approve
    → package (template) → QC preflight → lock → invoice → payment → download

Run with:  cd backend && .venv/bin/python -m pytest tests/test_e2e.py -q
(or `make e2e` / `make smoke`).
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


def test_full_review_to_paid_delivery_journey(client):
    # demo seed is up (the landing "Open a sample review" CTA target)
    r = client.get("/api/demo/review")
    assert r.status_code == 200
    assert r.json()["share_token"]

    # engineer registers and opens a session
    r = client.post("/api/auth/register", json={"username": "producer", "password": "secret1"})
    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/sessions", json={"name": "Neon Warehouse"}, headers=auth)
    sid = r.json()["id"]
    share = r.json()["share_token"]

    # brief + included rounds so the client knows the rules
    client.patch(
        f"/api/sessions/{sid}/brief",
        json={
            "service_type": "mix_master",
            "genre": "Neon warehouse",
            "goal": "label",
            "required_deliverables": "master, instrumental",
            "do_not_change": "Keep the vocal balance as-is",
        },
        headers=auth,
    )

    # v1 uploaded; guest leaves a draft note via the share link (no account)
    r = client.post(
        f"/api/sessions/{sid}/versions",
        headers=auth,
        data={"message": "v1"},
        files=[("file", ("v1.wav", make_wav(1.0), "audio/wav"))],
    )
    v1 = r.json()
    r = client.post(
        f"/api/sessions/public/{share}/versions/{v1['id']}/comments",
        json={"time_s": 0.4, "body": "Kick and bass clash at the drop", "author_name": "Aisha (A&R)"},
    )
    assert r.status_code == 201
    assert r.json()["status"] in ("draft", "open")

    # feedback owner submits the consolidated round
    r = client.post(
        f"/api/sessions/{sid}/submit-feedback",
        json={"note": "Consolidated A&R + artist notes"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["round_number"] == 2

    # v2 ships the fix; client approves it
    r = client.post(
        f"/api/sessions/{sid}/versions",
        headers=auth,
        data={"message": "v2 — bass revised"},
        files=[("file", ("v2.wav", make_wav(1.0), "audio/wav"))],
    )
    v2 = r.json()
    assert v2["round_number"] == 2
    r = client.post(
        f"/api/sessions/{sid}/versions/{v2['id']}/approvals",
        json={"scope": "master", "approved": True, "note": "", "approver_name": "Aisha (A&R)"},
        headers=auth,
    )
    assert r.status_code == 201

    # release package from the final_master template
    r = client.post(
        "/api/release-packages",
        json={"session_id": sid, "approved_version_id": v2["id"], "template": "final_master"},
        headers=auth,
    )
    pkg = r.json()
    client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/from-version",
        json={"type": "master", "from_version_id": v2["id"]},
        headers=auth,
    )
    # instrumental is a separate file (a real package never ships two identical blobs)
    instr = io.BytesIO()
    with wave.open(instr, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * 0.3)) for _ in range(8000)))
    client.post(
        f"/api/release-packages/{pkg['id']}/deliverables/upload",
        headers=auth,
        data={"type": "instrumental"},
        files=[("file", ("instrumental.wav", instr.getvalue(), "audio/wav"))],
    )

    # QC preflight passes → lock opens the delivery link
    pre = client.post(f"/api/release-packages/{pkg['id']}/preflight", headers=auth).json()
    assert pre["passed"] is True
    r = client.post(
        f"/api/release-packages/{pkg['id']}/lock",
        json={"approval_scope": "master", "note": "final"},
        headers=auth,
    )
    pkg = r.json()
    assert pkg["status"] == "ready"
    tok = pkg["delivery_token"]

    # invoice: balance due → delivery is gated
    client.patch(
        f"/api/release-packages/{pkg['id']}/invoice",
        json={"invoice_status": "balance_due", "amount_due_cents": 4900, "currency": "usd"},
        headers=auth,
    )
    did = pkg["deliverables"][0]["id"]
    durl = f"/api/release-packages/public/{tok}/files/{did}"
    assert client.get(durl).status_code == 402

    # paid (manual Stripe-less mode) → client downloads the approved master
    client.patch(f"/api/release-packages/{pkg['id']}/invoice", json={"invoice_status": "paid"}, headers=auth)
    r = client.get(durl)
    assert r.status_code == 200
    assert r.content[:4] == b"RIFF"

    # ledger is intact end to end
    r = client.get(f"/api/sessions/{sid}/ledger/verify", headers=auth)
    assert r.json()["ok"] is True
    kinds = {e["event"] for e in client.get(f"/api/sessions/{sid}/ledger", headers=auth).json()["events"]}
    for expected in ("version.created", "round.submitted", "approval.created", "package.created", "package.locked", "invoice.paid"):
        assert expected in kinds, f"missing ledger event {expected}"
