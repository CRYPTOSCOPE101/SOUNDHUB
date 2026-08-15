"""Decision ledger — append-only, tamper-evident event history.

event_hash = SHA256(prev_event_hash || canonical_payload)

The canonical payload is a stable JSON with sorted keys, so the same event
always produces the same hash. Rewriting or deleting an old event breaks the
chain and `verify_history` reports it.
"""

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import LedgerEvent


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _chain_hash(prev_hash: str | None, canonical: bytes) -> str:
    return hashlib.sha256((prev_hash or "").encode() + canonical).hexdigest()


def last_event_hash(db: Session) -> str | None:
    row = db.scalar(select(LedgerEvent.event_hash).order_by(LedgerEvent.id.desc()).limit(1))
    return row


def append(
    db: Session,
    event: str,
    *,
    session_id: int | None = None,
    package_id: int | None = None,
    actor: str = "",
    entity_type: str = "",
    entity_id: int | None = None,
    payload: dict | None = None,
) -> LedgerEvent:
    """Append an event to the chain and return it (caller commits)."""
    payload = payload or {}
    canonical = _canonical(payload)
    prev_hash = last_event_hash(db)
    entry = LedgerEvent(
        event=event,
        session_id=session_id,
        package_id=package_id,
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        prev_event_hash=prev_hash,
        event_hash=_chain_hash(prev_hash, canonical),
    )
    db.add(entry)
    return entry


def verify_history(db: Session) -> dict:
    """Walk the chain and confirm every hash matches. Returns integrity result."""
    rows = db.scalars(select(LedgerEvent).order_by(LedgerEvent.id)).all()
    prev = None
    problems: list[dict] = []
    for r in rows:
        expected = _chain_hash(prev, _canonical(r.payload))
        if r.event_hash != expected:
            problems.append({"id": r.id, "event": r.event, "expected": expected, "stored": r.event_hash})
        prev = r.event_hash
    return {
        "ok": not problems,
        "total": len(rows),
        "head_hash": prev,
        "problems": problems,
    }
