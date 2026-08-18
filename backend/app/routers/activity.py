"""Activity feed router."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ActivityEvent
from ..schemas import ActivityEventOut
from ..security import get_current_user

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("", response_model=list[ActivityEventOut])
def list_activity(
    session_id: int | None = None,
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(ActivityEvent).order_by(ActivityEvent.created_at.desc())
    if session_id:
        query = query.where(ActivityEvent.session_id == session_id)
    else:
        query = query.where(ActivityEvent.user_id == user.id)
    events = db.scalars(query.limit(limit)).all()
    return [ActivityEventOut.model_validate(e, from_attributes=True) for e in events]
