"""Audio analysis background job.

Runs after upload so the waveform is returned immediately and loudness lands
a moment later. Non-WAV or non-PCM files are marked `unavailable` — the UI
falls back to manual gain.
"""

from sqlalchemy.orm import Session

from ..models import AudioAnalysis, ReviewVersion
from ..services import loudness, storage


def analyse_version(db: Session, version: ReviewVersion) -> AudioAnalysis:
    data = storage.read_blob(version.blob_sha)
    result = loudness.analyse(data)
    analysis = AudioAnalysis(
        version_id=version.id,
        duration_ms=int(version.duration_s * 1000),
        sample_rate=result["sample_rate"],
        channels=result["channels"],
        integrated_lufs=result["integrated_lufs"],
        true_peak_dbtp=result["true_peak_dbtp"],
        analysis_status=result["status"],
        analysed_at=utcnow(),
    )
    db.add(analysis)
    db.commit()
    return analysis


def utcnow():
    from ..models import utcnow as _u

    return _u()
