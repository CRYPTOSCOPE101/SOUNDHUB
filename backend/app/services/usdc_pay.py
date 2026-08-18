"""USDC on-chain payments on Base network."""
from ..config import BASE_RPC_URL, USDC_CHAIN_ID, USDC_DECIMALS, USDC_TOKEN_ADDRESS


def enabled() -> bool:
    return bool(BASE_RPC_URL)


def usdc_to_raw(amount: float) -> int:
    """Convert USDC amount to raw integer (6 decimals)."""
    return int(amount * (10 ** USDC_DECIMALS))


def raw_to_usdc(raw: int) -> float:
    """Convert raw integer to USDC amount."""
    return raw / (10 ** USDC_DECIMALS)


def payment_info() -> dict:
    """Return USDC payment configuration."""
    return {
        "enabled": enabled(),
        "token_address": USDC_TOKEN_ADDRESS,
        "decimals": USDC_DECIMALS,
        "chain_id": USDC_CHAIN_ID,
        "network": "Base",
    }
