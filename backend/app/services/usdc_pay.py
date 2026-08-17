"""USDC checkout on Base — the crypto payment layer beside Stripe.

Flow (no custodial step, no webhook needed):

1. Client asks for payment terms (`terms_for_*`): amount in USDC units
   (6 decimals), payee address (engineer's linked wallet, fallback address
   otherwise), the USDC token and chain id.
2. Client sends USDC to the payee from their own wallet (MetaMask / WalletConnect).
3. Client posts the tx hash to `/webhooks/usdc`; we read the transaction
   receipt over JSON-RPC and look for a `Transfer(payee, amount)` log from
   the USDC token contract. If the amount covers the invoice (and the tx is
   confirmed), the invoice is marked paid — idempotently.

When `BASE_RPC_URL` is unset the flow is disabled (503) and the manual
"mark paid" path stays the fallback, exactly like Stripe-less mode.
"""

import hashlib
import json
import time

import httpx

from .. import config

# keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

RPC_TIMEOUT = httpx.Timeout(15.0)


def enabled() -> bool:
    return bool(config.BASE_RPC_URL)


def decimals() -> int:
    return config.USDC_DECIMALS


def chain_id() -> int:
    return config.USDC_CHAIN_ID


def token_address() -> str:
    return config.USDC_TOKEN_ADDRESS


def payee_for(wallet_address: str | None) -> str:
    """Where the client sends USDC: the engineer's wallet, or the fallback."""
    if wallet_address:
        return wallet_address
    return config.USDC_FALLBACK_PAYEE


def has_payee(wallet_address: str | None) -> bool:
    return bool(wallet_address or config.USDC_FALLBACK_PAYEE)


def usdc_units(amount_cents: int) -> int:
    """Convert invoice cents → USDC base units (6 decimals, 1 USDC = $1)."""
    return amount_cents * (10 ** (config.USDC_DECIMALS - 2))


def _rpc(method: str, params: list) -> dict | None:
    resp = httpx.post(
        config.BASE_RPC_URL,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=RPC_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"RPC error ({resp.status_code}): {resp.text[:200]}")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result")


def get_transaction_receipt(tx_hash: str) -> dict | None:
    return _rpc("eth_getTransactionReceipt", [tx_hash])


def _hex_uint(value: str) -> int:
    return int(value, 16) if value else 0


def _address(log_topic: str) -> str:
    """0x + last 20 bytes of a padded topic."""
    return "0x" + log_topic[-40:].lower()


def find_usdc_transfer(
    receipt: dict,
    *,
    to_address: str,
    min_units: int,
    token: str | None = None,
) -> dict | None:
    """Find a USDC Transfer log paying `to_address` ≥ min_units.

    Returns {from, to, value, log_index} or None. `receipt` is the raw
    JSON-RPC receipt (with `logs` and `logsBloom`).
    """
    token = (token or config.USDC_TOKEN_ADDRESS).lower()
    target = to_address.lower()
    logs = receipt.get("logs") or []
    for i, log in enumerate(logs):
        if (log.get("address") or "").lower() != token:
            continue
        topics = log.get("topics") or []
        if not topics or topics[0].lower() != TRANSFER_TOPIC:
            continue
        if len(topics) < 3:
            continue
        if _address(topics[2]) != target:
            continue
        value = _hex_uint(log.get("data") or "0x0")
        if value >= min_units:
            return {
                "from": _address(topics[1]),
                "to": _address(topics[2]),
                "value": value,
                "log_index": i,
            }
    return None


def verify_transfer(
    tx_hash: str,
    *,
    to_address: str,
    min_units: int,
    confirmations: int = 0,
    token: str | None = None,
) -> dict:
    """Verify a USDC transfer paid `to_address` ≥ min_units.

    Raises ValueError with a human reason when the tx doesn't satisfy the
    payment (not found, wrong token, wrong payee, insufficient amount).
    Returns the matched Transfer log info on success.
    """
    tx_hash = tx_hash.strip().lower()
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        raise ValueError("Invalid transaction hash")

    receipt = get_transaction_receipt(tx_hash)
    if receipt is None:
        # not yet mined (or pending) — surface a distinct message
        raise ValueError("Transaction not found on chain yet — is it mined?")

    match = find_usdc_transfer(
        receipt, to_address=to_address, min_units=min_units, token=token
    )
    if match is None:
        raise ValueError(
            "No matching USDC transfer found — check the amount, the payee address and that you used the USDC token on Base"
        )
    if confirmations > 0:
        block_number = _hex_uint(receipt.get("blockNumber") or "0x0")
        current = _hex_uint((_rpc("eth_blockNumber", []) or "0x0"))
        if current - block_number < confirmations:
            raise ValueError(
                f"Transaction is still confirming ({current - block_number} of {confirmations} blocks) — try again shortly"
            )
    return match


def sha256_ref(tx_hash: str) -> str:
    """Stable dedup key for a payment (ledger + idempotency)."""
    return hashlib.sha256(tx_hash.lower().encode()).hexdigest()[:16]


def terms(
    *,
    amount_cents: int,
    wallet_address: str | None,
    purpose: str,
) -> dict:
    """Payment terms the client needs to send USDC from their wallet."""
    if not enabled():
        raise RuntimeError("USDC checkout is not configured (set SOUNDHUB_BASE_RPC_URL)")
    if not has_payee(wallet_address):
        raise RuntimeError("This engineer has no wallet linked — ask them to link one, or pay by card")
    payee = payee_for(wallet_address)
    units = usdc_units(amount_cents)
    return {
        "network": "base",
        "chain_id": chain_id(),
        "token_address": token_address(),
        "payee_address": payee,
        "amount_usdc_units": units,
        "amount_usdc": round(units / 10 ** config.USDC_DECIMALS, 6),
        "decimals": config.USDC_DECIMALS,
        "purpose": purpose,
        "expires_at": int(time.time()) + 3600,  # soft expiry for display only
    }
