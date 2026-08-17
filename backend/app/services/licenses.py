"""License receipts — machine- and human-readable proof of what a purchase allows.

Every purchase on SoundHub ships a receipt that states *what the buyer may do
with the audio*, not just that ownership moved. The receipt is signed with the
app secret so it can be re-verified later (e.g. to gate delivery or resolve a
dispute).

Prototype note: like the download token, the receipt is issued with the
buyer/seller the client reports. Production must verify the purchase on-chain
against SoundHubMarket (buyer == contract.buyer, escrowed > 0) before issuing.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid

RECEIPT_VERSION = "1.0"

# license -> (what the buyer gets, what the seller keeps)
LICENSE_SCOPES: dict[str, tuple[str, str]] = {
    "Personal": (
        "Use in personal projects, demos and private sketches",
        "Commercial distribution is not allowed",
    ),
    "Commercial": (
        "Releases, streaming, client projects and monetized work",
        "Reselling the raw asset itself is not allowed",
    ),
    "Sync": (
        "Sync licensing for film, TV, games, ads and video",
        "Exclusive territory or term may require a separate agreement",
    ),
    "Exclusive": (
        "Exclusive license — the listing is delisted after the sale",
        "Terms are fixed in the purchase agreement",
    ),
}


def _canonical(payload: dict) -> str:
    """Deterministic string over the receipt fields (sorted keys)."""
    return "|".join(f"{k}={payload[k]}" for k in sorted(payload))


def _sign(secret: str, payload: dict) -> str:
    return hmac.new(secret.encode(), _canonical(payload).encode(), hashlib.sha256).hexdigest()


def make_license_receipt(
    secret: str,
    *,
    listing_id: int,
    asset_name: str,
    license: str,
    seller: str,
    buyer: str,
    price_snd: str,
    asset_hash: str,
) -> dict:
    """Build a signed license receipt for a purchase."""
    scope = LICENSE_SCOPES.get(license)
    issued_at = int(time.time())
    payload = {
        "receipt_id": uuid.uuid4().hex[:16],
        "version": RECEIPT_VERSION,
        "listing_id": listing_id,
        "asset_name": asset_name,
        "license": license,
        "buyer_can": scope[0] if scope else "",
        "seller_keeps": scope[1] if scope else "",
        "seller": seller,
        "buyer": buyer,
        "price_snd": price_snd,
        "asset_sha256": asset_hash,
        "issued_at": issued_at,
    }
    payload["signature"] = _sign(secret, payload)
    return payload


def verify_license_receipt(secret: str, receipt: dict) -> bool:
    """Return True if the receipt's signature matches its (unchanged) fields."""
    if not isinstance(receipt, dict) or not receipt.get("signature"):
        return False
    body = {k: v for k, v in receipt.items() if k != "signature"}
    expected = _sign(secret, body)
    return hmac.compare_digest(expected, str(receipt["signature"]))
