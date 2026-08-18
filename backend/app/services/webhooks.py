"""HTTP webhook dispatching with HMAC signing."""
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from ..models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)


def dispatch(db: Session, event_type: str, payload: dict) -> None:
    """Dispatch an event to all matching active webhooks."""
    webhooks = db.query(Webhook).filter(Webhook.is_active == True).all()

    for wh in webhooks:
        # Check if this webhook subscribes to this event
        if wh.events != "*":
            subscribed = [e.strip() for e in wh.events.split(",")]
            if event_type not in subscribed:
                continue

        _deliver(db, wh, event_type, payload)


def _deliver(db: Session, webhook: Webhook, event_type: str, payload: dict) -> None:
    """Deliver a webhook event."""
    body = json.dumps({"event": event_type, "payload": payload}, default=str)

    headers = {"Content-Type": "application/json"}
    if webhook.secret:
        sig = hmac.new(webhook.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-Signature-256"] = f"sha256={sig}"

    start = time.time()
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(webhook.url, content=body, headers=headers)
            duration_ms = int((time.time() - start) * 1000)

            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                event_type=event_type,
                payload=payload,
                status_code=resp.status_code,
                response_body=resp.text[:2000],
                success=200 <= resp.status_code < 300,
                duration_ms=duration_ms,
            )
            db.add(delivery)

            webhook.last_status = resp.status_code
            webhook.last_triggered_at = datetime.now(timezone.utc)
            if not delivery.success:
                webhook.last_error = resp.text[:500]
            else:
                webhook.last_error = ""
    except Exception as e:
        logger.warning("webhook %s delivery of %s failed: %s", webhook.id, event_type, e, exc_info=True)
        duration_ms = int((time.time() - start) * 1000)
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=event_type,
            payload=payload,
            status_code=None,
            response_body=str(e)[:2000],
            success=False,
            duration_ms=duration_ms,
        )
        db.add(delivery)
        webhook.last_status = None
        webhook.last_error = str(e)[:500]
        webhook.last_triggered_at = datetime.now(timezone.utc)

    db.commit()
