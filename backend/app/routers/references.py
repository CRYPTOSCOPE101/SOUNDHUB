"""Reference tracks — mix/reference A/B without polluting versions.

References are private to the review session and NON-DELIVERABLE by
construction: they live in their own table (`reference_tracks`), are never
linked from `release_deliverables` (which only references `review_versions`),
and are never exposed on the public delivery link. The deliverable endpoints
carry a server-side guard so a reference blob can't be slipped into a package.

Two source types:
- `external_url` — just a link; SoundHub never downloads third-party content
  (Spotify/YouTube). It's opened in a separate tab.
- `private_upload` — a file the user has rights to; it gets the same neutral
  loudness analysis as versions and can be used for in-app A/B.
"""

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_SIZE
from ..database import get_db
from ..models import (
    AudioAnalysis,
    ReferenceComparison,
    ReferenceTrack,
    ReviewSession,
    ReviewVersion,
    User,
)
from ..schemas import (
    ReferenceComparisonCreate,
    ReferenceComparisonOut,
    ReferenceTrackCreate,
    ReferenceTrackOut,
    ReferenceTrackUpdate,
)
from ..security import get_current_user
from ..services import ledger, loudness, storage, waveform
from .sessions import (
    _require_share_permission,
    get_public_session,
    get_session_or_404,
    get_version_or_404,
)

router = APIRouter(prefix="/api", tags=["references"])

ALLOWED_AUDIO = {"wav", "mp3", "flac", "aif", "aiff", "m4a", "ogg"}

DISCLAIMER = (
    "Reference audio is private to this review session and is never delivered, "
    "redistributed, or included in release exports."
)


def _ref_out(r: ReferenceTrack) -> ReferenceTrackOut:
    data = storage.read_blob(r.blob_sha) if r.blob_sha else b""
    wf = waveform.generate(r.blob_sha or "", data, r.filename, r.audio_format) if r.blob_sha else {
        "duration_s": r.duration_s, "peaks": [], "synthetic": True
    }
    return ReferenceTrackOut(
        id=r.id,
        session_id=r.session_id,
        title=r.title,
        artist=r.artist,
        source_type=r.source_type,
        external_url=r.external_url,
        purpose=r.purpose,
        visibility=r.visibility,
        note=r.note,
        created_by=r.created_by,
        created_at=r.created_at,
        filename=r.filename,
        size=r.size,
        audio_format=r.audio_format,
        duration_s=wf["duration_s"] or r.duration_s,
        integrated_lufs=r.integrated_lufs,
        true_peak_dbtp=r.true_peak_dbtp,
        sample_rate=r.sample_rate,
        channels=r.channels,
        analysis_status=r.analysis_status,
        waveform=wf["peaks"],
        waveform_synthetic=wf["synthetic"],
    )


def _get_reference(db: Session, session_id: int, reference_id: int) -> ReferenceTrack:
    ref = db.get(ReferenceTrack, reference_id)
    if ref is None or ref.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reference not found")
    return ref


def _ensure_analysis_ready(ref: ReferenceTrack) -> None:
    if ref.source_type != "private_upload" or not ref.blob_sha:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only uploaded private references can be compared in-app — URL references open in a new tab",
        )
    if ref.analysis_status == "unavailable":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Reference analysis is unavailable for this format — upload a WAV to compare in-app",
        )
    if ref.analysis_status != "done":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Reference analysis is not ready yet — try again in a moment",
        )


# ---------- owner endpoints ----------


