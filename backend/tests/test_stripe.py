"""Stripe paid delivery tests: checkout session creation + webhook verification."""

import hashlib
import hmac
import io
import json
import struct
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402

WEBHOOK_SECRET = "whsec_test_secret_123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import config, database
    from app.services import stripe_pay

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

    # Stripe enabled for tests
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(config, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(stripe_pay, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(stripe_pay, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)

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


def _locked_package(client, token) -> dict:
    """Session → approved version → locked release package → balance due."""
    r = client.post("/api/sessions", json={"name": "Neon Warehouse"}, headers=_auth(token))
    sid = r.json()["id"]
    r = client.post(
        f"/api/sessions/{sid}/versions",
        headers=_auth(token),
        data={"message": "v1"},
        files=[("file", ("v1.wav", make_wav(1.0), "audio/wav"))],
    )
    vid = r.json()["id"]
    r = client.post(
        f"/api/sessions/{sid}/versions/{vid}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    assert r.status_code == 200
    r = client.post(
        "/api/release-packages",
        json={"session_id": sid, "approved_version_id": vid, "name": "Final delivery"},
        headers=_auth(token),
    )
    pid = r.json()["id"]
    client.post(
        f"/api/release-packages/{pid}/deliverables/from-version",
        json={"type": "master", "from_version_id": vid},
        headers=_auth(token),
    )
    r = client.post(
        f"/api/release-packages/{pid}/lock",
        json={"approval_scope": "master", "note": "final"},
        headers=_auth(token),
    )
    pkg = r.json()
    client.patch(
        f"/api/release-packages/{pid}/invoice",
        json={"invoice_status": "balance_due", "amount_due_cents": 4900, "currency": "usd"},
        headers=_auth(token),
    )
    return pkg


def _signed_event(payload: dict, secret: str = WEBHOOK_SECRET) -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    ts = int(time.time())
    signed = f"{ts}.".encode() + body
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return body, f"t={ts},v1={sig}"


def test_checkout_requires_stripe_config(client, monkeypatch):
    from app import config
    from app.services import stripe_pay

    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(stripe_pay, "STRIPE_SECRET_KEY", "")
    token = _register(client)
    pkg = _locked_package(client, token)
    r = client.post(f"/api/release-packages/{pkg['id']}/checkout", headers=_auth(token))
    assert r.status_code == 503


def test_checkout_requires_amount(client, monkeypatch):
    token = _register(client)
    r = client.post("/api/sessions", json={"name": "S"}, headers=_auth(token))
    sid = r.json()["id"]
    r = client.post(
        f"/api/sessions/{sid}/versions",
        headers=_auth(token),
        data={"message": "v1"},
        files=[("file", ("v1.wav", make_wav(1.0), "audio/wav"))],
    )
    vid = r.json()["id"]
    client.post(
        f"/api/sessions/{sid}/versions/{vid}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    r = client.post(
        "/api/release-packages",
        json={"session_id": sid, "approved_version_id": vid},
        headers=_auth(token),
    )
    pid = r.json()["id"]
    client.post(
        f"/api/release-packages/{pid}/deliverables/from-version",
        json={"type": "master", "from_version_id": vid},
        headers=_auth(token),
    )
    client.post(
        f"/api/release-packages/{pid}/lock",
        json={"approval_scope": "master"},
        headers=_auth(token),
    )
    # amount set but invoice status still 'none' → nothing to charge
    client.patch(
        f"/api/release-packages/{pid}/invoice",
        json={"invoice_status": "none", "amount_due_cents": 4900},
        headers=_auth(token),
    )
    r = client.post(f"/api/release-packages/{pid}/checkout", headers=_auth(token))
    assert r.status_code == 400


def test_checkout_creates_session(client, monkeypatch):
    from app.services import stripe_pay

    created = {}

    def fake_create(**kw):
        created.update(kw)
        return "cs_test_abc", "https://checkout.stripe.com/c/pay/cs_test_abc"

    monkeypatch.setattr(stripe_pay, "create_checkout_session", fake_create)
    token = _register(client)
    pkg = _locked_package(client, token)
    r = client.post(f"/api/release-packages/{pkg['id']}/checkout", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_abc"
    assert body["session_id"] == "cs_test_abc"
    assert body["amount_due_cents"] == 4900
    assert created["amount_cents"] == 4900
    assert created["package_id"] == pkg["id"]

    # public checkout by delivery token (client without account)
    tok = pkg["delivery_token"]
    r = client.post(
        f"/api/release-packages/public/{tok}/checkout",
        data={"success_url": "https://soundhub.app/d/x?paid=1", "cancel_url": "https://soundhub.app/d/x"},
    )
    assert r.status_code == 200
    assert r.json()["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_abc"


def test_webhook_invalid_signature_rejected(client):
    body = json.dumps({"type": "checkout.session.completed", "data": {"object": {}}}).encode()
    r = client.post(
        "/api/release-packages/webhooks/stripe",
        content=body,
        headers={"stripe-signature": "t=1,v1=bogus"},
    )
    assert r.status_code == 400


def test_webhook_marks_paid_and_unlocks(client):
    token = _register(client)
    pkg = _locked_package(client, token)
    did = pkg["deliverables"][0]["id"]
    tok = pkg["delivery_token"]

    # locked behind balance_due
    assert client.get(f"/api/release-packages/public/{tok}/files/{did}").status_code == 402

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_webhook",
                "metadata": {"package_id": str(pkg["id"])},
            }
        },
    }
    body, sig = _signed_event(event)
    r = client.post(
        "/api/release-packages/webhooks/stripe",
        content=body,
        headers={"stripe-signature": sig},
    )
    assert r.status_code == 200
    assert r.json()["handled"] is True

    # download unlocked
    assert client.get(f"/api/release-packages/public/{tok}/files/{did}").status_code == 200

    # ledger event recorded with method stripe
    r = client.get(f"/api/sessions/{pkg['session_id']}/ledger", headers=_auth(token))
    events = [e["event"] for e in r.json()["events"]]
    assert "invoice.paid" in events


def test_webhook_idempotent_replay(client):
    token = _register(client)
    pkg = _locked_package(client, token)
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_x", "metadata": {"package_id": str(pkg["id"])}}},
    }
    body, sig = _signed_event(event)
    for _ in range(2):
        r = client.post(
            "/api/release-packages/webhooks/stripe",
            content=body,
            headers={"stripe-signature": sig},
        )
        assert r.status_code == 200
    # only one invoice.paid event
    r = client.get(f"/api/sessions/{pkg['session_id']}/ledger", headers=_auth(token))
    paid = [e for e in r.json()["events"] if e["event"] == "invoice.paid"]
    assert len(paid) == 1


def test_webhook_unknown_package_noop(client):
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_test_zz", "metadata": {"package_id": "99999"}}},
    }
    body, sig = _signed_event(event)
    r = client.post(
        "/api/release-packages/webhooks/stripe",
        content=body,
        headers={"stripe-signature": sig},
    )
    assert r.status_code == 200
    assert r.json()["handled"] is False
