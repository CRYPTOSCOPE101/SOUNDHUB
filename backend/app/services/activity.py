"""Activity feed — record events and query the feed."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import ActivityEvent


def record(
    db: DbSession,
    *,
    event_type: str,
    actor_name: str = "",
    user_id: int | None = None,
    session_id: int | None = None,
    project_id: int | None = None,
    entity_type: str = "",
    entity_id: int | None = None,
    detail: str = "",
    metadata_json: dict | None = None,
) -> ActivityEvent:
    """Record a single activity event."""
    ev = ActivityEvent(
        event_type=event_type,
        actor_name=actor_name,
        user_id=user_id,
        session_id=session_id,
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
        metadata_json=metadata_json,
    )
    db.add(ev)
    db.flush()
    return ev


def get_session_feed(
    db: DbSession, session_id: int, limit: int = 50, offset: int = 0
) -> list[ActivityEvent]:
    """Recent activity for a session."""
    return list(
        db.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.session_id == session_id)
            .order_by(ActivityEvent.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def get_project_feed(
    db: DbSession, project_id: int, limit: int = 50, offset: int = 0
) -> list[ActivityEvent]:
    """Recent activity for a project."""
    return list(
        db.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.project_id == project_id)
            .order_by(ActivityEvent.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


def get_user_feed(
    db: DbSession, user_id: int, limit: int = 50, offset: int = 0
) -> list[ActivityEvent]:
    """Recent activity across all of a user's sessions and projects."""
    return list(
        db.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.user_id == user_id)
            .order_by(ActivityEvent.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
