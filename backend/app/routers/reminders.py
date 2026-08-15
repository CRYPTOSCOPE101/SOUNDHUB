"""Reminder automation routes: cron entrypoint, engineer settings, client opt-out."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notification, User, utcnow
from ..schemas import NotificationOut, ReminderSettingsUpdate, RemindersEvalOut, ReviewSessionDetailOut
from ..security import get_current_user
from ..services import ledger, reminders
from .sessions import _session_detail, get_public_session, get_session_or_404

router = APIRouter(prefix="/api", tags=["reminders"])


@router.post("/reminders/evaluate", response_model=RemindersEvalOut)
def evaluate_reminders(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cron / smoke entrypoint: scan sessions, queue + send reminders."""
    result = reminders.run_all(db)
    db.commit()
    return result


@router.get("/sessions/{session_id}/reminders")
def session_reminders(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Engineer view: automation settings + the notification log for a session."""
    session = get_session_or_404(db, user, session_id)
    rows = db.scalars(
        select(Notification)
        .where(Notification.session_id == session_id)
        .order_by(Notification.id.desc())
        .limit(200)
    ).all()
    return {
        "settings": {
            "reminders_enabled": session.reminders_enabled,
            "reminder_categories": session.reminder_categories,
            "client_email": session.client_email,
            "client_opted_out": session.reminders_client_opt_out,
        },
        "notifications": [NotificationOut.model_validate(n, from_attributes=True) for n in rows],
    }


@router.patch("/sessions/{session_id}/reminders", response_model=ReviewSessionDetailOut)
def update_reminder_settings(
    session_id: int,
    payload: ReminderSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Engineer picks what to automate and where client mail goes."""
    session = get_session_or_404(db, user, session_id)
    if payload.reminders_enabled is not None:
        session.reminders_enabled = payload.reminders_enabled
    if payload.reminder_categories is not None:
        session.reminder_categories = payload.reminder_categories.strip()
    if payload.client_email is not None:
        session.client_email = payload.client_email.strip()
    session.updated_at = utcnow()
    ledger.append(
        db,
        "reminders.settings_updated",
        session_id=session.id,
        actor=user.username,
        entity_type="session",
        entity_id=session.id,
        payload={
            "enabled": session.reminders_enabled,
            "categories": session.reminder_categories[:200],
            "client_email": bool(session.client_email),
        },
    )
    db.commit()
    return _session_detail(db, session)


@router.post("/sessions/public/{share_token}/reminders/opt-out")
def client_opt_out(
    share_token: str,
    db: Session = Depends(get_db),
):
    """Client can silence non-critical reminders (transactional mail stays on)."""
    session = get_public_session(db, share_token)
    session.reminders_client_opt_out = True
    dismissed = reminders.dismiss_pending(db, session.id)
    db.commit()
    return {"opted_out": True, "dismissed": dismissed["dismissed"]}
