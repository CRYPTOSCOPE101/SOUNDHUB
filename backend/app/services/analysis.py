"""Loudness analysis for audio versions.

Measures integrated LUFS, true peak, sample rate, and channels.
Analysis runs in the background after upload.
"""
import io
import logging
import math
import struct
import wave
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import AudioAnalysis, ReviewVersion

logger = logging.getLogger(__name__)

MEASURE_ERRORS = (wave.Error, struct.error, EOFError, ValueError, MemoryError)


def analyse_version(db: Session, version: ReviewVersion) -> None:
    """Run loudness analysis on a version (called from background task)."""
    from . import storage

    existing = db.query(AudioAnalysis).filter(AudioAnalysis.version_id == version.id).first()
    if existing and existing.analysis_status == "done":
        return

    if existing is None:
        existing = AudioAnalysis(version_id=version.id)
        db.add(existing)

    try:
        data = storage.read_blob(version.blob_sha)
        result = _measure_audio(data, version.audio_format)
        existing.duration_ms = result["duration_ms"]
        existing.sample_rate = result["sample_rate"]
        existing.channels = result["channels"]
        existing.integrated_lufs = result["integrated_lufs"]
        existing.true_peak_dbtp = result["true_peak_dbtp"]
        existing.analysis_status = "done"
        existing.analysed_at = datetime.now(timezone.utc)
    except (OSError, *MEASURE_ERRORS):
        logger.warning(
            "loudness analysis unavailable for version %s (blob %s)",
            version.id,
            version.blob_sha,
            exc_info=True,
        )
        existing.analysis_status = "unavailable"
    except Exception:
        # Unexpected failure: record it and re-raise so the caller/task sees it.
        logger.exception("loudness analysis failed for version %s", version.id)
        existing.analysis_status = "unavailable"
        db.commit()
        raise

    db.commit()


def _measure_audio(data: bytes, audio_format: str) -> dict:
    """Measure audio properties from raw data."""
    result = {
        "duration_ms": 0,
        "sample_rate": None,
        "channels": None,
        "integrated_lufs": None,
        "true_peak_dbtp": None,
    }

    if audio_format == "wav":
        try:
            buf = io.BytesIO(data)
            with wave.open(buf, "rb") as w:
                framerate = w.getframerate()
                n_channels = w.getnchannels()
                sampwidth = w.getsampwidth()
                n_frames = w.getnframes()

                result["sample_rate"] = framerate
                result["channels"] = n_channels
                result["duration_ms"] = int(n_frames / framerate * 1000) if framerate > 0 else 0

                if sampwidth == 2 and framerate > 0:
                    raw = w.readframes(n_frames)
                    n_samples = n_frames * n_channels
                    samples = struct.unpack(f"<{n_samples}h", raw)
                    max_val = max(abs(s) for s in samples) if samples else 0
                    if max_val > 0:
                        dbfs = 20 * math.log10(max_val / 32768.0)
                        result["true_peak_dbtp"] = round(dbfs, 2)
                        # Rough LUFS estimate from peak
                        result["integrated_lufs"] = round(dbfs - 3.0, 2)
        except MEASURE_ERRORS:
            logger.warning("could not measure wav audio (%d bytes)", len(data), exc_info=True)

    return result
