"""Activity feed — who did what, when, on which session/project."""
from sqlalchemy.orm import Session

from ..models import ActivityEvent


def record(
    db: Session,
    event_type: str,
    user_id: int | None = None,
    session_id: int | None = None,
    project_id: int | None = None,
    actor_name: str = "",
    entity_type: str = "",
    entity_id: int | None = None,
    detail: str = "",
    metadata_json: dict | None = None,
) -> ActivityEvent:
    """Record an activity event."""
    event = ActivityEvent(
        user_id=user_id,
        session_id=session_id,
        project_id=project_id,
        event_type=event_type,
        actor_name=actor_name,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
        metadata_json=metadata_json,
    )
    db.add(event)
    return event
