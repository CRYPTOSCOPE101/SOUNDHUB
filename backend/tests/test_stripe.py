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


def test_session_checkout_deposit_and_extra_round(client, monkeypatch):
    from app.services import stripe_pay

    created = {}

    def fake_create(**kw):
        created.update(kw)
        return "cs_test_sess", "https://checkout.stripe.com/c/pay/cs_test_sess"

    monkeypatch.setattr(stripe_pay, "create_checkout_session", fake_create)
    token = _register(client)
    s = client.post("/api/sessions", json={"name": "Deposit session"}, headers=_auth(token)).json()

    # deposit checkout (owner)
    client.patch(f"/api/sessions/{s['id']}/share", json={"deposit_due_cents": 5000}, headers=_auth(token))
    r = client.post(f"/api/sessions/{s['id']}/checkout", data={"kind": "deposit"}, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["amount_due_cents"] == 5000
    assert created["metadata"] == {"kind": "deposit"}

    # public checkout by share token (client without account)
    share = client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()["share_token"]
    r = client.post(
        f"/api/sessions/public/{share}/checkout",
        data={"kind": "deposit", "success_url": "https://soundhub.app/r/x?paid=1"},
    )
    assert r.status_code == 200
    assert r.json()["amount_due_cents"] == 5000

    # webhook marks the deposit paid
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_sess",
                "metadata": {"session_id": str(s["id"]), "kind": "deposit", "package_id": "0"},
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
    detail = client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()
    assert detail["deposit_status"] == "paid"

    # extra-round checkout + webhook increments rounds_paid
    client.patch(
        f"/api/sessions/{s['id']}/share",
        json={"extra_round_price_cents": 2500},
        headers=_auth(token),
    )
    r = client.post(f"/api/sessions/{s['id']}/checkout", data={"kind": "extra_round"}, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["amount_due_cents"] == 2500

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_x",
                "metadata": {"session_id": str(s["id"]), "kind": "extra_round", "package_id": "0"},
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
    detail = client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()
    assert detail["rounds_paid"] == 1

    # deposit checkout without a due deposit → 400
    s2 = client.post("/api/sessions", json={"name": "No deposit"}, headers=_auth(token)).json()
    r = client.post(f"/api/sessions/{s2['id']}/checkout", data={"kind": "deposit"}, headers=_auth(token))
    assert r.status_code == 400


def test_webhook_change_order_grants_round(client, monkeypatch):
    """Stripe webhook for kind=change_order marks the order paid + reopens the round."""
    from app.services import stripe_pay

    token = _register(client)
    s = client.post("/api/sessions", json={"name": "Change order session"}, headers=_auth(token)).json()
    r = client.post(
        f"/api/sessions/{s['id']}/versions",
        headers=_auth(token),
        data={"message": "v1"},
        files=[("file", ("v1.wav", make_wav(1.0), "audio/wav"))],
    )
    vid = r.json()["id"]
    client.post(
        f"/api/sessions/{s['id']}/versions/{vid}/status",
        json={"status": "approved"},
        headers=_auth(token),
    )
    share = client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()["share_token"]

    co = client.post(
        f"/api/sessions/public/{share}/change-orders",
        json={"reason": "mix_revision", "description": "rebalance"},
        params={"actor": "client@x.com"},
    ).json()
    client.patch(
        f"/api/sessions/{s['id']}/change-orders/{co['id']}",
        json={"decision": "paid_round", "price_cents": 4500},
        headers=_auth(token),
    )
    client.post(
        f"/api/sessions/public/{share}/change-orders/{co['id']}/accept",
        params={"actor": "client@x.com"},
    )

    # the webhook pays it (metadata kind=change_order)
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_co",
                "metadata": {
                    "kind": "change_order",
                    "change_order_id": str(co["id"]),
                    "session_id": str(s["id"]),
                    "package_id": "0",
                },
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

    detail = client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()
    assert detail["change_rounds_granted"] == 1
    assert detail["rounds_open"] is True

    # replay is a no-op — the round is granted exactly once
    r = client.post(
        "/api/release-packages/webhooks/stripe",
        content=body,
        headers={"stripe-signature": sig},
    )
    assert r.status_code == 200
    assert r.json()["handled"] is False
    assert client.get(f"/api/sessions/{s['id']}", headers=_auth(token)).json()["change_rounds_granted"] == 1
