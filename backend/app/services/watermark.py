"""Audible watermark for preview streams.

Unapproved versions served to guests are mixed with periodic beep bursts so a
leaked preview is traceable and annoying enough to not be "the final file".
The original blob is never modified — we synthesize a *new* content-addressed
blob (deduplicated by SHA-256) and cache its hash on the version.

Only PCM WAV files are watermarked in-place (we can re-write the data chunk
directly). Non-WAV formats are served as-is — the UI shows a watermark notice
for those, and the delivery gate (402 on download) remains the real protection.
"""

import math
import struct
from io import BytesIO

BEEP_HZ = 1400          # clearly audible mid tone
BEEP_SECONDS = 0.22     # burst length
BEEP_EVERY = 5.0        # one burst every N seconds
BEEP_LEVEL = 0.16       # peak amplitude of the beep (0..1)


def _data_chunk_span(data: bytes) -> tuple[dict, int, int] | None:
    """Return (fmt, data_offset, data_size) for a PCM WAV, or None."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    buf = BytesIO(data)
    buf.seek(12)
    fmt: dict = {}
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
            return fmt, buf.tell(), csize
        else:
            buf.seek(csize, 1)
        if csize % 2:
            buf.seek(1, 1)
    return None


def _read_sample(chunk: bytes, off: int, bits: int) -> int:
    """Return the sample as a signed value scaled to 16-bit-ish range."""
    if bits == 8:
        return (chunk[off] - 128) << 8
    if bits == 16:
        return struct.unpack_from("<h", chunk, off)[0]
    if bits == 24:
        b0, b1, b2 = chunk[off], chunk[off + 1], chunk[off + 2]
        val = b0 | (b1 << 8) | (b2 << 16)
        if val >= 2**23:
            val -= 2**24
        return val << 8
    if bits == 32:
        return struct.unpack_from("<i", chunk, off)[0] >> 8
    return 0


def _write_sample(chunk: bytearray, off: int, bits: int, val: int) -> None:
    """Write a signed value (16-bit-scale) back into the sample at `off`."""
    if bits == 8:
        chunk[off] = max(0, min(255, (val >> 8) + 128))
    elif bits == 16:
        struct.pack_into("<h", chunk, off, max(-32768, min(32767, val)))
    elif bits == 24:
        v = max(-2**23, min(2**23 - 1, val >> 8))
        chunk[off] = v & 0xFF
        chunk[off + 1] = (v >> 8) & 0xFF
        chunk[off + 2] = (v >> 16) & 0xFF
    elif bits == 32:
        struct.pack_into("<i", chunk, off, max(-2**31, min(2**31 - 1, val << 8)))


def apply_watermark(data: bytes) -> bytes:
    """Return a copy of `data` with periodic beeps mixed in. Non-WAV → original."""
    span = _data_chunk_span(data)
    if span is None:
        return data
    fmt, data_off, data_size = span
    if fmt.get("audio_format") != 1 or not fmt.get("sample_rate"):
        return data  # compressed / unknown WAV — leave untouched
    channels = fmt["channels"]
    sample_rate = fmt["sample_rate"]
    bits = fmt["bits"]

    chunk = bytearray(data[data_off : data_off + data_size])
    bytes_per_sample = max(1, bits // 8)
    frame_bytes = bytes_per_sample * channels
    n_frames = len(chunk) // frame_bytes

    frames_per_period = int(BEEP_EVERY * sample_rate)
    frames_in_beep = int(BEEP_SECONDS * sample_rate)

    phase = 2 * math.pi * BEEP_HZ / sample_rate
    for i in range(n_frames):
        if i % frames_per_period >= frames_in_beep:
            continue
        beep = round(BEEP_LEVEL * 32767 * math.sin(phase * i))
        for ch in range(channels):
            off = i * frame_bytes + ch * bytes_per_sample
            cur = _read_sample(chunk, off, bits)
            _write_sample(chunk, off, bits, cur + beep)

    out = bytearray(data)
    out[data_off : data_off + data_size] = chunk
    return bytes(out)


def watermarked_blob(db, version) -> bytes:
    """Return the watermarked preview bytes for a version, cached on the row.

    The watermarked copy is a separate content-addressed blob — the original
    is never touched, so the locked release package stays byte-identical.
    Non-WAV files are returned untouched (no in-place watermark possible).
    """
    from . import storage

    if version.watermark_sha:
        return storage.read_blob(version.watermark_sha)
    data = storage.read_blob(version.blob_sha)
    wm = apply_watermark(data)
    if wm == data:
        return data  # not watermarked-able — caller still gets preview bytes
    sha = storage.put_blob(wm)
    version.watermark_sha = sha
    try:
        db.commit()
    except Exception:
        db.rollback()
    return wm
