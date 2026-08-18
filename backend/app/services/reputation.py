"""Engineer reputation scoring.

Reputation is computed from real session data — bio, specialty, location
are the only self-edited fields.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ReviewApproval, ReviewSession, ReviewVersion


def compute_reputation(db: Session, user_id: int) -> dict:
    """Compute reputation metrics for a user."""
    sessions = db.scalars(
        select(ReviewSession).where(ReviewSession.owner_id == user_id)
    ).all()

    total_sessions = len(sessions)
    approved_sessions = sum(1 for s in sessions if s.status == "approved")

    total_versions = db.scalar(
        select(func.count(ReviewVersion.id))
        .join(ReviewSession)
        .where(ReviewSession.owner_id == user_id)
    ) or 0

    total_approvals = db.scalar(
        select(func.count(ReviewApproval.id))
        .join(ReviewSession)
        .where(ReviewSession.owner_id == user_id, ReviewApproval.approved == True)
    ) or 0

    # Simple reputation score
    score = 0
    score += min(total_sessions * 10, 100)  # up to 100 for sessions
    score += min(approved_sessions * 15, 150)  # up to 150 for approvals
    score += min(total_versions * 2, 100)  # up to 100 for versions

    return {
        "score": min(score, 500),
        "total_sessions": total_sessions,
        "approved_sessions": approved_sessions,
        "total_versions": total_versions,
        "total_approvals": total_approvals,
        "approval_rate": round(approved_sessions / total_sessions * 100, 1) if total_sessions > 0 else 0,
    }


def badge_for_score(score: int) -> str:
    """Return a badge label for a reputation score."""
    if score >= 400:
        return "Gold"
    elif score >= 250:
        return "Silver"
    elif score >= 100:
        return "Bronze"
    else:
        return "Newcomer"
