"""Built-in job handlers — wrap existing services for background execution.

Import this module at startup to register all handlers:
    import app.services.job_handlers  # noqa: F401
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .job_queue import register_handler

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ..models import Job

logger = logging.getLogger(__name__)


# ── parse_daw ───────────────────────────────────────────────────────────


@register_handler("parse_daw")
def handle_parse_daw(job: "Job", db: "Session") -> dict:
    """Parse a DAW project file and extract metadata."""
    from .daw.registry import get_daw_info
    from . import storage

    if not job.storage_object_id:
        raise ValueError("storage_object_id required for parse_daw")

    from ..models import StorageObject

    obj = db.get(StorageObject, job.storage_object_id)
    if obj is None:
        raise ValueError(f"StorageObject {job.storage_object_id} not found")

    data = storage.read_blob(obj.sha256)
    result = get_daw_info(obj.original_filename, data)
    return {"parsed": True, "metadata": result}


# ── generate_waveform ───────────────────────────────────────────────────


@register_handler("generate_waveform")
def handle_generate_waveform(job: "Job", db: "Session") -> dict:
    """Generate waveform peak data for an audio blob."""
    from . import waveform
    from . import storage

    input_data = job.input_json or {}
    sha = input_data.get("sha256")
    filename = input_data.get("filename", "audio.wav")
    audio_format = input_data.get("format", "wav")

    if not sha and job.storage_object_id:
        from ..models import StorageObject

        obj = db.get(StorageObject, job.storage_object_id)
        if obj:
            sha = obj.sha256
            filename = obj.original_filename or filename

    if not sha:
        raise ValueError("sha256 required (via input_json or storage_object_id)")

    data = storage.read_blob(sha)
    result = waveform.generate(sha, data, filename, audio_format)
    return result


# ── analyze_loudness ────────────────────────────────────────────────────


@register_handler("analyze_loudness")
def handle_analyze_loudness(job: "Job", db: "Session") -> dict:
    """Run loudness analysis (LUFS, True Peak, sample rate, channels)."""
    from . import loudness
    from . import storage

    input_data = job.input_json or {}
    sha = input_data.get("sha256")

    if not sha and job.storage_object_id:
        from ..models import StorageObject

        obj = db.get(StorageObject, job.storage_object_id)
        if obj:
            sha = obj.sha256

    if not sha:
        raise ValueError("sha256 required")

    data = storage.read_blob(sha)
    result = loudness.analyse(data)
    return result


# ── extract_audio_metadata ──────────────────────────────────────────────


@register_handler("extract_audio_metadata")
def handle_extract_audio_metadata(job: "Job", db: "Session") -> dict:
    """Extract audio metadata (sample rate, channels, duration, format)."""
    from . import storage

    input_data = job.input_json or {}
    sha = input_data.get("sha256")
    filename = input_data.get("filename", "")

    if not sha and job.storage_object_id:
        from ..models import StorageObject

        obj = db.get(StorageObject, job.storage_object_id)
        if obj:
            sha = obj.sha256
            filename = obj.original_filename or filename

    if not sha:
        raise ValueError("sha256 required")

    data = storage.read_blob(sha)

    # Basic metadata extraction
    result = {"sha256": sha, "size": len(data), "filename": filename}

    # Try WAV header parsing
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        import struct
        from io import BytesIO

        buf = BytesIO(data)
        buf.seek(12)
        while True:
            header = buf.read(8)
            if len(header) < 8:
                break
            cid, csize = struct.unpack("<4sI", header)
            if cid == b"fmt ":
                chunk = buf.read(csize)
                if len(chunk) >= 16:
                    af, channels, sr = struct.unpack("<HHI", chunk[:8])
                    bits = struct.unpack("<H", chunk[14:16])[0]
                    result.update({
                        "sample_rate": sr,
                        "channels": channels,
                        "bits": bits,
                        "audio_format": "wav",
                    })
            elif cid == b"data":
                sr = result.get("sample_rate", 44100)
                channels = result.get("channels", 1)
                bits = result.get("bits", 16)
                bytes_per_sample = bits // 8
                frame_size = bytes_per_sample * channels
                duration_s = csize / (sr * frame_size) if frame_size > 0 and sr > 0 else 0
                result["duration_s"] = round(duration_s, 2)
                break
            else:
                buf.seek(csize + (csize % 2), 1)

    return result


# ── transcode_audio ─────────────────────────────────────────────────────


@register_handler("transcode_audio")
def handle_transcode_audio(job: "Job", db: "Session") -> dict:
    """Transcode audio to a target format (placeholder — needs ffmpeg)."""
    from . import storage

    input_data = job.input_json or {}
    target_format = input_data.get("target_format", "wav")
    sha = input_data.get("sha256")

    if not sha and job.storage_object_id:
        from ..models import StorageObject

        obj = db.get(StorageObject, job.storage_object_id)
        if obj:
            sha = obj.sha256

    if not sha:
        raise ValueError("sha256 required")

    data = storage.read_blob(sha)

    # Placeholder: in production, use ffmpeg or pydub
    # For now, just store as-is
    new_sha = storage.put_blob(data)

    return {
        "source_sha256": sha,
        "output_sha256": new_sha,
        "target_format": target_format,
        "note": "Transcoding placeholder — implement with ffmpeg",
    }


# ── watermark_preview ───────────────────────────────────────────────────


@register_handler("watermark_preview")
def handle_watermark_preview(job: "Job", db: "Session") -> dict:
    """Generate a watermarked preview of an audio file."""
    from . import storage
    from .watermark import generate_watermark_key

    input_data = job.input_json or {}
    sha = input_data.get("sha256")
    version_id = job.version_id

    if not sha and job.storage_object_id:
        from ..models import StorageObject

        obj = db.get(StorageObject, job.storage_object_id)
        if obj:
            sha = obj.sha256

    if not sha:
        raise ValueError("sha256 required")

    data = storage.read_blob(sha)
    watermark_key = generate_watermark_key(version_id or 0)

    # Placeholder: in production, apply audible watermark
    watermarked_sha = storage.put_blob(data)

    return {
        "original_sha256": sha,
        "watermarked_sha256": watermarked_sha,
        "watermark_key": watermark_key,
        "note": "Watermarking placeholder — implement DSP",
    }
