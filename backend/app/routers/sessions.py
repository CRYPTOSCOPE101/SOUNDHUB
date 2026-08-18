"""Review sessions — the core review loop for music production."""
import secrets
from pathlib import PurePosixPath

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import not_found, session_or_404
from ..config import MAX_UPLOAD_SIZE
from ..database import get_db
from ..models import (
    LedgerEvent,
    ReviewApproval,
    ReviewComment,
    ReviewRound,
    ReviewSession,
    ReviewVersion,
    ShareAccessEvent,
    User,
    utcnow,
)
from ..schemas import (
    CheckoutOut,
    GuestReviewCommentCreate,
    ReviewApprovalCreate,
    ReviewBriefUpdate,
    ReviewApprovalOut,
    ReviewCommentCreate,
    ReviewCommentOut,
    ReviewRequestStatusUpdate,
    ReviewRoundOut,
    ReviewRoundSubmit,
    ReviewSessionCreate,
    ReviewSessionDetailOut,
    ReviewSessionOut,
    ReviewStatusUpdate,
    ShareAccessEventOut,
    ShareSettingsUpdate,
    ReviewVersionOut,
    VersionDiffOut,
)
from ..security import get_current_user
from ..services import ledger, storage, versioning, watermark, waveform

router = APIRouter(prefix="/api/sessions", tags=["review sessions"])

ALLOWED_AUDIO = {"wav", "mp3", "flac", "ogg", "aif", "aiff", "m4a"}


def get_session_or_404(db: Session, user: User, session_id: int) -> ReviewSession:
    return session_or_404(db, session_id, user)


def get_version_or_404(db: Session, session_id: int, version_id: int) -> ReviewVersion:
    version = db.get(ReviewVersion, version_id)
    if version is None or version.session_id != session_id:
        raise not_found("Version")
    return version


def next_version_number(db: Session, session_id: int) -> int:
    return (
        db.scalar(
            select(ReviewVersion.number)
            .where(ReviewVersion.session_id == session_id)
            .order_by(ReviewVersion.number.desc())
            .limit(1)
        )
        or 0
    ) + 1


def _comment_out(c: ReviewComment) -> ReviewCommentOut:
    name = c.author_name or (c.author.username if c.author else "Reviewer")
    return ReviewCommentOut(
        id=c.id,
        version_id=c.version_id,
        time_s=c.time_s,
        body=c.body,
        resolved=c.resolved,
        author_name=name,
        parent_id=c.parent_id,
        created_at=c.created_at,
        status=c.status,
        fixed_in=c.fixed_in,
        verified_at=c.verified_at,
        voice_format=c.voice_format or "",
        voice_duration_s=c.voice_duration_s or 0.0,
        transcript=c.transcript or "",
    )


def _version_out(db: Session, v: ReviewVersion, with_comments: bool = False) -> ReviewVersionOut:
    data = storage.read_blob(v.blob_sha)
    wf = waveform.generate(v.blob_sha, data, v.filename, v.audio_format)
    comments = [_comment_out(c) for c in v.comments] if with_comments else []
    session = db.get(ReviewSession, v.session_id)
    watermarked = bool(session and session.watermark_enabled and v.status != "approved")
    return ReviewVersionOut(
        id=v.id,
        session_id=v.session_id,
        number=v.number,
        label=v.label,
        message=v.message,
        status=v.status,
        filename=v.filename,
        size=v.size,
        duration_s=wf["duration_s"],
        audio_format=v.audio_format,
        created_at=v.created_at,
        round_number=v.round_number,
        waveform=wf["peaks"],
        waveform_synthetic=wf["synthetic"],
        comments=comments,
        watermarked=watermarked,
        commit_id=v.commit_id,
    )


def _session_out(db: Session, s: ReviewSession) -> ReviewSessionOut:
    versions = db.scalars(
        select(ReviewVersion)
        .where(ReviewVersion.session_id == s.id)
        .order_by(ReviewVersion.number.desc())
    ).all()
    latest = versions[0] if versions else None
    return ReviewSessionOut(
        id=s.id,
        project_id=s.project_id,
        name=s.name,
        status=s.status,
        share_token=s.share_token,
        created_at=s.created_at,
        updated_at=s.updated_at,
        owner_username=s.owner.username if s.owner else "",
        version_count=len(versions),
        latest_status=latest.status if latest else "",
    )


