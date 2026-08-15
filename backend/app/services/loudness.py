"""Loudness analysis in pure Python (no numpy).

A pragmatic EBU R128 approximation: K-weighting (shelf + high-pass) applied
per-sample, RMS over 400 ms blocks with 75% overlap gated at -70 LUFS, and
short-term loudness as sliding 3 s windows. The values are honest estimates —
marked `approximate` in the UI — sufficient for level-matching two versions
of the same session.
"""

import math
import struct
from io import BytesIO

# K-weighting filter coefficients (biquad cascade, 48 kHz design; applied at
# the file's sample rate — close enough for level matching between versions).
FS = 48000.0
_SHELF = (1.53512485958697, -2.69169618940638, 1.19839281085285, -1.69065929318241, 0.73248077421585)
_HIGHPASS = (1.0, -2.0, 1.0, -1.99004745483398, 0.99007225036621)


def _kweighted(chunk: list[float], shelf: tuple, hp: tuple) -> list[float]:
    out = []
    s1 = s2 = 0.0
    z1 = z2 = 0.0
    b0, b1, b2, a1, a2 = shelf
    c0, c1, c2, d1, d2 = hp
    for x in chunk:
        y = b0 * x + b1 * s1 + b2 * s2 - a1 * z1 - a2 * z2
        s1, s2, z1, z2 = x, s1, y, z1
        w = c0 * y + c1 * z1 + c2 * z2 - d1 * y - d2 * z1
        z2, z1 = z1, y
        out.append(w)
    return out


def _samples_wav(data: bytes) -> dict | None:
    """Decode PCM WAV into a mono float list + metadata."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    buf = BytesIO(data)
    buf.seek(12)
    fmt: dict = {}
    audio: bytes | None = None
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
                fmt = {"channels": channels, "sample_rate": sr, "bits": bits, "audio_format": af}
        elif cid == b"data":
            audio = buf.read(csize)
            break
        else:
            buf.seek(csize + (csize % 2), 1)
    if audio is None or not fmt or fmt["audio_format"] != 1:  # PCM only
        return None
    channels = fmt["channels"] or 1
    bits = fmt["bits"] or 16
    bps = max(1, bits // 8)
    frame = bps * channels
    n = len(audio) // frame
    samples: list[float] = []
    for i in range(n):
        off = i * frame
        if bps == 2:
            v = struct.unpack_from("<h", audio, off)[0] / 32768.0
        elif bps == 4:
            v = struct.unpack_from("<i", audio, off)[0] / 2147483648.0
        else:
            v = (audio[off] - 128) / 128.0
        samples.append(v)
    return {"samples": samples, "sample_rate": fmt["sample_rate"] or 44100, "channels": channels}


def _rms_db(x: list[float]) -> float:
    if not x:
        return -math.inf
    s = sum(v * v for v in x) / len(x)
    return 10 * math.log10(max(s, 1e-12))


def analyse(data: bytes) -> dict:
    """Return integrated LUFS, true peak (dBTP), sample rate, channels."""
    dec = _samples_wav(data)
    if dec is None:
        return {
            "integrated_lufs": None,
            "true_peak_dbtp": None,
            "sample_rate": None,
            "channels": None,
            "status": "unavailable",
        }
    sr = dec["sample_rate"]
    nch = dec["channels"]
    # per-frame channel average (interleave is frame-major)
    mono = [sum(dec["samples"][f * nch : (f + 1) * nch]) / nch for f in range(len(dec["samples"]) // nch)]
    # The K-weighting filters are designed for 48 kHz; below ~24 kHz they can
    # become unstable, so skip them and measure flat RMS instead (still a fair
    # loudness proxy for level-matching two versions of the same session).
    if sr >= 24000:
        weighted = _kweighted(mono, _SHELF, _HIGHPASS)
    else:
        weighted = mono

    # true peak: max abs sample, +3 dB overshoot allowance (approximate)
    peak = max((abs(v) for v in mono), default=0.0)
    true_peak = 20 * math.log10(max(peak, 1e-12)) + 3.0

    # integrated LUFS: 400 ms blocks, 75% overlap, gating at -70 LUFS
    block = int(sr * 0.4)
    hop = block // 4
    blocks = []
    i = 0
    while i + block <= len(weighted):
        blocks.append(_rms_db(weighted[i : i + block]))
        i += hop
    gated = [b for b in blocks if b > -70.0]
    if not gated:
        return {
            "integrated_lufs": None,
            "true_peak_dbtp": round(true_peak, 2),
            "sample_rate": sr,
            "channels": dec["channels"],
            "status": "done",
        }
    integrated = 10 * math.log10(sum(10 ** (b / 10) for b in gated) / len(gated))
    return {
        "integrated_lufs": round(integrated, 1),
        "true_peak_dbtp": round(true_peak, 2),
        "sample_rate": sr,
        "channels": dec["channels"],
        "status": "done",
    }


def short_term_lufs(data: bytes, start_ms: int, end_ms: int) -> float | None:
    """Short-term loudness (3 s window mean) around a region."""
    dec = _samples_wav(data)
    if dec is None or dec["sample_rate"] is None:
        return None
    sr = dec["sample_rate"]
    start = max(0, int(sr * start_ms / 1000))
    end = min(len(dec["samples"]), int(sr * end_ms / 1000))
    if end - start < int(sr * 0.4):  # < 400 ms of material
        return None
    nch = dec["channels"]
    mono = [sum(dec["samples"][f * nch : (f + 1) * nch]) / nch for f in range(len(dec["samples"]) // nch)]
    if sr >= 24000:
        weighted = _kweighted(mono[start:end], _SHELF, _HIGHPASS)
    else:
        weighted = mono[start:end]
    win = int(sr * 3.0)
    if len(weighted) < win:
        return round(_rms_db(weighted), 1) if weighted else None
    windows = []
    for i in range(0, len(weighted) - win + 1, win // 2):
        windows.append(_rms_db(weighted[i : i + win]))
    return round(sum(windows) / len(windows), 1) if windows else None


def gain_to_match(base_lufs: float | None, compare_lufs: float | None) -> tuple[float, float]:
    """Returns (base_gain_db, compare_gain_db) that equalize loudness.

    The louder version is attenuated; the quieter one stays at 0 so we never
    push a clip into distortion. base is the reference (v12).
    """
    if base_lufs is None or compare_lufs is None:
        return 0.0, 0.0
    diff = compare_lufs - base_lufs  # how much louder compare is
    if diff >= 0:
        return 0.0, -diff
    return diff, 0.0
