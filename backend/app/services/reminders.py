"""Email reminders with SMTP transport.

The engineer picks what to send and how often; the client can opt out
of non-critical reminders (never transactional mail like payment receipts).
"""
import hashlib
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Notification, ReviewSession


def _deliver(msg: EmailMessage) -> None:
    """Transport: send one EmailMessage via SMTP; raises on any failure."""
    host = config.SMTP_HOST
    port = config.SMTP_PORT
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
            if config.SMTP_USER:
                smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.send_message(msg)
        return
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        try:
            smtp.starttls()
        except smtplib.SMTPException:
            pass
        if config.SMTP_USER:
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(msg)


def _smtp_send(notification: Notification) -> None:
    """Deliver via SMTP; raises on any failure."""
    msg = EmailMessage()
    msg["Subject"] = notification.subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = notification.recipient
    msg.set_content(f"{notification.body}\n\n{notification.cta_label}: {notification.cta_url}")
    _deliver(msg)


def evaluate(db: Session) -> dict:
    """Evaluate all active sessions for pending reminders.

    Returns {"evaluated": N, "created": M}.
    """
    sessions = db.scalars(
        select(ReviewSession).where(ReviewSession.reminders_enabled == True)
    ).all()

    evaluated = 0
    created = 0

    for session in sessions:
        if not session.client_email:
            continue
        if session.reminders_client_opt_out:
            continue

        evaluated += 1
        notifications = _check_session_reminders(db, session)
        created += len(notifications)

    db.commit()
    return {"evaluated": evaluated, "created": created}


def _check_session_reminders(db: Session, session: ReviewSession) -> list[Notification]:
    """Check a session for pending reminders and create notifications."""
    notifications = []
    now = datetime.now(timezone.utc)

    # Review opened reminder
    if session.status == "in_review":
        key = f"{session.id}:review.opened:{now.strftime('%Y-%m-%d')}"
        if not _exists(db, key):
            n = _create_notification(
                db, session, "review.opened",
                "New version ready for review",
                f"A new version has been uploaded to '{session.name}'. Please review and leave your feedback.",
                f"{config.FRONTEND_URL}/r/{session.share_token}",
                "Open review",
                session.client_email,
            )
            notifications.append(n)

    # Feedback deadline reminder
    if session.feedback_due_at and session.feedback_due_at > now:
        days_left = (session.feedback_due_at - now).days
        if days_left <= 2:
            key = f"{session.id}:feedback.deadline:{now.strftime('%Y-%m-%d')}"
            if not _exists(db, key):
                n = _create_notification(
                    db, session, "feedback.deadline",
                    "Feedback deadline approaching",
                    f"Feedback for '{session.name}' is due in {days_left} day(s).",
                    f"{config.FRONTEND_URL}/r/{session.share_token}",
                    "Leave feedback",
                    session.client_email,
                )
                notifications.append(n)

    return notifications


def _exists(db: Session, dedup_key: str) -> bool:
    return db.scalar(select(Notification).where(Notification.dedup_key == dedup_key)) is not None


def _create_notification(
    db: Session,
    session: ReviewSession,
    kind: str,
    subject: str,
    body: str,
    cta_url: str,
    cta_label: str,
    recipient: str,
) -> Notification:
    dedup_key = hashlib.sha256(f"{session.id}:{kind}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}".encode()).hexdigest()[:40]
    n = Notification(
        session_id=session.id,
        kind=kind,
        channel="email",
        recipient=recipient,
        subject=subject,
        body=body,
        cta_url=cta_url,
        cta_label=cta_label,
        status="queued",
        dedup_key=dedup_key,
    )
    db.add(n)
    return n


def send_pending(db: Session) -> dict:
    """Send all queued notifications."""
    queued = db.scalars(select(Notification).where(Notification.status == "queued")).all()
    sent = 0
    failed = 0
    for n in queued:
        if not n.recipient:
            continue
        try:
            _smtp_send(n)
            n.status = "sent"
            n.sent_at = datetime.now(timezone.utc)
            sent += 1
        except Exception as e:
            n.status = "failed"
            n.error = str(e)[:500]
            failed += 1
    db.commit()
    return {"sent": sent, "failed": failed}


def run_all(db: Session) -> dict:
    """Evaluate + send in one shot (used at startup)."""
    result = evaluate(db)
    send_result = send_pending(db)
    result.update(send_result)
    return result
