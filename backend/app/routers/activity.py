"""Activity feed — who did what, when."""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services import activity as act_svc

router = APIRouter(prefix="/api/activity", tags=["activity"])


class ActivityEventOut(BaseModel):
    id: int
    event_type: str
    actor_name: str
    entity_type: str
    entity_id: int | None
    detail: str
    session_id: int | None
    project_id: int | None
    created_at: str | None

    class Config:
        from_attributes = True


def _serialize(ev) -> dict:
    return {
        "id": ev.id,
        "event_type": ev.event_type,
        "actor_name": ev.actor_name,
        "entity_type": ev.entity_type,
        "entity_id": ev.entity_id,
        "detail": ev.detail,
        "session_id": ev.session_id,
        "project_id": ev.project_id,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


@router.get("/sessions/{session_id}")
def get_session_activity(
    session_id: int,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    events = act_svc.get_session_feed(db, session_id, limit, offset)
    return {"events": [_serialize(e) for e in events]}


@router.get("/projects/{project_id}")
def get_project_activity(
    project_id: int,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    events = act_svc.get_project_feed(db, project_id, limit, offset)
    return {"events": [_serialize(e) for e in events]}


@router.get("/me")
def get_my_activity(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    events = act_svc.get_user_feed(db, user.id, limit, offset)
    return {"events": [_serialize(e) for e in events]}
