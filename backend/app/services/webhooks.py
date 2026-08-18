"""Webhook system — notify external services on events."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import Webhook, WebhookDelivery


def create_webhook(
    db: DbSession,
    owner_id: int,
    *,
    url: str,
    events: str = "*",
    secret: str | None = None,
) -> Webhook:
    wh = Webhook(owner_id=owner_id, url=url, events=events, secret=secret)
    db.add(wh)
    db.flush()
    return wh


def list_webhooks(db: DbSession, owner_id: int) -> list[Webhook]:
    return list(
        db.scalars(
            select(Webhook).where(Webhook.owner_id == owner_id).order_by(Webhook.id)
        ).all()
    )


def get_webhook(db: DbSession, webhook_id: int) -> Webhook | None:
    return db.get(Webhook, webhook_id)


def delete_webhook(db: DbSession, webhook: Webhook) -> None:
    db.query(WebhookDelivery).filter(WebhookDelivery.webhook_id == webhook.id).delete()
    db.delete(webhook)
    db.flush()


def update_webhook(db: DbSession, webhook: Webhook, **fields) -> Webhook:
    for k, v in fields.items():
        if hasattr(webhook, k) and v is not None:
            setattr(webhook, k, v)
    db.flush()
    return webhook


def sign_payload(payload: dict, secret: str) -> str:
    """HMAC-SHA256 signature for webhook payload."""
    body = json.dumps(payload, sort_keys=True, default=str).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def trigger_webhooks(
    db: DbSession,
    event_type: str,
    payload: dict,
    owner_id: int | None = None,
) -> list[WebhookDelivery]:
    """Find matching webhooks and deliver the event."""
    q = select(Webhook).where(Webhook.is_active.is_(True))
    if owner_id is not None:
        q = q.where(Webhook.owner_id == owner_id)
    webhooks = list(db.scalars(q).all())

    deliveries: list[WebhookDelivery] = []
    for wh in webhooks:
        # check if webhook subscribes to this event
        subscribed_events = [e.strip() for e in wh.events.split(",")]
        if "*" not in subscribed_events and event_type not in subscribed_events:
            continue

        body = json.dumps(payload, default=str).encode()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if wh.secret:
            headers["X-Signature"] = sign_payload(payload, wh.secret)
        headers["X-Event-Type"] = event_type

        req = urllib.request.Request(wh.url, data=body, headers=headers, method="POST")
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                resp_body = resp.read().decode(errors="replace")[:2000]
                success = 200 <= status < 300
        except Exception as exc:
            status = 0
            resp_body = str(exc)[:2000]
            success = False
        duration_ms = int((time.monotonic() - t0) * 1000)

        delivery = WebhookDelivery(
            webhook_id=wh.id,
            event_type=event_type,
            payload=payload,
            status_code=status,
            response_body=resp_body,
            success=success,
            duration_ms=duration_ms,
        )
        db.add(delivery)
        wh.last_status = status
        wh.last_error = "" if success else resp_body
        wh.last_triggered_at = datetime.now(timezone.utc)
        deliveries.append(delivery)

    if deliveries:
        db.flush()
    return deliveries


def get_delivery_history(
    db: DbSession, webhook_id: int, limit: int = 20
) -> list[WebhookDelivery]:
    return list(
        db.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(WebhookDelivery.id.desc())
            .limit(limit)
        ).all()
    )
