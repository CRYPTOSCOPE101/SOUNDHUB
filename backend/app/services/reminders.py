"""Reminder automation — email nudges that keep review loops moving.

Events (all client-facing for now; engineer-side automation comes with roles):

    review.opened            first version ready for review
    approval.requested       a revised version (round >= 2) awaits a decision
    approval.reminder        a version has been waiting for approval 7+ days
    feedback.deadline_48h    revision notes due in ~48h
    feedback.deadline_24h    revision notes due in ~24h
    feedback.overdue         revision notes are overdue
    draft_notes.idle         draft notes sat unsubmitted for 3+ days
    invoice.due_7d           balance due in a week
    invoice.due_1d           balance due tomorrow
    invoice.overdue          balance overdue
    change_order.quote_expiring  a quote expires within 48h
    archive.expiring_30d     archived files expire within 30 days
    archive.expiring_7d      archived files expire within 7 days
    delivery.link_expiring   the delivery link expires within 7 days

Rules (product spec):
  - email in MVP; webhook / Discord / Telegram come later
  - no more than one email of the same type per 24h — enforced by a unique
    `dedup_key` on the Notification table, so a cron can re-run safely
  - the engineer chooses whether automation is on and which categories run
  - the client can disable *non-critical* reminders, never transactional
    ones (payment receipts / delivery links)
  - no reminders for archived / permanently-deleted / completed sessions
  - every send writes notification.sent / notification.failed /
    notification.dismissed into the existing decision ledger
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Notification, ReviewSession
from . import ledger

_logger = logging.getLogger("soundhub.reminders")

# kind -> category (what the engineer toggles in the UI)
KIND_CATEGORY: dict[str, str] = {
    "review.opened": "review",
    "approval.requested": "review",
    "approval.reminder": "review",
    "feedback.deadline_48h": "feedback",
    "feedback.deadline_24h": "feedback",
    "feedback.overdue": "feedback",
    "draft_notes.idle": "feedback",
    "invoice.due_7d": "invoice",
    "invoice.due_1d": "invoice",
    "invoice.overdue": "invoice",
    "change_order.quote_expiring": "change_order",
    "archive.expiring_30d": "archive",
    "archive.expiring_7d": "archive",
    "delivery.link_expiring": "delivery",
}

# Transactional mail the client can never opt out of (payment / delivery).
TRANSACTIONAL_KINDS = {"invoice.due_7d", "invoice.due_1d", "invoice.overdue", "delivery.link_expiring"}

CTA_LABELS: dict[str, str] = {
    "review.opened": "Listen & leave notes",
    "approval.requested": "Approve v{label}",
    "approval.reminder": "Approve v{label}",
    "feedback.deadline_48h": "Submit revision notes",
    "feedback.deadline_24h": "Submit revision notes",
    "feedback.overdue": "Submit revision notes",
    "draft_notes.idle": "Submit revision notes",
    "invoice.due_7d": "Pay balance",
    "invoice.due_1d": "Pay balance",
    "invoice.overdue": "Pay balance",
    "change_order.quote_expiring": "Review quote",
    "archive.expiring_30d": "See delivery",
    "archive.expiring_7d": "See delivery",
    "delivery.link_expiring": "Download delivery",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC (they are stored UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _hours_until(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    return (_as_utc(dt) - _now()).total_seconds() / 3600.0


def _day(dt: datetime | None = None) -> str:
    return (dt or _now()).strftime("%Y-%m-%d")


def _frontend_url(path: str) -> str:
    return f"{config.FRONTEND_URL}{path}"


def _allowed_kind(session: ReviewSession, kind: str) -> bool:
    """Engineer categories + client opt-out rules."""
    cats = {c.strip() for c in (session.reminder_categories or "").split(",") if c.strip()}
    if cats and KIND_CATEGORY.get(kind) not in cats:
        return False
    if session.reminders_client_opt_out and kind not in TRANSACTIONAL_KINDS:
        return False
    return True


def _queue(
    db: Session,
    session: ReviewSession,
    kind: str,
    *,
    subject: str,
    body: str,
    cta_path: str,
    label: str,
    dedup_key: str,
) -> bool:
    """Create one notification unless its dedup key already exists."""
    if db.scalar(select(Notification.id).where(Notification.dedup_key == dedup_key)):
        return False
    if not _allowed_kind(session, kind):
        return False
    db.add(
        Notification(
            session_id=session.id,
            kind=kind,
            recipient=session.client_email.strip(),
            subject=subject,
            body=body,
            cta_url=_frontend_url(cta_path),
            cta_label=label,
            dedup_key=dedup_key,
        )
    )
    return True


def _latest_version(session: ReviewSession):
    if not session.versions:
        return None
    return max(session.versions, key=lambda v: v.number)


def evaluate(db: Session) -> dict:
    """Scan active sessions and queue reminders (idempotent via dedup keys)."""
    created = 0
    evaluated = 0
    sessions = db.scalars(select(ReviewSession)).all()
    for session in sessions:
        # Suppression: only live review projects get reminders.
        if session.status not in ("in_review", "needs_changes", "approved"):
            continue
        if not session.reminders_enabled:
            continue
        if not session.client_email.strip():
            continue
        evaluated += 1
        sid = session.id
        token = session.share_token
        latest = _latest_version(session)

        # --- review.opened: first version ready for review -------------------
        if latest and latest.round_number == 1 and latest.status == "in_review":
            if _queue(
                db, session, "review.opened",
                subject=f"{session.name} — your mix is ready for review",
                body=f"{latest.label} ({latest.filename}) is ready. Listen at your own pace and leave timestamped notes — no account needed.",
                cta_path=f"/r/{token}",
                label=CTA_LABELS["review.opened"],
                dedup_key=f"{sid}:review.opened:{_day()}:v{latest.id}",
            ):
                created += 1

        # --- approval.requested: a revision awaits a decision -----------------
        if (
            latest
            and latest.round_number >= 2
            and latest.status in ("in_review", "needs_changes")
            and not latest.session.approvals
        ):
            if _queue(
                db, session, "approval.requested",
                subject=f"{session.name} — {latest.label} is ready for your call",
                body=f"The revised version {latest.label} responds to round {latest.round_number - 1}. Approve it, or add notes and submit a new round.",
                cta_path=f"/r/{token}",
                label=CTA_LABELS["approval.requested"].format(label=latest.label),
                dedup_key=f"{sid}:approval.requested:{_day()}:v{latest.id}",
            ):
                created += 1

        # --- approval.reminder: waiting 7+ days without a decision ------------
        if (
            latest
            and latest.status == "in_review"
            and (_as_utc(latest.created_at) or _now()) < _now() - timedelta(days=7)
            and not latest.session.approvals
        ):
            if _queue(
                db, session, "approval.reminder",
                subject=f"{session.name} — {latest.label} is still waiting on you",
                body=f"{latest.label} has been awaiting approval for over a week. A quick decision keeps the delivery on schedule.",
                cta_path=f"/r/{token}",
                label=CTA_LABELS["approval.reminder"].format(label=latest.label),
                dedup_key=f"{sid}:approval.reminder:{_day()}:v{latest.id}",
            ):
                created += 1

        # --- feedback deadlines (revision notes due / overdue) ----------------
        due = session.feedback_due_at or session.deadline_at
        if due and session.rounds_open and latest and latest.status in ("in_review", "needs_changes"):
            hours = _hours_until(due)
            if hours is not None:
                if 24 < hours <= 48:
                    kind = "feedback.deadline_48h"
                    subject = f"{session.name} — revision notes due in ~48h"
                    body = "Your notes for the current round are due in about two days. Gather them and submit once — the engineer works from the consolidated list."
                elif 0 < hours <= 24:
                    kind = "feedback.deadline_24h"
                    subject = f"{session.name} — revision notes due tomorrow"
                    body = "The current review round closes within 24 hours. Submit your consolidated notes to keep the schedule."
                elif hours <= 0:
                    kind = "feedback.overdue"
                    subject = f"{session.name} — revision notes are overdue"
                    body = "The review round is overdue. You can still submit — the engineer waits for the consolidated list before the next version."
                else:
                    kind = None
                if kind and _queue(
                    db, session, kind,
                    subject=subject,
                    body=body,
                    cta_path=f"/r/{token}",
                    label=CTA_LABELS[kind],
                    dedup_key=f"{sid}:{kind}:{_day()}",
                ):
                    created += 1

        # --- draft_notes.idle: drafts sat unsubmitted for 3+ days -------------
        if latest and (_as_utc(latest.created_at) or _now()) < _now() - timedelta(days=3):
            draft_count = sum(1 for c in latest.comments if c.status == "draft")
            if draft_count:
                if _queue(
                    db, session, "draft_notes.idle",
                    subject=f"{session.name} — {draft_count} draft note{'s' if draft_count != 1 else ''} not submitted",
                    body=f"{draft_count} draft note{'s' if draft_count != 1 else ''} on {latest.label} haven't been submitted yet. Send them as one consolidated round so the engineer can act.",
                    cta_path=f"/r/{token}",
                    label=CTA_LABELS["draft_notes.idle"],
                    dedup_key=f"{sid}:draft_notes.idle:v{latest.id}",
                ):
                    created += 1

        # --- invoices: due in 7d / 1d / overdue --------------------------------
        for pkg in session.release_packages:
            if pkg.invoice_status not in ("deposit_due", "balance_due"):
                continue
            if not pkg.amount_due_cents or pkg.amount_due_cents <= 0:
                continue
            due_at = _as_utc(pkg.invoice_due_at) or (_as_utc(pkg.immutable_at or pkg.created_at) + timedelta(days=14))
            hours = _hours_until(due_at)
            if hours is None:
                continue
            if 24 < hours <= 168:
                kind = "invoice.due_7d"
                subject = f"{session.name} — balance due in a week"
                body = f"Your balance of ${pkg.amount_due_cents / 100:.2f} is due in about a week. Paying unlocks the delivery download."
            elif 0 < hours <= 24:
                kind = "invoice.due_1d"
                subject = f"{session.name} — balance due tomorrow"
                body = f"Your balance of ${pkg.amount_due_cents / 100:.2f} is due tomorrow. Once paid, the delivery link opens."
            elif hours <= 0:
                kind = "invoice.overdue"
                subject = f"{session.name} — balance overdue"
                body = f"The balance of ${pkg.amount_due_cents / 100:.2f} is overdue. The delivery stays locked until it's paid."
            else:
                continue
            if _queue(
                db, session, kind,
                subject=subject,
                body=body,
                cta_path=f"/d/{pkg.delivery_token}" if pkg.delivery_token else f"/r/{token}",
                label=CTA_LABELS[kind],
                dedup_key=f"{sid}:{kind}:{_day()}:p{pkg.id}",
            ):
                created += 1

        # --- change_order.quote_expiring: quote expires within 48h -------------
        for co in session.change_orders:
            if co.status != "quoted" or not co.quote_expires_at:
                continue
            hours = _hours_until(co.quote_expires_at)
            if hours is not None and 0 <= hours <= 48:
                price = f"${co.price_cents / 100:.2f}" if co.price_cents else "—"
                if _queue(
                    db, session, "change_order.quote_expiring",
                    subject=f"{session.name} — your quote ({price}) expires soon",
                    body=f"The quote for your change request expires within 48 hours. Accept it to reopen the round and schedule the work.",
                    cta_path=f"/r/{token}?co={co.id}",
                    label=CTA_LABELS["change_order.quote_expiring"],
                    dedup_key=f"{sid}:change_order.quote_expiring:{_day()}:co{co.id}",
                ):
                    created += 1

        # --- archive: files expire within 30d / 7d ------------------------------
        for pkg in session.release_packages:
            if pkg.archive_status not in ("available_now", "needs_preparation") or not pkg.archive_expires_at:
                continue
            days = (_as_utc(pkg.archive_expires_at) - _now()).days
            if 7 < days <= 30:
                kind = "archive.expiring_30d"
                subject = f"{session.name} — archived files expire in 30 days"
                body = "The archived session files expire within 30 days. Download anything you need before they're purged."
            elif 0 <= days <= 7:
                kind = "archive.expiring_7d"
                subject = f"{session.name} — archived files expire in 7 days"
                body = "The archived session files expire within 7 days. Download anything you need before they're purged."
            else:
                continue
            if _queue(
                db, session, kind,
                subject=subject,
                body=body,
                cta_path=f"/d/{pkg.delivery_token}" if pkg.delivery_token else f"/r/{token}",
                label=CTA_LABELS[kind],
                dedup_key=f"{sid}:{kind}:{_day()}:p{pkg.id}",
            ):
                created += 1

        # --- delivery.link_expiring: link expires within 7 days -----------------
        for pkg in session.release_packages:
            if not pkg.delivery_token or pkg.status not in ("ready", "delivered"):
                continue
            if not session.share_expires_at:
                continue
            days = (_as_utc(session.share_expires_at) - _now()).days
            if 0 <= days <= 7 and _queue(
                db, session, "delivery.link_expiring",
                subject=f"{session.name} — delivery link expires in {days + 1} days",
                body=f"Your delivery link for {pkg.name} expires in {days + 1} days. Download your files before it closes.",
                cta_path=f"/d/{pkg.delivery_token}",
                label=CTA_LABELS["delivery.link_expiring"],
                dedup_key=f"{sid}:delivery.link_expiring:{_day()}:p{pkg.id}",
            ):
                created += 1

    return {"evaluated": evaluated, "created": created}


def _deliver(msg) -> None:
    """Transport: send one EmailMessage via SMTP; raises on any failure.

    Port 465 → implicit TLS (`SMTP_SSL`, used by Resend's relay). Any other
    port (587/25) → STARTTLS when the server offers it, falling back to a
    plain-text relay for local dev. The caller marks the notification failed
    on exception.
    """
    import smtplib

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
            pass  # no TLS offered — plain relay (dev only)
        if config.SMTP_USER:
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(msg)


def _smtp_send(notification: Notification) -> None:
    """Deliver via SMTP; raises on any failure (caller marks notification.failed)."""
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = notification.subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = notification.recipient
    msg.set_content(f"{notification.body}\n\n{notification.cta_label}: {notification.cta_url}")
    _deliver(msg)


def send_pending(db: Session) -> dict:
    """Deliver queued notifications (SMTP when configured, log-only otherwise)."""
    sent = failed = 0
    rows = db.scalars(select(Notification).where(Notification.status == "queued")).all()
    for n in rows:
        try:
            if config.SMTP_HOST:
                _smtp_send(n)
            else:
                # MVP transport: log-only until an email provider is wired up.
                _logger.info("[reminders] %s → %s: %s (%s)", n.kind, n.recipient, n.subject, n.cta_url)
            n.status = "sent"
            n.sent_at = _now()
            sent += 1
            ledger.append(
                db,
                "notification.sent",
                session_id=n.session_id,
                actor="reminders",
                entity_type="notification",
                entity_id=n.id,
                payload={"kind": n.kind, "recipient": n.recipient, "channel": n.channel},
            )
        except Exception as exc:  # transport failure — keep the queue honest
            n.status = "failed"
            n.error = str(exc)[:500]
            failed += 1
            ledger.append(
                db,
                "notification.failed",
                session_id=n.session_id,
                actor="reminders",
                entity_type="notification",
                entity_id=n.id,
                payload={"kind": n.kind, "recipient": n.recipient, "channel": n.channel, "error": str(exc)[:200]},
            )
    return {"sent": sent, "failed": failed}


def dismiss_pending(db: Session, session_id: int, actor: str = "client") -> dict:
    """Client opt-out: cancel queued non-transactional reminders for a session."""
    dismissed = 0
    rows = db.scalars(
        select(Notification).where(
            Notification.session_id == session_id,
            Notification.status == "queued",
        )
    ).all()
    for n in rows:
        if n.kind in TRANSACTIONAL_KINDS:
            continue
        n.status = "dismissed"
        dismissed += 1
        ledger.append(
            db,
            "notification.dismissed",
            session_id=session_id,
            actor=actor,
            entity_type="notification",
            entity_id=n.id,
            payload={"kind": n.kind, "recipient": n.recipient, "channel": n.channel},
        )
    return {"dismissed": dismissed}


def run_all(db: Session) -> dict:
    """evaluate + send — used by the /api/reminders/evaluate endpoint and cron."""
    ev = evaluate(db)
    sn = send_pending(db)
    return {**ev, **sn, "dismissed": 0}
