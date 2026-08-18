"""Waveform peak generation for audio visualization.

Generates peak data from audio blobs. Uses a synthetic fallback for
formats that can't be decoded locally.
"""
import hashlib
import io
import logging
import math
import struct
import wave

from ..config import TMP_DIR

logger = logging.getLogger(__name__)


def generate(blob_sha: str, data: bytes, filename: str, audio_format: str) -> dict:
    """Generate waveform peaks from audio data.

    Returns {"peaks": [float], "duration_s": float, "synthetic": bool}
    """
    peaks, duration_s = _extract_wav_peaks(data)
    if peaks:
        return {"peaks": peaks, "duration_s": duration_s, "synthetic": False}

    # Synthetic fallback for non-WAV or unparseable files
    return _synthetic_waveform(data, filename)


def _extract_wav_peaks(data: bytes) -> tuple[list[float], float]:
    """Extract peaks from WAV data (PCM 16-bit)."""
    try:
        buf = io.BytesIO(data)
        with wave.open(buf, "rb") as w:
            n_channels = w.getnchannels()
            sampwidth = w.getsampwidth()
            framerate = w.getframerate()
            n_frames = w.getnframes()
            duration_s = n_frames / framerate if framerate > 0 else 0.0

            if sampwidth != 2 or framerate == 0:
                return [], 0.0

            raw = w.readframes(n_frames)
            n_samples = n_frames * n_channels
            samples = struct.unpack(f"<{n_samples}h", raw)

            # Downsample to ~2000 peaks
            target_peaks = 2000
            chunk_size = max(1, len(samples) // target_peaks)
            peaks = []
            for i in range(0, len(samples), chunk_size):
                chunk = samples[i : i + chunk_size]
                if chunk:
                    max_val = max(abs(s) for s in chunk)
                    peaks.append(max_val / 32768.0)

            return peaks, duration_s
    except (wave.Error, struct.error, EOFError, ValueError, MemoryError):
        logger.info(
            "wav peak extraction failed (%d bytes) — falling back to synthetic waveform",
            len(data),
            exc_info=True,
        )
        return [], 0.0


def _synthetic_waveform(data: bytes, filename: str) -> dict:
    """Generate a synthetic waveform from file hash."""
    h = hashlib.sha256(data).hexdigest()
    n_peaks = 2000
    peaks = []
    for i in range(n_peaks):
        seed = int(h[i % len(h)], 16) / 15.0
        phase = (i * 7 + int(h[i % len(h)], 16) * 13) % 100 / 100.0
        val = 0.3 + 0.4 * seed * (0.5 + 0.5 * math.sin(2 * math.pi * phase))
        peaks.append(min(1.0, max(0.05, val)))

    duration_s = len(data) / (44100 * 2)  # rough estimate
    return {"peaks": peaks, "duration_s": duration_s, "synthetic": True}