def _session_detail(db: Session, s: ReviewSession, with_comments: bool = True) -> ReviewSessionDetailOut:
    versions = db.scalars(
        select(ReviewVersion)
        .where(ReviewVersion.session_id == s.id)
        .order_by(ReviewVersion.number.desc())
    ).all()
    out = _session_out(db, s)
    approvals = db.scalars(
        select(ReviewApproval)
        .where(ReviewApproval.session_id == s.id)
        .order_by(ReviewApproval.created_at.desc())
    ).all()
    events = db.scalars(
        select(ShareAccessEvent)
        .where(ShareAccessEvent.session_id == s.id)
        .order_by(ShareAccessEvent.created_at.desc())
        .limit(50)
    ).all()
    rounds = db.scalars(
        select(ReviewRound)
        .where(ReviewRound.session_id == s.id)
        .order_by(ReviewRound.number.desc())
    ).all()
    return ReviewSessionDetailOut(
        **out.model_dump(),
        versions=[_version_out(db, v, with_comments=with_comments) for v in versions],
        approvals=[ReviewApprovalOut.model_validate(a, from_attributes=True) for a in approvals],
        access_events=[ShareAccessEventOut.model_validate(e, from_attributes=True) for e in events],
        rounds=[ReviewRoundOut.model_validate(r, from_attributes=True) for r in rounds],
        share_expires_at=s.share_expires_at,
        share_permission=s.share_permission,
        share_has_password=bool(s.share_password),
        share_allowlist=s.share_allowlist,
        round_number=s.round_number,
        feedback_due_at=s.feedback_due_at,
        feedback_owner=s.feedback_owner,
        included_rounds=s.included_rounds,
        rounds_open=s.rounds_open,
        deposit_due_cents=s.deposit_due_cents,
        deposit_status=s.deposit_status,
        extra_round_price_cents=s.extra_round_price_cents,
        rounds_paid=s.rounds_paid,
        portfolio_public=s.portfolio_public,
        watermark_enabled=s.watermark_enabled,
        retention_until=s.retention_until,
        recall_fee_cents=s.recall_fee_cents,
        revision_fee_cents=s.revision_fee_cents,
        change_rounds_granted=s.change_rounds_granted,
        approval_preset=s.approval_preset,
        members=[
            {"id": m.id, "session_id": m.session_id, "email": m.email, "role": m.role, "invited_by": m.invited_by, "created_at": m.created_at}
            for m in s.members
        ],
        service_type=s.service_type,
        genre=s.genre,
        goal=s.goal,
        deadline_at=s.deadline_at,
        review_start_at=s.review_start_at,
        reference_links=s.reference_links,
        do_not_change=s.do_not_change,
        required_deliverables=s.required_deliverables,
    )


def _check_share_access(session: ReviewSession, actor: str = "", password: str | None = None) -> None:
    from datetime import datetime, timezone
    if session.share_expires_at and session.share_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This review link has expired")
    if session.share_password and (password or "") != session.share_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This review link is password protected")
    if session.share_allowlist.strip():
        allowed = {e.strip().lower() for e in session.share_allowlist.split(",") if e.strip()}
        if actor and actor.strip().lower() not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your email is not on the access list")


def _require_share_permission(session: ReviewSession, needed: str, actor: str = "", password: str | None = None) -> None:
    _check_share_access(session, actor, password)
    order = {"view": 0, "comment": 1, "download": 2}
    if order.get(session.share_permission, 1) < order[needed]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"This review link does not allow {needed}")


def _log_access(db: Session, session: ReviewSession, actor: str, action: str, detail: str = "") -> None:
    db.add(ShareAccessEvent(session_id=session.id, actor=actor or "anonymous", action=action, detail=detail))


# ---------- public share endpoints ----------

def get_public_session(db: Session, share_token: str) -> ReviewSession:
    session = db.scalar(select(ReviewSession).where(ReviewSession.share_token == share_token))
    if session is None:
        raise not_found("Review link")
    return session


