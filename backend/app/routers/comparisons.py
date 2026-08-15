"""Level-matched A/B comparison between versions of the same session.

The gains are derived from loudness analysis and applied ONLY in the preview
graph (Web Audio on the client). Source files, metadata and the locked release
package are never modified.
"""

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_SIZE
from ..database import get_db
from ..models import AudioAnalysis, ReviewVersion, StemAsset, VersionComparison, User
from ..schemas import (
    AudioAnalysisOut,
    ComparisonCreate,
    ComparisonOut,
    StemCreate,
    StemOut,
)
from ..security import get_current_user
from ..services import ledger, loudness, storage

ALLOWED_STEM_AUDIO = {"wav", "mp3", "flac", "aif", "aiff", "m4a", "ogg"}

router = APIRouter(prefix="/api", tags=["comparisons"])


def _get_version(db: Session, user: User, version_id: int) -> ReviewVersion:
    v = db.get(ReviewVersion, version_id)
    if v is None or v.session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    return v


def _analysis_out(a: AudioAnalysis | None) -> AudioAnalysisOut:
    if a is None:
        return AudioAnalysisOut(analysis_status="pending")
    return AudioAnalysisOut(
        version_id=a.version_id,
        duration_ms=a.duration_ms,
        sample_rate=a.sample_rate,
        channels=a.channels,
        integrated_lufs=a.integrated_lufs,
        true_peak_dbtp=a.true_peak_dbtp,
        analysis_status=a.analysis_status,
        analysed_at=a.analysed_at,
    )


@router.get("/versions/{version_id}/audio-analysis", response_model=AudioAnalysisOut)
def get_audio_analysis(
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    v = _get_version(db, user, version_id)
    analysis = db.scalar(select(AudioAnalysis).where(AudioAnalysis.version_id == v.id))
    if analysis is None:
        # analyse on demand so the UI never stalls forever
        from ..services import analysis as analysis_job

        analysis = analysis_job.analyse_version(db, v)
    return _analysis_out(analysis)


@router.post("/comparisons", response_model=ComparisonOut, status_code=status.HTTP_201_CREATED)
def create_comparison(
    payload: ComparisonCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = _get_version(db, user, payload.base_version_id)
    compare = _get_version(db, user, payload.compare_version_id)
    if base.session_id != compare.session_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Both versions must belong to the same review session",
        )

    # short-term loudness around the region for level matching
    short: dict = {}
    base_lufs = compare_lufs = None
    level_match = "none"
    start_ms = payload.start_ms
    end_ms = payload.end_ms or start_ms + 20000
    stem_name = payload.stem_logical_name
    base_stem = compare_stem = None
    stem_url = ""

    if payload.mode == "stem":
        if not stem_name:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "stem_logical_name is required when mode=stem",
            )
        # match by logical name — both stems must exist in BOTH versions
        base_stem = db.scalar(
            select(StemAsset).where(StemAsset.version_id == base.id, StemAsset.logical_name == stem_name)
        )
        compare_stem = db.scalar(
            select(StemAsset).where(StemAsset.version_id == compare.id, StemAsset.logical_name == stem_name)
        )
        if base_stem is None or compare_stem is None:
            missing = base.label if base_stem is None else compare.label
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Stem '{stem_name}' is unavailable in {missing} — compare the full mix instead",
            )
        if base_stem.audio_format == "wav" and compare_stem.audio_format == "wav":
            # region LUFS relative to the stem's own timeline (start_offset_ms)
            b_offset = base_stem.start_offset_ms
            c_offset = compare_stem.start_offset_ms
            try:
                b_data = storage.read_blob(base_stem.blob_sha)
                c_data = storage.read_blob(compare_stem.blob_sha)
                base_lufs = loudness.short_term_lufs(b_data, max(0, start_ms - b_offset), end_ms - b_offset)
                compare_lufs = loudness.short_term_lufs(c_data, max(0, start_ms - c_offset), end_ms - c_offset)
                if base_lufs is not None and compare_lufs is not None:
                    short = {base.label: base_lufs, compare.label: compare_lufs}
                    level_match = "short_term_lufs"
            except Exception:
                level_match = "none"
        stem_url = f"/api/versions/{base.id}/stems/{base_stem.id}/audio"

    if payload.mode != "stem" and payload.level_match and payload.level_match != "none":
        try:
            b_data = storage.read_blob(base.blob_sha)
            c_data = storage.read_blob(compare.blob_sha)
            if base.audio_format == "wav" and compare.audio_format == "wav":
                base_lufs = loudness.short_term_lufs(b_data, start_ms, end_ms)
                compare_lufs = loudness.short_term_lufs(c_data, start_ms, end_ms)
                if base_lufs is not None and compare_lufs is not None:
                    short = {base.label: base_lufs, compare.label: compare_lufs}
                    level_match = "short_term_lufs"
            else:
                # integrated fallback from stored analysis
                ba = db.scalar(select(AudioAnalysis).where(AudioAnalysis.version_id == base.id))
                ca = db.scalar(select(AudioAnalysis).where(AudioAnalysis.version_id == compare.id))
                if ba and ca and ba.integrated_lufs is not None and ca.integrated_lufs is not None:
                    base_lufs, compare_lufs = ba.integrated_lufs, ca.integrated_lufs
                    short = {base.label: base_lufs, compare.label: compare_lufs}
                    level_match = "integrated_lufs"
        except Exception:
            level_match = "none"

    base_gain, compare_gain = loudness.gain_to_match(base_lufs, compare_lufs)
    comp = VersionComparison(
        session_id=base.session_id,
        base_version_id=base.id,
        compare_version_id=compare.id,
        request_id=payload.request_id,
        start_ms=start_ms,
        end_ms=end_ms,
        base_gain_db=round(base_gain, 1),
        compare_gain_db=round(compare_gain, 1),
        level_match=level_match,
        short_term_lufs=short,
        mode=payload.mode,
        stem_logical_name=stem_name if payload.mode == "stem" else None,
    )
    db.add(comp)
    db.flush()
    ledger.append(
        db,
        "comparison.created",
        session_id=base.session_id,
        actor=user.username,
        entity_type="comparison",
        entity_id=comp.id,
        payload={
            "base": base.label,
            "compare": compare.label,
            "request_id": payload.request_id,
            "level_match": level_match,
            "mode": payload.mode,
            "stem": stem_name,
            "gains": {"base": base_gain, "compare": compare_gain},
        },
    )
    db.commit()
    return _comparison_out(comp)


