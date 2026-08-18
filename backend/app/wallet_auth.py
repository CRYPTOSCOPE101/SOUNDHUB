"""Web3 wallet authentication.

Flow: client requests a nonce → signs a message with their wallet
(personal_sign) → server recovers the signer and issues a JWT.
"""
import logging
import secrets
import threading
import time
from datetime import datetime, timezone

from eth_account import Account
from eth_account.messages import encode_defunct

NONCE_TTL_SECONDS = 300  # 5 minutes

_lock = threading.Lock()
_pending: dict[str, dict] = {}  # nonce -> {"address": str, "expires": float}

DOMAIN = "soundhub.xyz"

logger = logging.getLogger(__name__)


def _cleanup() -> None:
    now = time.time()
    for nonce in [k for k, v in _pending.items() if v["expires"] < now]:
        _pending.pop(nonce, None)


def issue_challenge(address: str) -> tuple[str, str]:
    """Create a fresh nonce and the exact message to sign."""
    _cleanup()
    nonce = secrets.token_hex(16)
    issued = datetime.now(timezone.utc).isoformat(timespec="seconds")
    message = (
        f"{DOMAIN} wants you to sign in with your SoundHub account:\n"
        f"{address}\n\n"
        f"Nonce: {nonce}\n"
        f"Issued at: {issued}"
    )
    with _lock:
        _pending[nonce] = {"address": address.lower(), "expires": time.time() + NONCE_TTL_SECONDS}
    return nonce, message


def verify_challenge(address: str, message: str, signature: str) -> bool:
    """Recover the signer of `message` and compare with `address`."""
    nonce = _extract_nonce(message)
    if nonce is None:
        return False
    with _lock:
        challenge = _pending.pop(nonce, None)
    if challenge is None:
        return False
    if challenge["expires"] < time.time():
        return False
    if challenge["address"] != address.lower():
        return False

    try:
        recovered = Account.recover_message(encode_defunct(text=message), signature=signature)
    except Exception:
        # Any recovery failure means an unusable signature — log it so bad
        # clients and malformed signatures are diagnosable, then reject.
        logger.warning("signature recovery failed for %s", address, exc_info=True)
        return False
    return recovered.lower() == address.lower()


def _extract_nonce(message: str) -> str | None:
    for line in message.splitlines():
        line = line.strip()
        if line.startswith("Nonce:"):
            value = line.split(":", 1)[1].strip()
            return value if len(value) == 32 else None
    return None
