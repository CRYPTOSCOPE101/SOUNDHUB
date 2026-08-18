"""HTTP webhook dispatching with HMAC signing."""
import hashlib
import hmac
import ipaddress
import json
import socket
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from ..models import Webhook, WebhookDelivery


def validate_url(url: str) -> str:
    """Reject webhook targets that point at non-public networks (SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Webhook URL must be an absolute http(s) URL")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError(f"Webhook host cannot be resolved: {parsed.hostname}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError("Webhook URL must not point at a private or loopback address")
    return url


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
