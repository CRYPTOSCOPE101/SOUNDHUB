"""Activity feed router."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ActivityEvent, ReviewSession
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
        session = db.get(ReviewSession, session_id)
        if session is None or session.owner_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        query = query.where(ActivityEvent.session_id == session_id)
    else:
        query = query.where(ActivityEvent.user_id == user.id)
    events = db.scalars(query.limit(limit)).all()
    return [ActivityEventOut.model_validate(e, from_attributes=True) for e in events]
