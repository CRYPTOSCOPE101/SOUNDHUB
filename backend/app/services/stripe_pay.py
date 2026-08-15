"""Stripe Checkout for paid delivery — no SDK dependency.

We call the public Stripe REST API over httpx (already a project dependency)
and verify webhook signatures with the documented HMAC-SHA256 scheme
(`t=<ts>,v1=<sig>`). When STRIPE_SECRET_KEY is unset the service stays in
manual-invoice mode: checkout endpoints return 503 and the manual
"mark paid" flow is used instead.
"""

import base64
import hashlib
import hmac
import json
import time

import httpx

from ..config import (
    STRIPE_API_BASE,
    STRIPE_CURRENCY,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)

CHECKOUT_TIMEOUT = httpx.Timeout(30.0)


def enabled() -> bool:
    return bool(STRIPE_SECRET_KEY)


def create_checkout_session(
    *,
    amount_cents: int,
    currency: str,
    package_id: int,
    package_name: str,
    session_id: int,
    success_url: str,
    cancel_url: str,
    metadata: dict | None = None,
) -> tuple[str, str]:
    """Create a Checkout Session; returns (session_id, hosted_checkout_url)."""
    meta = {"package_id": str(package_id), "session_id": str(session_id)}
    if metadata:
        meta.update({k: str(v) for k, v in metadata.items()})
    resp = httpx.post(
        f"{STRIPE_API_BASE}/v1/checkout/sessions",
        headers={
            "Authorization": f"Bearer {STRIPE_SECRET_KEY}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": currency,
            "line_items[0][price_data][unit_amount]": str(amount_cents),
            "line_items[0][price_data][product_data][name]": package_name[:240],
            "metadata[package_id]": meta["package_id"],
            "metadata[session_id]": meta["session_id"],
        },
        timeout=CHECKOUT_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Stripe checkout failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return data["id"], data["url"]


def retrieve_checkout_session(session_id: str) -> dict:
    resp = httpx.get(
        f"{STRIPE_API_BASE}/v1/checkout/sessions/{session_id}",
        headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
        timeout=CHECKOUT_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Stripe retrieve failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def verify_webhook_signature(payload: bytes, sig_header: str, secret: str | None = None) -> dict:
    """Verify a Stripe-Signature header and return the parsed event.

    Implements Stripe's scheme: `t=<unix_ts>,v1=<hex_hmac_sha256>` where the
    signed payload is `<ts>.<raw_body>`. Raises ValueError on any mismatch.
    """
    secret = secret or STRIPE_WEBHOOK_SECRET
    if not secret:
        raise ValueError("Stripe webhook secret is not configured")
    parts: dict[str, str] = {}
    for item in sig_header.split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k.strip()] = v.strip()
    ts = parts.get("t")
    sig = parts.get("v1")
    if not ts or not sig:
        raise ValueError("Malformed Stripe-Signature header")
    # allow up to 5 minutes of clock skew
    if abs(time.time() - int(ts)) > 300:
        raise ValueError("Stripe webhook timestamp is too old")
    signed = f"{ts}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("Stripe webhook signature does not match")
    return json.loads(payload.decode("utf-8"))
