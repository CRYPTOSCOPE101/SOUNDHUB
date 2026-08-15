"""Review sessions — the Frame.io-style loop for music.

A session is a review workspace for a track. Producers upload audio versions
(WAV/MP3/stems), reviewers leave timestamped comments via a public share
link (no account, no wallet), and the producer moves versions through
In review → Needs changes → Approved.
"""

import secrets
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_SIZE
from ..database import get_db
from ..models import ReviewComment, ReviewSession, ReviewVersion, User, utcnow
from ..schemas import (
    GuestReviewCommentCreate,
    ReviewCommentCreate,
    ReviewCommentOut,
    ReviewSessionCreate,
    ReviewSessionDetailOut,
    ReviewSessionOut,
    ReviewStatusUpdate,
    ReviewVersionCreate,
    ReviewVersionOut,
)
from ..security import get_current_user
from ..services import storage, waveform

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
    )


def _version_out(db: Session, v: ReviewVersion, with_comments: bool = False) -> ReviewVersionOut:
    data = storage.read_blob(v.blob_sha)
    wf = waveform.generate(v.blob_sha, data, v.filename, v.audio_format)
    comments = (
        [_comment_out(c) for c in v.comments] if with_comments else []
    )
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
        waveform=wf["peaks"],
        waveform_synthetic=wf["synthetic"],
        comments=comments,
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


# ---------- public share endpoints (no auth) ----------
# Defined BEFORE /{session_id} routes so FastAPI matches them first
# (otherwise "public" would be parsed as an int session_id and 404).


def get_public_session(db: Session, share_token: str) -> ReviewSession:
    session = db.scalar(
        select(ReviewSession).where(ReviewSession.share_token == share_token)
    )
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review link not found")
    return session


@router.get("/public/{share_token}", response_model=ReviewSessionDetailOut)
def public_session(
    share_token: str,
    db: Session = Depends(get_db),
):
    session = get_public_session(db, share_token)
    versions = db.scalars(
        select(ReviewVersion)
        .where(ReviewVersion.session_id == session.id)
        .order_by(ReviewVersion.number.desc())
    ).all()
    out = _session_out(db, session)
    return ReviewSessionDetailOut(
        **out.model_dump(),
        versions=[_version_out(db, v, with_comments=True) for v in versions],
    )


@router.post("/public/{share_token}/versions/{version_id}/comments", response_model=ReviewCommentOut, status_code=status.HTTP_201_CREATED)
def guest_comment(
    share_token: str,
    version_id: int,
    payload: GuestReviewCommentCreate,
    db: Session = Depends(get_db),
):
    session = get_public_session(db, share_token)
    version = get_version_or_404(db, session.id, version_id)
    if payload.parent_id:
        parent = db.get(ReviewComment, payload.parent_id)
        if parent is None or parent.version_id != version.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parent comment not found in this version")
    comment = ReviewComment(
        version_id=version.id,
        author_name=payload.author_name.strip()[:128] or "Reviewer",
        time_s=payload.time_s,
        body=payload.body.strip(),
        parent_id=payload.parent_id,
    )
    db.add(comment)
    session.updated_at = utcnow()
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)


# ---------- owner endpoints ----------


@router.get("", response_model=list[ReviewSessionOut])
def list_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = db.scalars(
        select(ReviewSession)
        .where(ReviewSession.owner_id == user.id)
        .order_by(ReviewSession.updated_at.desc())
    ).all()
    return [_session_out(db, s) for s in sessions]


@router.post("", response_model=ReviewSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ReviewSessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
def get_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user, session_id)
    versions = db.scalars(
        select(ReviewVersion)
        .where(ReviewVersion.session_id == session.id)
        .order_by(ReviewVersion.number.desc())
    ).all()
    out = _session_out(db, session)
    return ReviewSessionDetailOut(
        **out.model_dump(),
        versions=[_version_out(db, v, with_comments=True) for v in versions],
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user, session_id)
    db.delete(session)
    db.commit()


@router.post("/{session_id}/versions", response_model=ReviewVersionOut, status_code=status.HTTP_201_CREATED)
def upload_version(
    session_id: int,
    message: str = Form(""),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user, session_id)
    filename = PurePosixPath((file.filename or "audio.wav").replace("\\", "/")).name
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_AUDIO:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported audio format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_AUDIO))}",
        )
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
    )
    db.add(version)
    session.updated_at = utcnow()  # touch
    db.commit()
    db.refresh(version)
    return _version_out(db, version)


@router.get("/{session_id}/versions/{version_id}/audio")
def download_audio(
    session_id: int,
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_session_or_404(db, user, session_id)
    version = get_version_or_404(db, session_id, version_id)
    data = storage.read_blob(version.blob_sha)
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type=f"audio/{version.audio_format}",
        headers={"Content-Disposition": f'attachment; filename="{version.filename}"'},
    )


@router.post("/{session_id}/versions/{version_id}/comments", response_model=ReviewCommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    session_id: int,
    version_id: int,
    payload: ReviewCommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_session_or_404(db, user, session_id)
    version = get_version_or_404(db, session_id, version_id)
    if payload.parent_id:
        parent = db.get(ReviewComment, payload.parent_id)
        if parent is None or parent.version_id != version.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Parent comment not found in this version")
    comment = ReviewComment(
        version_id=version.id,
        author_id=user.id,
        time_s=payload.time_s,
        body=payload.body.strip(),
        parent_id=payload.parent_id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)


@router.patch("/{session_id}/versions/{version_id}/comments/{comment_id}", response_model=ReviewCommentOut)
def update_comment(
    session_id: int,
    version_id: int,
    comment_id: int,
    resolved: bool | None = None,
    body: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
def set_version_status(
    session_id: int,
    version_id: int,
    payload: ReviewStatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user, session_id)
    version = get_version_or_404(db, session_id, version_id)
    version.status = payload.status
    session.status = payload.status
    db.commit()
    db.refresh(version)
    return _version_out(db, version)