@router.get("/comparisons/{comparison_id}", response_model=ComparisonOut)
def get_comparison(
    comparison_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comp = db.get(VersionComparison, comparison_id)
    if comp is None or comp.session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comparison not found")
    return _comparison_out(comp)


def _comparison_out(c: VersionComparison) -> ComparisonOut:
    label = "Level matched"
    if c.level_match == "none":
        label = "Level match unavailable"
    elif c.base_gain_db:
        label = f"Level matched · {c.base_version.label} {c.base_gain_db:+.1f} dB"
    return ComparisonOut(
        id=c.id,
        session_id=c.session_id,
        base_version_id=c.base_version_id,
        compare_version_id=c.compare_version_id,
        base_label=c.base_version.label,
        compare_label=c.compare_version.label,
        request_id=c.request_id,
        start_ms=c.start_ms,
        end_ms=c.end_ms,
        base_gain_db=c.base_gain_db,
        compare_gain_db=c.compare_gain_db,
        short_term_lufs=c.short_term_lufs,
        level_match=c.level_match,
        label=label,
        mode=c.mode,
        stem_logical_name=c.stem_logical_name,
        created_at=c.created_at,
    )


# ---------- stems ----------


def _stem_out(s: StemAsset) -> StemOut:
    return StemOut(
        id=s.id,
        version_id=s.version_id,
        logical_name=s.logical_name,
        display_name=s.display_name,
        size=s.size,
        audio_format=s.audio_format,
        start_offset_ms=s.start_offset_ms,
        created_at=s.created_at,
    )


@router.post("/versions/{version_id}/stems", response_model=StemOut, status_code=status.HTTP_201_CREATED)
def upload_stem(
    version_id: int,
    logical_name: str = Form(...),
    display_name: str = Form(""),
    start_offset_ms: int = Form(0),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attach a stem (submix render) to a version, matched by logical name."""
    if logical_name not in {"drums", "bass", "vocal", "synths", "other"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid logical_name")
    v = _get_version(db, user, version_id)
    filename = PurePosixPath((file.filename or "stem.wav").replace("\\", "/")).name
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_STEM_AUDIO:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported audio format '{ext}'. Allowed: {', '.join(sorted(ALLOWED_STEM_AUDIO))}",
        )
    try:
        data = storage.put_upload_file(file, MAX_UPLOAD_SIZE)
    except ValueError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))
    blob_sha = storage.put_blob(data)
    stem = StemAsset(
        version_id=v.id,
        logical_name=logical_name,
        display_name=display_name.strip() or logical_name,
        blob_sha=blob_sha,
        size=len(data),
        audio_format=ext,
        start_offset_ms=max(0, start_offset_ms),
    )
    db.add(stem)
    db.flush()
    ledger.append(
        db,
        "stem.uploaded",
        session_id=v.session_id,
        actor=user.username,
        entity_type="stem",
        entity_id=stem.id,
        payload={"version": v.label, "logical_name": logical_name, "filename": filename},
    )
    db.commit()
    return _stem_out(stem)


@router.get("/versions/{version_id}/stems", response_model=list[StemOut])
def list_stems(
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    v = _get_version(db, user, version_id)
    stems = db.scalars(
        select(StemAsset).where(StemAsset.version_id == v.id).order_by(StemAsset.logical_name)
    ).all()
    return [_stem_out(s) for s in stems]


@router.get("/versions/{version_id}/stems/{stem_id}/audio")
def stem_audio(
    version_id: int,
    stem_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    v = _get_version(db, user, version_id)
    stem = db.get(StemAsset, stem_id)
    if stem is None or stem.version_id != v.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stem not found")
    data = storage.read_blob(stem.blob_sha)
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{stem.display_name or stem.logical_name}"'},
    )