@router.post("/sessions/{session_id}/references", response_model=ReferenceTrackOut, status_code=status.HTTP_201_CREATED)
def create_reference(
    session_id: int,
    payload: ReferenceTrackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add an external-URL reference. No audio job is created — the link is
    opened separately, never downloaded by SoundHub."""
    session = get_session_or_404(db, user, session_id)
    if payload.source_type == "private_upload":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Private references must be uploaded as a file",
        )
    ref = ReferenceTrack(
        session_id=session.id,
        title=payload.title.strip(),
        artist=payload.artist.strip(),
        source_type="external_url",
        external_url=payload.external_url.strip(),
        purpose=payload.purpose,
        visibility=payload.visibility,
        note=payload.note.strip(),
        created_by=user.username,
    )
    db.add(ref)
    db.flush()
    ledger.append(
        db,
        "reference.created",
        session_id=session.id,
        actor=user.username,
        entity_type="reference",
        entity_id=ref.id,
        payload={"title": ref.title, "artist": ref.artist, "source_type": "external_url", "visibility": ref.visibility, "purpose": ref.purpose},
    )
    db.commit()
    return _ref_out(ref)


@router.post("/sessions/{session_id}/references/upload", response_model=ReferenceTrackOut, status_code=status.HTTP_201_CREATED)
def upload_reference(
    session_id: int,
    title: str = Form(...),
    artist: str = Form(""),
    purpose: str = Form("overall"),
    visibility: str = Form("reviewers"),
    note: str = Form(""),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a private reference file (the user must hold rights to it)."""
    session = get_session_or_404(db, user, session_id)
    if purpose not in {"balance", "low_end", "vocal", "width", "arrangement", "overall"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid purpose")
    if visibility not in {"engineer_only", "reviewers"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid visibility")
    filename = PurePosixPath((file.filename or "reference.wav").replace("\\", "/")).name
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
    result = loudness.analyse(data)
    ref = ReferenceTrack(
        session_id=session.id,
        title=title.strip()[:200] or filename,
        artist=artist.strip()[:128],
        source_type="private_upload",
        blob_sha=blob_sha,
        filename=filename,
        size=len(data),
        audio_format=ext,
        duration_s=wf["duration_s"],
        purpose=purpose,
        visibility=visibility,
        note=note.strip()[:1000],
        created_by=user.username,
        integrated_lufs=result["integrated_lufs"],
        true_peak_dbtp=result["true_peak_dbtp"],
        sample_rate=result["sample_rate"],
        channels=result["channels"],
        analysis_status=result["status"],
    )
    db.add(ref)
    db.flush()
    ledger.append(
        db,
        "reference.created",
        session_id=session.id,
        actor=user.username,
        entity_type="reference",
        entity_id=ref.id,
        payload={"title": ref.title, "artist": ref.artist, "source_type": "private_upload", "visibility": ref.visibility, "purpose": ref.purpose, "filename": filename},
    )
    db.commit()
    return _ref_out(ref)


@router.get("/sessions/{session_id}/references", response_model=list[ReferenceTrackOut])
def list_references(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_session_or_404(db, user, session_id)
    refs = db.scalars(
        select(ReferenceTrack).where(ReferenceTrack.session_id == session_id).order_by(ReferenceTrack.id)
    ).all()
    return [_ref_out(r) for r in refs]


@router.patch("/sessions/{session_id}/references/{reference_id}", response_model=ReferenceTrackOut)
def update_reference(
    session_id: int,
    reference_id: int,
    payload: ReferenceTrackUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user, session_id)
    ref = _get_reference(db, session.id, reference_id)
    if payload.title is not None:
        ref.title = payload.title.strip()
    if payload.artist is not None:
        ref.artist = payload.artist.strip()
    if payload.external_url is not None:
        ref.external_url = payload.external_url.strip()
    if payload.purpose is not None:
        ref.purpose = payload.purpose
    if payload.visibility is not None:
        ref.visibility = payload.visibility
    if payload.note is not None:
        ref.note = payload.note.strip()
    ledger.append(
        db,
        "reference.updated",
        session_id=session.id,
        actor=user.username,
        entity_type="reference",
        entity_id=ref.id,
        payload={"title": ref.title, "artist": ref.artist, "visibility": ref.visibility, "purpose": ref.purpose},
    )
    db.commit()
    return _ref_out(ref)


@router.delete("/sessions/{session_id}/references/{reference_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reference(
    session_id: int,
    reference_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user, session_id)
    ref = _get_reference(db, session.id, reference_id)
    ledger.append(
        db,
        "reference.removed",
        session_id=session.id,
        actor=user.username,
        entity_type="reference",
        entity_id=ref.id,
        payload={"title": ref.title, "artist": ref.artist},
    )
    db.delete(ref)
    db.commit()


@router.get("/sessions/{session_id}/references/{reference_id}/audio")
def reference_audio(
    session_id: int,
    reference_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_session_or_404(db, user, session_id)
    ref = _get_reference(db, session_id, reference_id)
    if not ref.blob_sha:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "URL references have no audio")
    data = storage.read_blob(ref.blob_sha)
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type=f"audio/{ref.audio_format}",
        headers={"Content-Disposition": f'inline; filename="{ref.filename}"'},
    )


@router.post("/sessions/{session_id}/references/compare", response_model=ReferenceComparisonOut, status_code=status.HTTP_201_CREATED)
def create_reference_comparison(
    session_id: int,
    payload: ReferenceComparisonCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user, session_id)
    return _build_reference_comparison(
        db,
        session,
        version=get_version_or_404(db, session.id, payload.version_id),
        ref=_get_reference(db, session.id, payload.reference_id),
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
        level_match=payload.level_match,
        actor=user.username,
    )


# ---------- public share endpoints (guests / reviewers) ----------


@router.get("/sessions/public/{share_token}/references", response_model=list[ReferenceTrackOut])
def public_list_references(
    share_token: str,
    actor: str = "",
    password: str | None = None,
    db: Session = Depends(get_db),
):
    session = get_public_session(db, share_token)
    # reviewers only — view-only guests don't see references
    _require_share_permission(session, "comment", actor, password)
    refs = db.scalars(
        select(ReferenceTrack)
        .where(ReferenceTrack.session_id == session.id, ReferenceTrack.visibility == "reviewers")
        .order_by(ReferenceTrack.id)
    ).all()
    return [_ref_out(r) for r in refs]


@router.get("/sessions/public/{share_token}/references/{reference_id}/audio")
def public_reference_audio(
    share_token: str,
    reference_id: int,
    actor: str = "",
    password: str | None = None,
    db: Session = Depends(get_db),
):
    session = get_public_session(db, share_token)
    _require_share_permission(session, "comment", actor, password)
    ref = _get_reference(db, session.id, reference_id)
    if ref.visibility != "reviewers" or not ref.blob_sha:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reference not found")
    data = storage.read_blob(ref.blob_sha)
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type=f"audio/{ref.audio_format}",
        headers={"Content-Disposition": f'inline; filename="{ref.filename}"'},
    )


@router.post("/sessions/public/{share_token}/references/compare", response_model=ReferenceComparisonOut, status_code=status.HTTP_201_CREATED)
def public_create_reference_comparison(
    share_token: str,
    payload: ReferenceComparisonCreate,
    actor: str = "",
    password: str | None = None,
    db: Session = Depends(get_db),
):
    session = get_public_session(db, share_token)
    _require_share_permission(session, "comment", actor, password)
    version = get_version_or_404(db, session.id, payload.version_id)
    ref = _get_reference(db, session.id, payload.reference_id)
    if ref.visibility != "reviewers":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reference not found")
    return _build_reference_comparison(
        db,
        session,
        version=version,
        ref=ref,
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
        level_match=payload.level_match,
        actor=actor or "reviewer",
        public_token=share_token,
    )


# ---------- shared comparison builder ----------


def _build_reference_comparison(
    db: Session,
    session: ReviewSession,
    *,
    version: ReviewVersion,
    ref: ReferenceTrack,
    start_ms: int,
    end_ms: int | None,
    level_match: str,
    actor: str,
    public_token: str | None = None,
) -> ReferenceComparisonOut:
    """Level-matched mix ↔ reference. Gains are applied ONLY in the client's
    Web Audio graph — neither file is ever modified."""
    _ensure_analysis_ready(ref)
    end = end_ms or start_ms + 20000
    short: dict = {}
    mix_lufs = ref_lufs = None
    matched = "none"
    if level_match != "none":
        try:
            mix_data = storage.read_blob(version.blob_sha)
            ref_data = storage.read_blob(ref.blob_sha)
            if version.audio_format == "wav" and ref.audio_format == "wav":
                mix_lufs = loudness.short_term_lufs(mix_data, start_ms, end)
                ref_lufs = loudness.short_term_lufs(ref_data, start_ms, end)
                if mix_lufs is not None and ref_lufs is not None:
                    short = {"mix": mix_lufs, "reference": ref_lufs}
                    matched = "short_term_lufs"
            else:
                # integrated fallback from stored analysis (mix side may lag)
                mix_a = db.scalar(select(AudioAnalysis).where(AudioAnalysis.version_id == version.id))
                if mix_a and mix_a.integrated_lufs is not None and ref.integrated_lufs is not None:
                    mix_lufs, ref_lufs = mix_a.integrated_lufs, ref.integrated_lufs
                    short = {"mix": mix_lufs, "reference": ref_lufs}
                    matched = "integrated_lufs"
        except Exception:
            matched = "none"
    mix_gain, ref_gain = loudness.gain_to_match(mix_lufs, ref_lufs)
    comp = ReferenceComparison(
        session_id=session.id,
        version_id=version.id,
        reference_id=ref.id,
        start_ms=start_ms,
        end_ms=end,
        mix_gain_db=round(mix_gain, 1),
        ref_gain_db=round(ref_gain, 1),
        level_match=matched,
        short_term_lufs=short,
    )
    db.add(comp)
    db.flush()
    ledger.append(
        db,
        "reference.compared",
        session_id=session.id,
        actor=actor,
        entity_type="reference",
        entity_id=ref.id,
        payload={
            "version": version.label,
            "reference": ref.title,
            "artist": ref.artist,
            "level_match": matched,
            "gains": {"mix": mix_gain, "reference": ref_gain},
        },
    )
    db.commit()
    if public_token:
        mix_audio_url = f"/api/sessions/public/{public_token}/versions/{version.id}/audio"
        ref_audio_url = f"/api/sessions/public/{public_token}/references/{ref.id}/audio"
    else:
        mix_audio_url = f"/api/sessions/{session.id}/versions/{version.id}/audio"
        ref_audio_url = f"/api/sessions/{session.id}/references/{ref.id}/audio"
    return ReferenceComparisonOut(
        id=comp.id,
        session_id=comp.session_id,
        version_id=comp.version_id,
        reference_id=comp.reference_id,
        version_label=version.label,
        reference_label=f"{ref.artist} — {ref.title}" if ref.artist else ref.title,
        start_ms=comp.start_ms,
        end_ms=comp.end_ms,
        mix_gain_db=comp.mix_gain_db,
        ref_gain_db=comp.ref_gain_db,
        short_term_lufs=comp.short_term_lufs,
        level_match=comp.level_match,
        label="Level matched" if comp.level_match != "none" else "Level match unavailable",
        mix_audio_url=mix_audio_url,
        ref_audio_url=ref_audio_url,
        created_at=comp.created_at,
    )