@router.get("/public/{share_token}", response_model=ReviewSessionDetailOut)
def public_session(share_token: str, actor: str = "", password: str | None = None, db: Session = Depends(get_db)):
    session = get_public_session(db, share_token)
    _check_share_access(session, actor, password)
    _log_access(db, session, actor, "opened")
    db.commit()
    return _session_detail(db, session)


@router.get("/public/{share_token}/versions/{version_id}/audio")
def public_download_audio(share_token: str, version_id: int, actor: str = "", password: str | None = None, db: Session = Depends(get_db)):
    session = get_public_session(db, share_token)
    _require_share_permission(session, "download", actor, password)
    version = get_version_or_404(db, session.id, version_id)
    data = storage.read_blob(version.blob_sha)
    if session.watermark_enabled and version.status != "approved":
        data = watermark.watermarked_blob(db, version)
    _log_access(db, session, actor, "downloaded", version.label)
    db.commit()
    return Response(
        content=data,
        media_type=f"audio/{version.audio_format}",
        headers={"Content-Disposition": f'inline; filename="{version.filename}"'},
    )


@router.get("/public/{share_token}/versions/{version_id}/diff", response_model=VersionDiffOut)
def public_version_diff(share_token: str, version_id: int, actor: str = "", password: str | None = None, db: Session = Depends(get_db)):
    session = get_public_session(db, share_token)
    _check_share_access(session, actor, password)
    version = get_version_or_404(db, session.id, version_id)
    _log_access(db, session, actor, "diffed", f"{version.label}")
    db.commit()
    return {"version_label": version.label, "from_label": None, "has_daw": False}


@router.post("/public/{share_token}/versions/{version_id}/comments", response_model=ReviewCommentOut, status_code=status.HTTP_201_CREATED)
def guest_comment(share_token: str, version_id: int, payload: GuestReviewCommentCreate, password: str | None = None, db: Session = Depends(get_db)):
    session = get_public_session(db, share_token)
    _require_share_permission(session, "comment", payload.author_name, password)
    if not session.rounds_open:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This revision round is closed")
    version = get_version_or_404(db, session.id, version_id)
    if payload.parent_id:
        parent = db.get(ReviewComment, payload.parent_id)
        if parent is None or parent.version_id != version.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parent comment not found")
    comment = ReviewComment(
        version_id=version.id,
        author_name=payload.author_name.strip()[:128] or "Reviewer",
        time_s=payload.time_s,
        body=payload.body.strip(),
        parent_id=payload.parent_id,
        status="open",
    )
    db.add(comment)
    _log_access(db, session, payload.author_name, "commented", f"{version.label} @ {payload.time_s:.1f}s")
    ledger.append(db, "request.created", session_id=session.id, actor=payload.author_name, entity_type="request", entity_id=comment.id, payload={"version": version.label, "time_s": payload.time_s})
    session.updated_at = utcnow()
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)


@router.post("/public/{share_token}/versions/{version_id}/approvals", response_model=ReviewApprovalOut, status_code=status.HTTP_201_CREATED)
def guest_approve(share_token: str, version_id: int, payload: ReviewApprovalCreate, password: str | None = None, db: Session = Depends(get_db)):
    session = get_public_session(db, share_token)
    _require_share_permission(session, "comment", payload.approver_name, password)
    version = get_version_or_404(db, session.id, version_id)
    if not payload.approved and not payload.note.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A 'needs changes' decision requires a note")
    approval = ReviewApproval(
        session_id=session.id,
        version_id=version.id,
        scope=payload.scope,
        approved=payload.approved,
        note=payload.note.strip(),
        approver_name=payload.approver_name.strip()[:128] or "Reviewer",
    )
    db.add(approval)
    _log_access(db, session, payload.approver_name, "approved" if payload.approved else "needs_changes", f"{version.label} · {payload.scope}")
    version.status = "approved" if payload.approved else "needs_changes"
    session.status = version.status
    session.updated_at = utcnow()
    ledger.append(db, "approval.created", session_id=session.id, actor=payload.approver_name, entity_type="approval", entity_id=approval.id, payload={"version": version.label, "scope": payload.scope, "approved": payload.approved})
    db.commit()
    db.refresh(approval)
    return ReviewApprovalOut.model_validate(approval, from_attributes=True)


# ---------- owner endpoints ----------

