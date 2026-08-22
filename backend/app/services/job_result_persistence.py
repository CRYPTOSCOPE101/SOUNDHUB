"""Persist job results into domain models.

After a background job completes, its output is stored in ``Job.output_json``.
This module writes those results into the appropriate domain models so they
are queryable by the rest of the application.

Idempotent by design: re-running a completed job overwrites the same
``StorageObject.metadata_json`` key instead of creating duplicates.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from ..models import Job, StorageObject

logger = logging.getLogger(__name__)


def persist_job_result(job: Job, output: dict[str, Any], db: Session) -> None:
    """Dispatch job output to the right domain model writer.

    Called by the job worker after a handler returns successfully.
    Failures here are logged but never raise — the job is already marked
    as completed.
    """
    try:
        if job.type == "parse_daw":
            _persist_daw_metadata(job, output, db)
        elif job.type == "extract_audio_metadata":
            _persist_audio_metadata(job, output, db)
        elif job.type == "analyze_loudness":
            _persist_loudness(job, output, db)
        elif job.type == "generate_waveform":
            _persist_waveform(job, output, db)
        # transcode_audio / watermark_preview don't need domain persistence yet
    except Exception:
        logger.exception(
            "Failed to persist result for job %d (type=%s)", job.id, job.type
        )


# ── Individual persisters ───────────────────────────────────────────────


def _get_storage_object(job: Job, db: Session) -> StorageObject | None:
    """Resolve the StorageObject for this job (via storage_object_id or sha256)."""
    if job.storage_object_id:
        return db.get(StorageObject, job.storage_object_id)

    input_data = job.input_json or {}
    sha = input_data.get("sha256")
    if not sha:
        return None

    from sqlalchemy import select
    return db.scalar(
        select(StorageObject).where(StorageObject.sha256 == sha).limit(1)
    )


def _merge_metadata(obj: StorageObject, key: str, data: dict, db: Session) -> None:
    """Idempotently merge a result into StorageObject.metadata_json."""
    existing = obj.metadata_json or {}
    if isinstance(existing, str):
        try:
            existing = json.loads(existing)
        except (json.JSONDecodeError, TypeError):
            existing = {}

    existing[key] = data
    obj.metadata_json = existing
    obj.processed_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    )
    db.flush()


def _persist_daw_metadata(job: Job, output: dict, db: Session) -> None:
    """Store parsed DAW structure (tracks, plugins, BPM, etc.) on the StorageObject."""
    obj = _get_storage_object(job, db)
    if obj is None:
        logger.warning("parse_daw job %d: no StorageObject found, skipping persist", job.id)
        return

    metadata = output.get("metadata", output)
    _merge_metadata(obj, "daw_metadata", metadata, db)
    logger.info("Persisted DAW metadata for job %d on object %d", job.id, obj.id)


def _persist_audio_metadata(job: Job, output: dict, db: Session) -> None:
    """Store audio metadata (sample rate, channels, duration, format)."""
    obj = _get_storage_object(job, db)
    if obj is None:
        logger.warning("extract_audio_metadata job %d: no StorageObject found", job.id)
        return

    # Only persist audio-relevant fields
    audio_fields = {
        k: output[k]
        for k in ("sample_rate", "channels", "bits", "duration_s", "audio_format", "size")
        if k in output
    }
    if audio_fields:
        _merge_metadata(obj, "audio_metadata", audio_fields, db)
        logger.info("Persisted audio metadata for job %d on object %d", job.id, obj.id)


def _persist_loudness(job: Job, output: dict, db: Session) -> None:
    """Store loudness analysis (LUFS, True Peak, sample rate, channels)."""
    obj = _get_storage_object(job, db)
    if obj is None:
        logger.warning("analyze_loudness job %d: no StorageObject found", job.id)
        return

    loudness_fields = {
        k: output[k]
        for k in (
            "integrated_lufs",
            "true_peak_dbtp",
            "sample_rate",
            "channels",
            "loudness_range",
        )
        if k in output and output[k] is not None
    }
    if loudness_fields:
        _merge_metadata(obj, "loudness", loudness_fields, db)
        logger.info("Persisted loudness data for job %d on object %d", job.id, obj.id)


def _persist_waveform(job: Job, output: dict, db: Session) -> None:
    """Store waveform peak data on the StorageObject.

    Waveform data can be large (peak arrays), so we store a summary
    rather than the full peak data.  The full data stays in job.output_json
    for the waveform API endpoint.
    """
    obj = _get_storage_object(job, db)
    if obj is None:
        logger.warning("generate_waveform job %d: no StorageObject found", job.id)
        return

    waveform_summary = {
        k: output[k]
        for k in ("duration_s", "sample_rate", "channels", "peaks_count")
        if k in output
    }
    # Store peak count for quick access; full peaks stay in output_json
    if "peaks" in output:
        waveform_summary["peaks_count"] = len(output["peaks"])

    if waveform_summary:
        _merge_metadata(obj, "waveform", waveform_summary, db)
        logger.info("Persisted waveform summary for job %d on object %d", job.id, obj.id)
