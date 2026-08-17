"""Engineer reputation — trust signals computed from real platform data.

Nothing here is self-reported or hand-set: every number comes from rows the
engineer actually produced (review sessions, approved versions, locked
release packages, approval signatures). `verified` means the account has a
linked wallet (the wallet login already verifies ownership via signature).

Returned as a dict (the router wraps it in the schema):
  delivered_count     — release packages locked & delivered (status ready)
  approved_count      — sessions with an approved version
  session_count       — review sessions owned by the engineer
  avg_rounds          — mean highest round reached per session with versions
  on_time_rate        — share of approved sessions finished by deadline (0..1, None if no deadlines)
  verified            — wallet linked (identity proof)
  badges              — human-readable achievement strings
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ReleasePackage, ReviewApproval, ReviewSession, ReviewVersion, User


def _approved_at(db: Session, session_id: int, version_id: int) -> datetime | None:
    """When the last approving signature for this version landed."""
    row = db.scalar(
        select(ReviewApproval.created_at)
        .where(
            ReviewApproval.session_id == session_id,
            ReviewApproval.version_id == version_id,
            ReviewApproval.approved.is_(True),
        )
        .order_by(ReviewApproval.created_at.desc())
        .limit(1)
    )
    return row


def engineer_reputation(db: Session, user: User) -> dict:
    sessions = db.scalars(
        select(ReviewSession).where(ReviewSession.owner_id == user.id)
    ).all()

    delivered = db.scalar(
        select(func.count(ReleasePackage.id)).where(
            ReleasePackage.session_id.in_([s.id for s in sessions] or [-1]),
            ReleasePackage.status == "ready",
        )
    ) or 0

    approved_count = 0
    avg_rounds: float | None = None
    on_time_done = 0
    on_time_ok = 0
    round_sums = 0
    round_sessions = 0

    for s in sessions:
        versions = db.scalars(
            select(ReviewVersion)
            .where(ReviewVersion.session_id == s.id)
            .order_by(ReviewVersion.number.desc())
        ).all()
        if versions:
            round_sums += max(v.round_number or 1 for v in versions)
            round_sessions += 1
        approved = next((v for v in versions if v.status == "approved"), None)
        if approved is not None:
            approved_count += 1
            if s.deadline_at is not None:
                on_time_done += 1
                at = _approved_at(db, s.id, approved.id)
                if at is not None and at <= s.deadline_at:
                    on_time_ok += 1

    if round_sessions:
        avg_rounds = round(round_sums / round_sessions, 2)

    verified = bool(user.wallet_address)

    badges: list[str] = []
    if delivered > 0:
        badges.append(f"{delivered} delivered package{'s' if delivered != 1 else ''}")
    if approved_count > 0:
        badges.append(f"{approved_count} approved session{'s' if approved_count != 1 else ''}")
    if avg_rounds is not None and avg_rounds <= 1.5:
        badges.append("Fast turnaround — usually approved in 1–2 rounds")
    if on_time_done and on_time_ok == on_time_done:
        badges.append("On-time deliveries")
    if user.wallet_address:
        badges.append("Wallet-linked identity")

    return {
        "delivered_count": delivered,
        "approved_count": approved_count,
        "session_count": len(sessions),
        "avg_rounds": avg_rounds,
        "on_time_rate": (on_time_ok / on_time_done) if on_time_done else None,
        "verified": verified,
        "badges": badges,
        "bio": user.bio or "",
        "specialty": user.specialty or "",
        "location": user.location or "",
    }
