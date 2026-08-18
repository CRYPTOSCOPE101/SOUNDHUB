"""License management for delivered assets."""


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
