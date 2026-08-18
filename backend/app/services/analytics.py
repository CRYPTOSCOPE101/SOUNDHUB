"""Session analytics — metrics and insights for professional workflows."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from ..models import (
    ActivityEvent,
    ReviewApproval,
    ReviewComment,
    ReviewSession,
    ReviewVersion,
    SessionMember,
    ShareAccessEvent,
)


def session_stats(db: DbSession, session_id: int) -> dict:
    """Comprehensive stats for a single session."""
    session = db.get(ReviewSession, session_id)
    if not session:
        return {}

    # Version count and status distribution
    versions = list(
        db.scalars(
            select(ReviewVersion).where(ReviewVersion.session_id == session_id)
        ).all()
    )
    version_statuses = {}
    for v in versions:
        version_statuses[v.status] = version_statuses.get(v.status, 0) + 1

    # Comment count
    comment_count = 0
    unresolved_count = 0
    for v in versions:
        comments = list(
            db.scalars(
                select(ReviewComment).where(ReviewComment.version_id == v.id)
            ).all()
        )
        comment_count += len(comments)
        unresolved_count += sum(1 for c in comments if not c.resolved)

    # Approval stats
    approvals = list(
        db.scalars(
            select(ReviewApproval).where(ReviewApproval.session_id == session_id)
        ).all()
    )
    approval_scopes = {}
    for a in approvals:
        approval_scopes.setdefault(a.scope, {"approved": 0, "rejected": 0})
        if a.approved:
            approval_scopes[a.scope]["approved"] += 1
        else:
            approval_scopes[a.scope]["rejected"] += 1

    # Access stats
    access_count = db.scalar(
        select(func.count(ShareAccessEvent.id)).where(
            ShareAccessEvent.session_id == session_id
        )
    ) or 0

    # Member count
    member_count = db.scalar(
        select(func.count(SessionMember.id)).where(
            SessionMember.session_id == session_id
        )
    ) or 0

    # Activity count
    activity_count = db.scalar(
        select(func.count(ActivityEvent.id)).where(
            ActivityEvent.session_id == session_id
        )
    ) or 0

    # Time metrics
    created = session.created_at
    updated = session.updated_at
    if created and updated:
        duration_days = (updated - created).days
    else:
        duration_days = 0

    # First version upload time
    first_version_time = None
    if versions:
        first = min(versions, key=lambda v: v.created_at or datetime.max.replace(tzinfo=timezone.utc))
        if first.created_at and created:
            first_version_time = (first.created_at - created).total_seconds() / 3600

    return {
        "session_id": session_id,
        "name": session.name,
        "status": session.status,
        "round_number": session.round_number,
        "total_versions": len(versions),
        "version_statuses": version_statuses,
        "total_comments": comment_count,
        "unresolved_comments": unresolved_count,
        "approval_scopes": approval_scopes,
        "total_approvals": len(approvals),
        "access_count": access_count,
        "member_count": member_count,
        "activity_count": activity_count,
        "duration_days": duration_days,
        "first_version_hours": round(first_version_time, 1) if first_version_time else None,
    }


def user_stats(db: DbSession, user_id: int) -> dict:
    """Aggregate stats across all of a user's sessions."""
    sessions = list(
        db.scalars(
            select(ReviewSession).where(ReviewSession.owner_id == user_id)
        ).all()
    )

    total_versions = 0
    total_comments = 0
    total_accesses = 0
    status_dist = {}
    for s in sessions:
        v_count = db.scalar(
            select(func.count(ReviewVersion.id)).where(ReviewVersion.session_id == s.id)
        ) or 0
        total_versions += v_count

        c_count = db.scalar(
            select(func.count(ReviewComment.id))
            .join(ReviewVersion, ReviewComment.version_id == ReviewVersion.id)
            .where(ReviewVersion.session_id == s.id)
        ) or 0
        total_comments += c_count

        a_count = db.scalar(
            select(func.count(ShareAccessEvent.id)).where(
                ShareAccessEvent.session_id == s.id
            )
        ) or 0
        total_accesses += a_count

        status_dist[s.status] = status_dist.get(s.status, 0) + 1

    return {
        "user_id": user_id,
        "total_sessions": len(sessions),
        "total_versions": total_versions,
        "total_comments": total_comments,
        "total_accesses": total_accesses,
        "session_status_distribution": status_dist,
    }


def recent_activity_summary(db: DbSession, user_id: int, days: int = 7) -> dict:
    """Activity summary for the last N days."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    events = list(
        db.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.user_id == user_id, ActivityEvent.created_at >= cutoff)
        ).all()
    )

    event_types = {}
    for e in events:
        event_types[e.event_type] = event_types.get(e.event_type, 0) + 1

    return {
        "period_days": days,
        "total_events": len(events),
        "event_type_distribution": event_types,
    }
