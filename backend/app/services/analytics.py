"""Session analytics and statistics."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ReviewApproval, ReviewComment, ReviewSession, ReviewVersion


def get_user_analytics(db: Session, user_id: int) -> dict:
    """Get analytics for a user's sessions."""
    sessions = db.scalars(
        select(ReviewSession).where(ReviewSession.owner_id == user_id)
    ).all()

    total_sessions = len(sessions)
    session_ids = [s.id for s in sessions]

    if not session_ids:
        return {
            "total_sessions": 0,
            "total_versions": 0,
            "total_comments": 0,
            "total_approvals": 0,
            "sessions_by_status": {},
            "avg_versions_per_session": 0.0,
        }

    total_versions = db.scalar(
        select(func.count(ReviewVersion.id)).where(ReviewVersion.session_id.in_(session_ids))
    ) or 0

    total_comments = db.scalar(
        select(func.count(ReviewComment.id)).join(ReviewVersion).where(
            ReviewVersion.session_id.in_(session_ids)
        )
    ) or 0

    total_approvals = db.scalar(
        select(func.count(ReviewApproval.id)).where(
            ReviewApproval.session_id.in_(session_ids)
        )
    ) or 0

    sessions_by_status = {}
    for s in sessions:
        sessions_by_status[s.status] = sessions_by_status.get(s.status, 0) + 1

    avg_versions = total_versions / total_sessions if total_sessions > 0 else 0.0

    return {
        "total_sessions": total_sessions,
        "total_versions": total_versions,
        "total_comments": total_comments,
        "total_approvals": total_approvals,
        "sessions_by_status": sessions_by_status,
        "avg_versions_per_session": round(avg_versions, 2),
    }
