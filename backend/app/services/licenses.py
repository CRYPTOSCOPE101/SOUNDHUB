"""License management for delivered assets."""
import hmac
import hashlib


def create_license(
    session_id: int,
    version_id: int,
    buyer_address: str,
    license_type: str = "standard",
) -> dict:
    """Create a license record for a delivered asset."""
    return {
        "session_id": session_id,
        "version_id": version_id,
        "buyer_address": buyer_address,
        "license_type": license_type,
        "terms": "Non-exclusive, perpetual license for the delivered audio files.",
    }


def create_signature(secret_key: str, receipt: dict) -> str:
    """Create a signature for a license receipt.

    Args:
        secret_key: The secret key used for signing
        receipt: The license receipt dictionary to sign (should not contain a signature field)

    Returns:
        Hexadecimal HMAC-SHA256 signature
    """
    # Create a canonical string representation of the receipt
    # Sort keys to ensure consistent ordering
    sorted_items = sorted(receipt.items())
    canonical_string = "&".join(f"{k}={v}" for k, v in sorted_items)

    # Generate the signature using HMAC-SHA256
    signature = hmac.new(
        secret_key.encode('utf-8'),
        canonical_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return signature


def verify_license_receipt(secret_key: str, receipt: dict) -> bool:
    """Verify a license receipt signature.

    Args:
        secret_key: The secret key used for signing
        receipt: The license receipt dictionary to verify

    Returns:
        True if the signature is valid, False otherwise
    """
    # Make a copy of the receipt without the signature field
    receipt_copy = receipt.copy()
    signature = receipt_copy.pop("signature", "")

    # Create the expected signature
    expected_signature = create_signature(secret_key, receipt_copy)

    # Compare signatures using constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, signature)
