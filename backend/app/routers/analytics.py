"""Session analytics — metrics and insights."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services import analytics as analytics_svc

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/sessions/{session_id}")
def get_session_stats(
    session_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return analytics_svc.session_stats(db, session_id)


@router.get("/me")
def get_my_stats(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return analytics_svc.user_stats(db, user.id)


@router.get("/me/activity")
def get_my_activity_summary(
    days: int = 7,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return analytics_svc.recent_activity_summary(db, user.id, days)
