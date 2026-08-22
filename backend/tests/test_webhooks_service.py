import hashlib
import hmac
import json
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base  # noqa: E402
from app.models import User, Webhook, WebhookDelivery  # noqa: E402
from app.services import webhooks  # noqa: E402


class _Response:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class _Client:
    calls = []
    response = _Response(200, "ok")
    error = None

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, content, headers):
        self.calls.append((url, content, headers))
        if self.error:
            raise self.error
        return self.response


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _webhook(db, **kwargs):
    user = User(username=f"user-{id(kwargs)}", password_hash="hash")
    db.add(user)
    db.flush()
    hook = Webhook(owner_id=user.id, url="https://example.test/hook", **kwargs)
    db.add(hook)
    db.commit()
    return hook


def test_dispatch_filters_inactive_and_event_subscriptions(monkeypatch):
    db = _session()
    active = _webhook(db, events=" push, review ")
    wildcard = _webhook(db, events="*")
    inactive = _webhook(db, events="push", is_active=False)
    _Client.calls = []
    _Client.response = _Response(204, "")
    _Client.error = None
    monkeypatch.setattr(webhooks.httpx, "Client", _Client)

    webhooks.dispatch(db, "review", {"id": 1})

    assert len(_Client.calls) == 2
    deliveries = db.query(WebhookDelivery).all()
    assert {delivery.webhook_id for delivery in deliveries} == {active.id, wildcard.id}
    assert inactive.id not in {delivery.webhook_id for delivery in deliveries}


def test_dispatch_signs_exact_body_and_records_success(monkeypatch):
    db = _session()
    hook = _webhook(db, secret="secret", events="*")
    _Client.calls = []
    _Client.response = _Response(201, "created")
    _Client.error = None
    monkeypatch.setattr(webhooks.httpx, "Client", _Client)

    payload = {"name": "mix", "number": 2}
    webhooks.dispatch(db, "version.created", payload)

    url, body, headers = _Client.calls[0]
    assert url == hook.url
    assert json.loads(body) == {"event": "version.created", "payload": payload}
    expected = hmac.new(b"secret", body.encode(), hashlib.sha256).hexdigest()
    assert headers["X-Signature-256"] == f"sha256={expected}"
    delivery = db.query(WebhookDelivery).one()
    db.refresh(hook)
    assert delivery.success is True
    assert delivery.status_code == 201
    assert delivery.response_body == "created"
    assert delivery.duration_ms is not None
    assert hook.last_status == 201
    assert hook.last_error == ""
    assert hook.last_triggered_at is not None


def test_dispatch_omits_signature_without_secret(monkeypatch):
    db = _session()
    _webhook(db, secret=None)
    _Client.calls = []
    _Client.response = _Response(200, "ok")
    _Client.error = None
    monkeypatch.setattr(webhooks.httpx, "Client", _Client)

    webhooks.dispatch(db, "ping", {})

    assert "X-Signature-256" not in _Client.calls[0][2]


def test_dispatch_records_non_2xx_and_truncates_error(monkeypatch):
    db = _session()
    hook = _webhook(db, secret=None)
    response_text = "x" * 2400
    _Client.calls = []
    _Client.response = _Response(500, response_text)
    _Client.error = None
    monkeypatch.setattr(webhooks.httpx, "Client", _Client)

    webhooks.dispatch(db, "failed", {})

    delivery = db.query(WebhookDelivery).one()
    db.refresh(hook)
    assert delivery.success is False
    assert delivery.status_code == 500
    assert len(delivery.response_body) == 2000
    assert hook.last_status == 500
    assert hook.last_error == response_text[:500]


def test_dispatch_records_transport_exception(monkeypatch):
    db = _session()
    hook = _webhook(db)
    _Client.calls = []
    _Client.error = RuntimeError("connection refused")
    monkeypatch.setattr(webhooks.httpx, "Client", _Client)

    webhooks.dispatch(db, "failed", {})

    delivery = db.query(WebhookDelivery).one()
    db.refresh(hook)
    assert delivery.status_code is None
    assert delivery.success is False
    assert delivery.response_body == "connection refused"
    assert hook.last_status is None
    assert hook.last_error == "connection refused"
