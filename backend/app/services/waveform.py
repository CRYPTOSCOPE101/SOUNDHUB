"""Waveform generation for review audio.

For WAV (RIFF) files we read the real amplitude peaks into ``buckets``
values (0..1). For any other format we return a deterministic pseudo-waveform
seeded from the blob SHA-256 — honest about being synthetic, so the UI can
label it.

Also extracts duration: WAV from the RIFF header; others are estimated from
size/bitrate defaults (0 if unknown).
"""

import hashlib
import struct
from io import BytesIO

BUCKETS = 96  # waveform resolution served to the UI


def _riff_wave_info(data: bytes) -> dict | None:
    """Return {'duration_s': float, 'peaks': list[float]} for a PCM WAV."""
    try:
        if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            return None
        buf = BytesIO(data)
        buf.seek(12)
        fmt: dict = {}
        data_chunk: bytes | None = None
        while True:
            header = buf.read(8)
            if len(header) < 8:
                break
            cid, csize = struct.unpack("<4sI", header)
            if cid == b"fmt ":
                chunk = buf.read(csize)
                if len(chunk) < 16:
                    break
                audio_format, channels, sample_rate = struct.unpack("<HHI", chunk[:8])
                bits = struct.unpack("<H", chunk[14:16])[0]
                fmt = {
                    "audio_format": audio_format,
                    "channels": channels,
                    "sample_rate": sample_rate,
                    "bits": bits,
                }
            elif cid == b"data":
                data_chunk = buf.read(csize)
                break
            else:
                buf.seek(csize, 1)
            if csize % 2:
                buf.seek(1, 1)
        if data_chunk is None or not fmt:
            return None

        sample_rate = fmt["sample_rate"] or 44100
        channels = fmt["channels"] or 1
        bits = fmt["bits"] or 16
        bytes_per_sample = max(1, bits // 8)
        frame_bytes = bytes_per_sample * channels
        total_frames = len(data_chunk) // frame_bytes
        duration_s = total_frames / sample_rate

        peaks = _peaks_from_pcm(data_chunk, bytes_per_sample, channels, bits, duration_s)
        return {"duration_s": duration_s, "peaks": peaks}
    except (struct.error, IndexError, ValueError):
        return None


def _peaks_from_pcm(data: bytes, bytes_per_sample: int, channels: int, bits: int, duration_s: float) -> list[float]:
    frame_bytes = bytes_per_sample * channels
    if frame_bytes <= 0 or len(data) < frame_bytes:
        return []

    n = BUCKETS
    peaks = [0.0] * n
    per_bucket = max(1, len(data) // frame_bytes // n)
    bucket_frames = per_bucket * frame_bytes

    for i in range(n):
        start = i * bucket_frames
        chunk = data[start : start + bucket_frames]
        if not chunk:
            break
        peak = 0.0
        # step through frames, take the first channel's first sample
        for off in range(0, len(chunk) - frame_bytes + 1, frame_bytes):
            if bytes_per_sample == 2:
                val = struct.unpack_from("<h", chunk, off)[0]
            elif bytes_per_sample == 4:
                val = struct.unpack_from("<i", chunk, off)[0] >> 16  # 24-bit padded / 32-bit
            else:
                val = (chunk[off] - 128) << 8
            a = abs(val) / 32768.0
            if a > peak:
                peak = a
        peaks[i] = min(1.0, peak)

    if duration_s and peaks:
        peaks[0] = max(peaks[0], 0.001)  # keep a visible start edge
    return peaks


def _pseudo_waveform(blob_sha: str, duration_s: float) -> list[float]:
    """Deterministic synthetic peaks from the blob hash (non-WAV fallback)."""
    seed = int(hashlib.sha256(blob_sha.encode()).hexdigest()[:8], 16)
    n = BUCKETS
    peaks: list[float] = []
    state = seed
    for _ in range(n):
        state = (state * 1103515245 + 12345) % (2**31)
        r = state / (2**31)
        env = 0.35 + 0.4 * abs(((state >> 8) % 100) - 50) / 50
        peaks.append(min(1.0, max(0.05, r * env)))
    return peaks


def estimate_duration(blob_sha: str, size: int, audio_format: str) -> float:
    """Best-effort duration for non-WAV audio: assume common bitrates."""
    if audio_format == "mp3":
        # ~128 kbps → ~16 KB/s
        return size / 16000.0
    if audio_format == "ogg":
        return size / 24000.0
    if audio_format == "flac":
        return size / 44000.0
    # unknown: pseudo duration so the UI timeline has a sane range
    return 180.0


def generate(blob_sha: str, data: bytes, filename: str, audio_format: str) -> dict:
    """Return {'duration_s': float, 'peaks': list[float], 'synthetic': bool}."""
    ext = audio_format or (filename.rsplit(".", 1)[-1] if "." in filename else "")
    info = _riff_wave_info(data) if ext == "wav" else None
    if info:
        return {
            "duration_s": round(info["duration_s"], 2),
            "peaks": info["peaks"],
            "synthetic": False,
        }
    duration = estimate_duration(blob_sha, len(data), ext)
    return {
        "duration_s": duration,
        "peaks": _pseudo_waveform(blob_sha, duration),
        "synthetic": True,
    }
