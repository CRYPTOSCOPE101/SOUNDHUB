"""USDC checkout on Base — terms, on-chain transfer verification, idempotency.

The RPC layer is mocked (no live Base node in CI); the receipt structure is
the real JSON-RPC shape. Transfer logs must match the payee wallet and cover
the invoice amount before the invoice flips to paid.
"""

import io
import json
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
    monkeypatch.setattr(config, "BASE_RPC_URL", "https://mainnet.base.org")
    monkeypatch.setattr(config, "USDC_FALLBACK_PAYEE", "")
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


TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _topic_address(addr: str) -> str:
    return "0x" + addr[2:].lower().rjust(64, "0")


def _usdc_receipt(payee: str, value_units: int, token: str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"):
    """A receipt with one USDC Transfer log paying `payee` `value_units`."""
    return {
        "transactionHash": "0x" + "ab" * 32,
        "blockNumber": "0x10",
        "logs": [
            {
                "address": token.lower(),
                "topics": [TRANSFER_TOPIC, _topic_address("0x" + "11" * 20), _topic_address(payee)],
                "data": hex(value_units),
            }
        ],
    }


def _locked_package(client, token, wallet_address: str | None = None, amount_cents: int = 4900):
    """Create a session, approve v1, build + lock a package with an invoice."""
    if wallet_address is not None:
        from app.database import SessionLocal
        from app.models import User

        with SessionLocal() as db:
            u = db.query(User).filter(User.username == "producer").first()
            u.wallet_address = wallet_address
            db.add(u)
            db.commit()

    r = client.post("/api/sessions", json={"name": "Neon"}, headers=_auth(token))
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
    locked = r.json()
    pkg["delivery_token"] = locked["delivery_token"]
    client.patch(
        f"/api/release-packages/{pkg['id']}/invoice",
        json={"invoice_status": "balance_due", "amount_due_cents": amount_cents, "currency": "usd"},
        headers=_auth(token),
    )
    return pkg


def test_usdc_terms_return_payment_info(client, monkeypatch):
    """Terms give the client everything needed to send USDC from their wallet."""
    token = _register(client)
    payee = "0x" + "aa" * 20
    pkg = _locked_package(client, token, wallet_address=payee, amount_cents=4900)

    r = client.post(f"/api/release-packages/{pkg['id']}/checkout/usdc", headers=_auth(token))
    assert r.status_code == 200, r.text
    terms = r.json()
    assert terms["network"] == "base"
    assert terms["chain_id"] == 8453
    assert terms["token_address"].startswith("0x")
    assert terms["payee_address"].lower() == payee.lower()
    assert terms["amount_usdc_units"] == 4900 * 10**4  # $49.00
    assert terms["amount_usdc"] == 49.0
    assert terms["decimals"] == 6
    assert terms["purpose"] == "release package invoice"

    # public delivery link terms (client, no account)
    tok = pkg["delivery_token"]
    r = client.post(f"/api/release-packages/public/{tok}/checkout/usdc")
    assert r.status_code == 200, r.text
    assert r.json()["payee_address"].lower() == payee.lower()


def test_usdc_terms_require_wallet_and_config(client, monkeypatch):
    token = _register(client)
    pkg = _locked_package(client, token, wallet_address=None, amount_cents=4900)

    # no wallet linked on the engineer → clear error
    r = client.post(f"/api/release-packages/{pkg['id']}/checkout/usdc", headers=_auth(token))
    assert r.status_code == 400
    assert "no wallet" in r.json()["detail"]

    # disabled config → 503
    from app import config

    monkeypatch.setattr(config, "BASE_RPC_URL", "")
    from app.database import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        u = db.query(User).filter(User.username == "producer").first()
        u.wallet_address = "0x" + "bb" * 20
        db.add(u)
        db.commit()
    r = client.post(f"/api/release-packages/{pkg['id']}/checkout/usdc", headers=_auth(token))
    assert r.status_code == 503


def test_usdc_verify_marks_invoice_paid(client, monkeypatch):
    token = _register(client)
    payee = "0x" + "cc" * 20
    pkg = _locked_package(client, token, wallet_address=payee, amount_cents=4900)
    tx_hash = "0x" + "dd" * 32

    import app.services.usdc_pay as usdc_pay

    monkeypatch.setattr(
        usdc_pay,
        "get_transaction_receipt",
        lambda h: _usdc_receipt(payee, 4900 * 10**4),
    )

    r = client.post(
        "/api/release-packages/webhooks/usdc",
        json={"tx_hash": tx_hash, "package_id": pkg["id"], "kind": "package"},
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["ok"] is True and res["handled"] is True
    assert res["transfer"]["value"] == 4900 * 10**4

    # invoice is now paid → downloads unlocked, idempotent re-verify
    r = client.post(
        "/api/release-packages/webhooks/usdc",
        json={"tx_hash": tx_hash, "package_id": pkg["id"], "kind": "package"},
    )
    assert r.status_code == 200
    assert r.json()["already_paid"] is True

    # list endpoint has the package with deliverables + paid invoice
    listing = client.get("/api/release-packages", headers=_auth(token)).json()
    pkg_out = next(p for p in listing if p["id"] == pkg["id"])
    assert pkg_out["invoice_status"] == "paid"
    did = pkg_out["deliverables"][0]["id"]
    durl = f"/api/release-packages/public/{pkg['delivery_token']}/files/{did}"
    r = client.get(durl)
    assert r.status_code == 200 and r.content[:4] == b"RIFF"

    # ledger carries the usdc payment
    ledger_events = client.get(
        f"/api/sessions/{pkg['session_id']}/ledger", headers=_auth(token)
    ).json()["events"]
    paid = [e for e in ledger_events if e["event"] == "invoice.paid"]
    assert paid and paid[0]["payload"]["method"] == "usdc"
    assert paid[0]["payload"]["tx_hash"] == tx_hash


def test_usdc_verify_rejects_wrong_amount_and_payee(client, monkeypatch):
    token = _register(client)
    payee = "0x" + "ee" * 20
    pkg = _locked_package(client, token, wallet_address=payee, amount_cents=4900)

    import app.services.usdc_pay as usdc_pay

    # transfer to someone else → reject
    monkeypatch.setattr(
        usdc_pay,
        "get_transaction_receipt",
        lambda h: _usdc_receipt("0x" + "ff" * 20, 4900 * 10**4),
    )
    r = client.post(
        "/api/release-packages/webhooks/usdc",
        json={"tx_hash": "0x" + "11" * 32, "package_id": pkg["id"], "kind": "package"},
    )
    assert r.status_code == 400
    assert "No matching USDC transfer" in r.json()["detail"]
    # still not paid
    listing = client.get("/api/release-packages", headers=_auth(token)).json()
    pkg_out = next(p for p in listing if p["id"] == pkg["id"])
    assert pkg_out["invoice_status"] == "balance_due"

    # right payee but insufficient amount → reject
    monkeypatch.setattr(
        usdc_pay,
        "get_transaction_receipt",
        lambda h: _usdc_receipt(payee, 100),  # $0.0001
    )
    r = client.post(
        "/api/release-packages/webhooks/usdc",
        json={"tx_hash": "0x" + "22" * 32, "package_id": pkg["id"], "kind": "package"},
    )
    assert r.status_code == 400
    assert "No matching USDC transfer" in r.json()["detail"]

    # tx not found on chain
    monkeypatch.setattr(usdc_pay, "get_transaction_receipt", lambda h: None)
    r = client.post(
        "/api/release-packages/webhooks/usdc",
        json={"tx_hash": "0x" + "33" * 32, "package_id": pkg["id"], "kind": "package"},
    )
    assert r.status_code == 400
    assert "not found on chain" in r.json()["detail"]


def test_usdc_verify_by_delivery_token(client, monkeypatch):
    """The public delivery page verifies by delivery token (no package id)."""
    token = _register(client)
    payee = "0x" + "9b" * 20
    pkg = _locked_package(client, token, wallet_address=payee, amount_cents=4900)

    import app.services.usdc_pay as usdc_pay

    monkeypatch.setattr(
        usdc_pay,
        "get_transaction_receipt",
        lambda h: _usdc_receipt(payee, 4900 * 10**4),
    )
    r = client.post(
        "/api/release-packages/webhooks/usdc",
        json={"tx_hash": "0x" + "cd" * 32, "delivery_token": pkg["delivery_token"], "kind": "package"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["handled"] is True
    assert r.json()["transfer"]["value"] == 4900 * 10**4

    # unknown token → not handled, no error
    r = client.post(
        "/api/release-packages/webhooks/usdc",
        json={"tx_hash": "0x" + "ef" * 32, "delivery_token": "nope", "kind": "package"},
    )
    assert r.status_code == 200
    assert r.json()["handled"] is False


def test_usdc_deposit_and_extra_round(client, monkeypatch):
    """kind=deposit and kind=extra_round work through the same verifier."""
    token = _register(client)
    payee = "0x" + "12" * 20
    r = client.post("/api/sessions", json={"name": "Neon"}, headers=_auth(token))
    sid = r.json()["id"]

    from app.database import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        u = db.query(User).filter(User.username == "producer").first()
        u.wallet_address = payee
        db.add(u)
        db.commit()

    client.patch(
        f"/api/sessions/{sid}/share",
        json={"deposit_due_cents": 5000, "deposit_status": "deposit_due", "extra_round_price_cents": 2500},
        headers=_auth(token),
    )

    import app.services.usdc_pay as usdc_pay

    monkeypatch.setattr(
        usdc_pay,
        "get_transaction_receipt",
        lambda h: _usdc_receipt(payee, 5000 * 10**4),
    )
    r = client.post(
        "/api/release-packages/webhooks/usdc",
        json={"tx_hash": "0x" + "77" * 32, "session_id": sid, "kind": "deposit"},
    )
    assert r.status_code == 200 and r.json()["handled"] is True
    session = client.get(f"/api/sessions/{sid}", headers=_auth(token)).json()
    assert session["deposit_status"] == "paid"

    monkeypatch.setattr(
        usdc_pay,
        "get_transaction_receipt",
        lambda h: _usdc_receipt(payee, 2500 * 10**4),
    )
    r = client.post(
        "/api/release-packages/webhooks/usdc",
        json={"tx_hash": "0x" + "88" * 32, "session_id": sid, "kind": "extra_round"},
    )
    assert r.status_code == 200 and r.json()["handled"] is True
    session = client.get(f"/api/sessions/{sid}", headers=_auth(token)).json()
    assert session["rounds_paid"] == 1
