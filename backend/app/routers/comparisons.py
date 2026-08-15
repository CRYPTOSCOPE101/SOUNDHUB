"""Level-matched A/B comparison between versions of the same session.

The gains are derived from loudness analysis and applied ONLY in the preview
graph (Web Audio on the client). Source files, metadata and the locked release
package are never modified.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AudioAnalysis, ReviewVersion, VersionComparison, User
from ..schemas import (
    AudioAnalysisOut,
    ComparisonCreate,
    ComparisonOut,
)
from ..security import get_current_user
from ..services import ledger, loudness, storage

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
    if payload.level_match and payload.level_match != "none":
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
        created_at=c.created_at,
    )
