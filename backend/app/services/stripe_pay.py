"""Stripe Checkout integration for payments."""
import stripe

from ..config import STRIPE_API_BASE, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET


def enabled() -> bool:
    return bool(STRIPE_SECRET_KEY)


def create_checkout_session(
    amount_cents: int,
    currency: str,
    package_id: int,
    package_name: str,
    session_id: int,
    success_url: str,
    cancel_url: str,
    metadata: dict | None = None,
) -> tuple[str, str]:
    """Create a Stripe Checkout session. Returns (session_id, checkout_url)."""
    if not enabled():
        raise RuntimeError("Stripe is not configured")

    stripe.api_key = STRIPE_SECRET_KEY

    params = {
        "payment_method_types": ["card"],
        "line_items": [
            {
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": package_name},
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {
            "package_id": str(package_id),
            "session_id": str(session_id),
            **(metadata or {}),
        },
    }

    checkout = stripe.checkout.Session.create(**params)
    return checkout.id, checkout.url


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify and construct a Stripe webhook event."""
    if not STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("Stripe webhook secret not configured")
    return stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