@router.get("", response_model=list[ReviewSessionOut])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.scalars(
        select(ReviewSession).where(ReviewSession.owner_id == user.id).order_by(ReviewSession.updated_at.desc())
    ).all()
    return [_session_out(db, s) for s in sessions]


@router.post("", response_model=ReviewSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: ReviewSessionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = ReviewSession(
        owner_id=user.id,
        project_id=payload.project_id,
        name=payload.name.strip(),
        share_token=secrets.token_urlsafe(16),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(db, session)


@router.get("/{session_id}", response_model=ReviewSessionDetailOut)
def get_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_or_404(db, user, session_id)
    return _session_detail(db, session)


@router.patch("/{session_id}/share", response_model=ReviewSessionDetailOut)
def update_share_settings(session_id: int, payload: ShareSettingsUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_or_404(db, user, session_id)
    if payload.share_password is not None:
        session.share_password = payload.share_password.strip() or None
    session.share_expires_at = payload.share_expires_at
    if payload.share_permission is not None:
        session.share_permission = payload.share_permission
    if payload.share_allowlist is not None:
        session.share_allowlist = payload.share_allowlist.strip()
    if payload.feedback_owner is not None:
        session.feedback_owner = payload.feedback_owner.strip()
    if payload.included_rounds is not None:
        session.included_rounds = payload.included_rounds
    if payload.rounds_open is not None:
        session.rounds_open = payload.rounds_open
    if payload.feedback_due_at is not None:
        session.feedback_due_at = payload.feedback_due_at
    if payload.deposit_due_cents is not None:
        session.deposit_due_cents = payload.deposit_due_cents
        if payload.deposit_due_cents > 0 and session.deposit_status == "none":
            session.deposit_status = "deposit_due"
    if payload.deposit_status is not None:
        session.deposit_status = payload.deposit_status
    if payload.extra_round_price_cents is not None:
        session.extra_round_price_cents = payload.extra_round_price_cents
    if payload.rounds_paid is not None:
        session.rounds_paid = payload.rounds_paid
    if payload.portfolio_public is not None:
        session.portfolio_public = payload.portfolio_public
    if payload.watermark_enabled is not None:
        session.watermark_enabled = payload.watermark_enabled
    if payload.retention_until is not None:
        session.retention_until = payload.retention_until
    if payload.recall_fee_cents is not None:
        session.recall_fee_cents = payload.recall_fee_cents
    if payload.revision_fee_cents is not None:
        session.revision_fee_cents = payload.revision_fee_cents
    db.commit()
    return _session_detail(db, session)


@router.patch("/{session_id}/brief", response_model=ReviewSessionDetailOut)
def update_brief(session_id: int, payload: ReviewBriefUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_or_404(db, user, session_id)
    session.service_type = payload.service_type
    session.genre = payload.genre.strip()
    session.goal = payload.goal.strip()
    session.deadline_at = payload.deadline_at
    session.review_start_at = payload.review_start_at
    session.reference_links = payload.reference_links.strip()
    session.do_not_change = payload.do_not_change.strip()
    session.required_deliverables = payload.required_deliverables.strip()
    session.updated_at = utcnow()
    ledger.append(db, "brief.updated", session_id=session.id, actor=user.username, entity_type="session", entity_id=session.id, payload={"service_type": payload.service_type, "genre": payload.genre.strip()[:80]})
    db.commit()
    return _session_detail(db, session)


@router.post("/{session_id}/versions", response_model=ReviewVersionOut, status_code=status.HTTP_201_CREATED)
def upload_version(session_id: int, message: str = Form(""), file: UploadFile = File(...), background: BackgroundTasks = BackgroundTasks(), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_or_404(db, user, session_id)
    filename = PurePosixPath((file.filename or "audio.wav").replace("\\", "/")).name
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_AUDIO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported audio format '{ext}'")
    try:
        data = storage.put_upload_file(file, MAX_UPLOAD_SIZE)
    except ValueError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))

    blob_sha = storage.put_blob(data)
    wf = waveform.generate(blob_sha, data, filename, ext)
    number = next_version_number(db, session.id)
    version = ReviewVersion(
        session_id=session.id,
        number=number,
        label=f"v{number}",
        message=message.strip(),
        filename=filename,
        blob_sha=blob_sha,
        size=len(data),
        duration_s=wf["duration_s"],
        audio_format=ext,
        round_number=session.round_number,
    )
    db.add(version)
    db.flush()

    open_reqs = db.scalars(
        select(ReviewComment)
        .join(ReviewVersion, ReviewComment.version_id == ReviewVersion.id)
        .where(
            ReviewVersion.session_id == session.id,
            ReviewComment.status.in_(["open", "acknowledged", "in_progress"]),
            ReviewComment.fixed_in.is_(None),
        )
    ).all()
    for c in open_reqs:
        c.status = "fixed"
        c.fixed_in = version.id

    session.rounds_open = True
    session.updated_at = utcnow()
    ledger.append(db, "version.created", session_id=session.id, actor=user.username, entity_type="version", entity_id=version.id, payload={"label": version.label, "round": version.round_number, "fixed_requests": len(open_reqs)})
    db.commit()
    db.refresh(version)
    return _version_out(db, version)


@router.get("/{session_id}/versions/{version_id}/audio")
def download_audio(session_id: int, version_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_session_or_404(db, user, session_id)
    version = get_version_or_404(db, session_id, version_id)
    data = storage.read_blob(version.blob_sha)
    return Response(
        content=data,
        media_type=f"audio/{version.audio_format}",
        headers={"Content-Disposition": f'inline; filename="{version.filename}"'},
    )


@router.post("/{session_id}/versions/{version_id}/comments", response_model=ReviewCommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(session_id: int, version_id: int, payload: ReviewCommentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_session_or_404(db, user, session_id)
    version = get_version_or_404(db, session_id, version_id)
    comment = ReviewComment(
        version_id=version.id,
        author_id=user.id,
        time_s=payload.time_s,
        body=payload.body.strip(),
        parent_id=payload.parent_id,
    )
    db.add(comment)
    ledger.append(db, "request.created", session_id=session_id, actor=user.username, entity_type="request", entity_id=comment.id, payload={"version": version.label, "time_s": payload.time_s})
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)


@router.patch("/{session_id}/versions/{version_id}/comments/{comment_id}", response_model=ReviewCommentOut)
def update_comment(session_id: int, version_id: int, comment_id: int, resolved: bool | None = None, body: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_session_or_404(db, user, session_id)
    version = get_version_or_404(db, session_id, version_id)
    comment = db.get(ReviewComment, comment_id)
    if comment is None or comment.version_id != version.id:
        raise not_found("Comment")
    if resolved is not None:
        comment.resolved = resolved
    if body is not None:
        comment.body = body.strip()
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)


@router.post("/{session_id}/versions/{version_id}/status", response_model=ReviewVersionOut)
def update_version_status(session_id: int, version_id: int, payload: ReviewStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_session_or_404(db, user, session_id)
    version = get_version_or_404(db, session_id, version_id)
    version.status = payload.status
    session = db.get(ReviewSession, session_id)
    if session:
        session.status = payload.status
        session.updated_at = utcnow()
    db.commit()
    return _version_out(db, version)


@router.post("/{session_id}/status", response_model=ReviewSessionDetailOut)
def update_session_status(session_id: int, payload: ReviewStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_or_404(db, user, session_id)
    session.status = payload.status
    session.updated_at = utcnow()
    db.commit()
    return _session_detail(db, session)


@router.get("/{session_id}/ledger")
def get_ledger(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_session_or_404(db, user, session_id)
    rows = db.scalars(
        select(LedgerEvent).where(LedgerEvent.session_id == session_id).order_by(LedgerEvent.id)
    ).all()
    return {
        "events": [
            {
                "id": e.id,
                "event": e.event,
                "actor": e.actor,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "payload": e.payload,
                "occurred_at": e.occurred_at.isoformat(),
                "prev_event_hash": e.prev_event_hash,
                "event_hash": e.event_hash,
            }
            for e in rows
        ],
        "head_hash": rows[-1].event_hash if rows else None,
    }


@router.get("/{session_id}/ledger/verify")
def verify_ledger(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_session_or_404(db, user, session_id)
    return ledger.verify_history(db, session_id=session_id)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_or_404(db, user, session_id)
    db.delete(session)
    db.commit()
