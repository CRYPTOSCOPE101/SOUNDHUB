"""Review sessions — the core review loop for music production."""
import hmac
import secrets
from pathlib import PurePosixPath

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

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
    FileSnapshot,
    Commit,
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
    session = db.get(ReviewSession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


def get_version_or_404(db: Session, session_id: int, version_id: int) -> ReviewVersion:
    version = db.get(ReviewVersion, version_id)
    if version is None or version.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
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
    if session.share_password and not hmac.compare_digest(password or "", session.share_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This review link is password protected")
    if session.share_allowlist.strip():
        allowed = {e.strip().lower() for e in session.share_allowlist.split(",") if e.strip()}
        if actor.strip().lower() not in allowed:
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
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review link not found")
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

    # Get the previous version in the same session (by number)
    prev_version = db.scalar(
        select(ReviewVersion)
        .where(
            ReviewVersion.session_id == session.id,
            ReviewVersion.number < version.number
        )
        .order_by(ReviewVersion.number.desc())
        .limit(1)
    )

    # Get DAW info for both versions if they have commits
    info_a = None
    info_b = None

    if prev_version and prev_version.commit_id:
        from ..services.daw.registry import get_daw_info
        from ..services.versioning import tree_files
        commit_a = db.get(Commit, prev_version.commit_id)
        if commit_a:
            tree_a = tree_files(db, commit_a)
            for snap in tree_a:
                if snap.path.lower().endswith(('.als', '.cpr', '.rpp', '.flp', '.logic', '.ptx', '.band')):
                    try:
                        data = storage.read_blob(snap.blob_sha)
                        info_a = get_daw_info(snap.path, data)
                        break
                    except Exception:
                        pass

    if version.commit_id:
        from ..services.daw.registry import get_daw_info
        from ..services.versioning import tree_files
        commit_b = db.get(Commit, version.commit_id)
        if commit_b:
            tree_b = tree_files(db, commit_b)
            for snap in tree_b:
                if snap.path.lower().endswith(('.als', '.cpr', '.rpp', '.flp', '.logic', '.ptx', '.band')):
                    try:
                        data = storage.read_blob(snap.blob_sha)
                        info_b = get_daw_info(snap.path, data)
                        break
                    except Exception:
                        pass

    # Generate summary diff
    from ..services.daw.diff_engine import summary_diff
    summary_raw = summary_diff(info_a, info_b)

    # Convert to the expected list format
    summary = []
    # Handle the case of no previous version (first version)
    if info_a is None and info_b is not None:
        summary.append({"label": "File created"})
    else:
        if "bpm" in summary_raw:
            bpm_diff = summary_raw["bpm"]
            old_val = bpm_diff.get("before")
            new_val = bpm_diff.get("after")
            # If the value is a float and represents an integer, convert to int to remove decimal
            if isinstance(old_val, float) and old_val.is_integer():
                old_val = int(old_val)
            if isinstance(new_val, float) and new_val.is_integer():
                new_val = int(new_val)
            summary.append({
                "kind": "bpm",
                "old": str(old_val),
                "new": str(new_val)
            })
        if "time_signature" in summary_raw:
            ts_diff = summary_raw["time_signature"]
            summary.append({
                "kind": "time_signature",
                "old": str(ts_diff.get("before")),
                "new": str(ts_diff.get("after"))
            })
        if "tracks" in summary_raw:
            tracks_diff = summary_raw["tracks"]
            for track in tracks_diff.get("added", []):
                summary.append({
                    "kind": "track_added",
                    "new": track
                })
            for track in tracks_diff.get("removed", []):
                summary.append({
                    "kind": "track_removed",
                    "old": track
                })
        if "plugins" in summary_raw:
            plugins_diff = summary_raw["plugins"]
            for plugin in plugins_diff.get("added", []):
                summary.append({
                    "kind": "plugin_added",
                    "new": plugin
                })
            for plugin in plugins_diff.get("removed", []):
                summary.append({
                    "kind": "plugin_removed",
                    "old": plugin
                })

    # Determine the path and format for the DAW file
    path = None
    fmt = None
    has_daw = False

    # Prefer info_b (current version) for path/format
    if info_b:
        path = info_b.get("path")
        # Extract file extension from path
        if path and "." in path:
            fmt = path.rsplit(".", 1)[-1].lower()
        else:
            fmt = info_b.get("format")
        has_daw = bool(path and fmt)
    elif info_a:
        path = info_a.get("path")
        # Extract file extension from path
        if path and "." in path:
            fmt = path.rsplit(".", 1)[-1].lower()
        else:
            fmt = info_a.get("format")
        has_daw = bool(path and fmt)

    # Generate raw text diff if we have DAW files
    raw = ""
    truncated = False
    if info_a and info_b:
        from ..services.daw.diff_engine import unified_diff, normalize_content
        try:
            # Get the DAW file content for both versions
            data_a = storage.read_blob(
                db.scalar(
                    select(FileSnapshot.blob_sha)
                    .where(
                        FileSnapshot.commit_id == prev_version.commit_id,
                        FileSnapshot.path == path,
                    )
                )
            ) if prev_version and prev_version.commit_id and path else b""
            data_b = storage.read_blob(
                db.scalar(
                    select(FileSnapshot.blob_sha)
                    .where(
                        FileSnapshot.commit_id == version.commit_id,
                        FileSnapshot.path == path,
                    )
                )
            ) if version.commit_id and path else b""
            text_a = normalize_content(path, data_a) if path else ""
            text_b = normalize_content(path, data_b) if path else ""
            raw, truncated = unified_diff(text_a, text_b)
        except Exception:
            raw = ""
            truncated = False

    # Get the "from" label
    from_label = prev_version.label if prev_version else None

    return VersionDiffOut(
        version_label=version.label,
        from_label=from_label,
        path=path,
        format=fmt,
        has_daw=has_daw,
        summary=summary,
        raw=raw,
        truncated=truncated,
    )


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

    # Create a ReviewRound if one doesn't exist for the current round number
    existing_round = db.scalar(
        select(ReviewRound).where(
            ReviewRound.session_id == session.id,
            ReviewRound.number == session.round_number,
        )
    )
    if existing_round is None:
        db.add(ReviewRound(
            session_id=session.id,
            number=session.round_number,
            status="open",
        ))

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


@router.get("/{session_id}/versions/{version_id}/diff", response_model=VersionDiffOut)
def version_diff(session_id: int, version_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_or_404(db, user, session_id)
    version = get_version_or_404(db, session_id, version_id)
    if version.commit_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no linked daw project")

    # Get the previous version in the same session (by number)
    prev_version = db.scalar(
        select(ReviewVersion)
        .where(
            ReviewVersion.session_id == session.id,
            ReviewVersion.number < version.number
        )
        .order_by(ReviewVersion.number.desc())
        .limit(1)
    )

    # Get DAW info for both versions if they have commits
    info_a = None
    info_b = None
    path_a = None
    path_b = None

    if prev_version and prev_version.commit_id:
        from ..services.daw.registry import get_daw_info
        from ..services.versioning import tree_files
        commit_a = db.get(Commit, prev_version.commit_id)
        if commit_a:
            tree_a = tree_files(db, commit_a)
            for snap in tree_a:
                if snap.path.lower().endswith(('.als', '.cpr', '.rpp', '.flp', '.logic', '.ptx', '.band')):
                    try:
                        data = storage.read_blob(snap.blob_sha)
                        info_a = get_daw_info(snap.path, data)
                        path_a = snap.path
                        break
                    except Exception:
                        pass

    if version.commit_id:
        from ..services.daw.registry import get_daw_info
        from ..services.versioning import tree_files
        commit_b = db.get(Commit, version.commit_id)
        if commit_b:
            tree_b = tree_files(db, commit_b)
            for snap in tree_b:
                if snap.path.lower().endswith(('.als', '.cpr', '.rpp', '.flp', '.logic', '.ptx', '.band')):
                    try:
                        data = storage.read_blob(snap.blob_sha)
                        info_b = get_daw_info(snap.path, data)
                        path_b = snap.path
                        break
                    except Exception:
                        pass

    # Generate summary diff
    from ..services.daw.diff_engine import summary_diff
    summary_raw = summary_diff(info_a, info_b)

    # Convert to the expected list format
    summary = []
    # Handle the case of no previous version (first version)
    if info_a is None and info_b is not None:
        summary.append({"label": "File created"})
    else:
        if "bpm" in summary_raw:
            bpm_diff = summary_raw["bpm"]
            old_val = bpm_diff.get("before")
            new_val = bpm_diff.get("after")
            # If the value is a float and represents an integer, convert to int to remove decimal
            if isinstance(old_val, float) and old_val.is_integer():
                old_val = int(old_val)
            if isinstance(new_val, float) and new_val.is_integer():
                new_val = int(new_val)
            summary.append({
                "kind": "bpm",
                "old": str(old_val),
                "new": str(new_val)
            })
        if "time_signature" in summary_raw:
            ts_diff = summary_raw["time_signature"]
            summary.append({
                "kind": "time_signature",
                "old": str(ts_diff.get("before")),
                "new": str(ts_diff.get("after"))
            })
        if "tracks" in summary_raw:
            tracks_diff = summary_raw["tracks"]
            for track in tracks_diff.get("added", []):
                summary.append({
                    "kind": "track_added",
                    "new": track
                })
            for track in tracks_diff.get("removed", []):
                summary.append({
                    "kind": "track_removed",
                    "old": track
                })
        if "plugins" in summary_raw:
            plugins_diff = summary_raw["plugins"]
            for plugin in plugins_diff.get("added", []):
                summary.append({
                    "kind": "plugin_added",
                    "new": plugin
                })
            for plugin in plugins_diff.get("removed", []):
                summary.append({
                    "kind": "plugin_removed",
                    "old": plugin
                })

    # Determine the path and format for the DAW file
    path = None
    fmt = None
    has_daw = False

    # Prefer info_b (current version) for path/format
    if info_b:
        path = path_b
        # Extract file extension from path
        if path and "." in path:
            fmt = path.rsplit(".", 1)[-1].lower()
        else:
            fmt = info_b.get("format")
        has_daw = bool(path and fmt)
    elif info_a:
        path = path_a
        # Extract file extension from path
        if path and "." in path:
            fmt = path.rsplit(".", 1)[-1].lower()
        else:
            fmt = info_a.get("format")
        has_daw = bool(path and fmt)

    # Generate raw text diff if we have DAW files
    raw = ""
    truncated = False
    if info_a and info_b:
        from ..services.daw.diff_engine import unified_diff, normalize_content
        try:
            # Get the DAW file content for both versions
            data_a = storage.read_blob(
                db.scalar(
                    select(FileSnapshot.blob_sha)
                    .where(
                        FileSnapshot.commit_id == prev_version.commit_id,
                        FileSnapshot.path == path,
                    )
                )
            ) if prev_version and prev_version.commit_id and path else b""
            data_b = storage.read_blob(
                db.scalar(
                    select(FileSnapshot.blob_sha)
                    .where(
                        FileSnapshot.commit_id == version.commit_id,
                        FileSnapshot.path == path,
                    )
                )
            ) if version.commit_id and path else b""
            text_a = normalize_content(path, data_a) if path else ""
            text_b = normalize_content(path, data_b) if path else ""
            raw, truncated = unified_diff(text_a, text_b)
        except Exception:
            raw = ""
            truncated = False

    # Get the "from" label
    from_label = prev_version.label if prev_version else None

    return VersionDiffOut(
        version_label=version.label,
        from_label=from_label,
        path=path,
        format=fmt,
        has_daw=has_daw,
        summary=summary,
        raw=raw,
        truncated=truncated,
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
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
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


# ---------- Stem endpoints (for version-based stem management) ----------

@router.get("/versions/{version_id}/stems", response_model=list[dict])
def list_version_stems(version_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all stems for a specific version."""
    version = db.get(ReviewVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    # Verify ownership through the session
    session = db.get(ReviewSession, version.session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    stems = db.scalars(
        select(StemAsset).where(StemAsset.version_id == version_id)
    ).all()

    return [
        {
            "id": stem.id,
            "logical_name": stem.logical_name,
            "display_name": stem.display_name,
            "blob_sha": stem.blob_sha,
            "size": stem.size,
            "audio_format": stem.audio_format,
            "start_offset_ms": stem.start_offset_ms,
            "created_at": stem.created_at,
        }
        for stem in stems
    ]


@router.post("/versions/{version_id}/stems", response_model=dict, status_code=status.HTTP_201_CREATED)
def upload_version_stem(
    version_id: int,
    logical_name: str = Form(...),
    display_name: str = Form(...),
    start_offset_ms: int = Form(0),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a stem to a specific version."""
    version = db.get(ReviewVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    # Verify ownership through the session
    session = db.get(ReviewSession, version.session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    try:
        data = storage.put_upload_file(file, MAX_UPLOAD_SIZE)
    except ValueError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))

    sha = storage.put_blob(data)
    stem = StemAsset(
        version_id=version_id,
        logical_name=logical_name,
        display_name=display_name,
        blob_sha=sha,
        size=len(data),
        audio_format=(file.filename or "stem.wav").rsplit(".", 1)[-1].lower(),
        start_offset_ms=start_offset_ms,
    )
    db.add(stem)
    db.commit()
    db.refresh(stem)

    return {
        "id": stem.id,
        "blob_sha": stem.blob_sha,
    }


@router.get("/versions/{version_id}/stems/{stem_id}/audio")
def get_stem_audio(
    version_id: int,
    stem_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the audio blob for a specific stem."""
    version = db.get(ReviewVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    # Verify ownership through the session
    session = db.get(ReviewSession, version.session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")

    stem = db.get(StemAsset, stem_id)
    if stem is None or stem.version_id != version_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stem not found")

    data = storage.read_blob(stem.blob_sha)
    return Response(
        content=data,
        media_type=f"audio/{stem.audio_format}",
        headers={"Content-Disposition": f'inline; filename="{stem.display_name}"'},
    )


# ---------- Submit feedback (close round) ----------


class SubmitFeedbackPayload(BaseModel):
    note: str = Field(default="", max_length=2000)


@router.post("/public/{share_token}/submit-feedback")
def submit_feedback(
    share_token: str,
    actor: str = Query(""),
    payload: SubmitFeedbackPayload = SubmitFeedbackPayload(),
    password: str | None = None,
    db: Session = Depends(get_db),
):
    """Guest submits feedback — closes the current review round.

    Business rules:
    - A round must already be open (created by upload_version or owner).
    - No round is auto-created: the owner must start the round first.
    - Calling submit-feedback on an already-closed round returns 409.
    """
    session = get_public_session(db, share_token)
    _require_share_permission(session, "comment", actor, password)

    if not session.rounds_open:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No open review round. The session owner must upload a new version to open a round before feedback can be submitted.",
        )

    # Find the open round — it must already exist (created by upload_version)
    current_round = db.scalar(
        select(ReviewRound)
        .where(
            ReviewRound.session_id == session.id,
            ReviewRound.status == "open",
        )
        .order_by(ReviewRound.number.desc())
        .limit(1)
    )
    if current_round is None:
        # Defensive: rounds_open is True but no open round exists — inconsistent state
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No open review round found. The session state is inconsistent; the owner should upload a new version.",
        )

    current_round.status = "submitted"
    current_round.submitted_at = utcnow()
    current_round.note = payload.note

    session.rounds_open = False
    session.round_number += 1
    session.updated_at = utcnow()
    _log_access(db, session, actor, "submitted_feedback", payload.note)
    ledger.append(db, "round.submitted", session_id=session.id, actor=actor, entity_type="round", entity_id=current_round.id, payload={"note": payload.note})
    db.commit()
    return {"ok": True, "round_number": session.round_number}


# ---------- Export open requests ----------


def _clock_fmt(seconds: float) -> str:
    """Format seconds as MM:SS.mmm."""
    m = int(seconds) // 60
    s = seconds - m * 60
    return f"{m}:{s:06.3f}"


@router.get("/{session_id}/requests/export")
def export_requests_owner(
    session_id: int,
    format: str = Query("markdown"),
    include_drafts: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Owner exports open requests as markdown or CSV."""
    session = get_session_or_404(db, user, session_id)
    return _export_requests(db, session, format, include_drafts)


@router.get("/public/{share_token}/requests/export")
def export_requests_public(
    share_token: str,
    format: str = Query("markdown"),
    include_drafts: bool = Query(False),
    actor: str = Query(""),
    password: str | None = None,
    db: Session = Depends(get_db),
):
    """Public export via share token (for M4L device)."""
    session = get_public_session(db, share_token)
    _require_share_permission(session, "comment", actor, password)
    _log_access(db, session, actor, "exported_requests")
    db.commit()
    return _export_requests(db, session, format, include_drafts)


def _export_requests(db: Session, session: ReviewSession, fmt: str, include_drafts: bool) -> Response:
    """Build markdown or CSV export of open review comments."""
    # Collect comments across all versions in this session
    versions = db.scalars(
        select(ReviewVersion).where(ReviewVersion.session_id == session.id).order_by(ReviewVersion.number)
    ).all()

    # Determine which rounds have been submitted
    submitted_rounds = {
        r.number
        for r in db.scalars(
            select(ReviewRound).where(
                ReviewRound.session_id == session.id,
                ReviewRound.status.in_(["submitted", "closed"]),
            )
        ).all()
    }

    rows: list[dict] = []
    for v in versions:
        comments = db.scalars(
            select(ReviewComment).where(ReviewComment.version_id == v.id)
        ).all()
        for c in comments:
            # Skip resolved
            if c.resolved:
                continue
            # A comment is a "draft" if its version's round was never submitted
            # round_number on the version tells us which round it belongs to
            is_draft = v.round_number not in submitted_rounds
            if not include_drafts and is_draft:
                continue
            rows.append({
                "version": v.label,
                "time_s": c.time_s,
                "clock": _clock_fmt(c.time_s),
                "author": c.author_name or "",
                "status": c.status,
                "body": c.body,
            })

    if fmt == "csv":
        import csv
        import io

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["version", "time_s", "clock", "author", "status", "body"])
        writer.writeheader()
        writer.writerows(rows)
        return Response(content=buf.getvalue(), media_type="text/csv")

    # Default: markdown
    lines = [f"# Open requests — {session.name}\n"]
    for r in rows:
        lines.append(f"- [{r['clock']}] {r['author']} — {r['body']}")
    if not rows:
        lines.append("_No open requests._")
    return Response(content="\n".join(lines) + "\n", media_type="text/markdown")


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = get_session_or_404(db, user, session_id)
    db.delete(session)
    db.commit()
