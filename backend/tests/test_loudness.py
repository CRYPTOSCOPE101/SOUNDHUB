import math
import struct
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.loudness import (  # noqa: E402
    _samples_wav,
    analyse,
    gain_to_match,
    short_term_lufs,
)


def _wav(
    samples: list[int] | list[tuple[int, ...]],
    *,
    sample_rate: int = 8000,
    channels: int = 1,
    bits: int = 16,
    audio_format: int = 1,
    chunks_before_data: list[tuple[bytes, bytes]] | None = None,
) -> bytes:
    if bits == 8:
        raw = bytes(samples)
    elif bits == 16:
        raw = b"".join(
            struct.pack("<h", value)
            for sample in samples
            for value in (sample if isinstance(sample, tuple) else (sample,))
        )
    elif bits == 32:
        raw = b"".join(
            struct.pack("<i", value)
            for sample in samples
            for value in (sample if isinstance(sample, tuple) else (sample,))
        )
    else:
        raise ValueError(bits)
    fmt = struct.pack(
        "<HHIIHH",
        audio_format,
        channels,
        sample_rate,
        sample_rate * channels * bits // 8,
        channels * bits // 8,
        bits,
    )
    chunks = [b"fmt " + struct.pack("<I", len(fmt)) + fmt]
    for chunk_id, body in chunks_before_data or []:
        chunks.append(chunk_id + struct.pack("<I", len(body)) + body)
        if len(body) % 2:
            chunks.append(b"\x00")
    chunks.append(b"data" + struct.pack("<I", len(raw)) + raw)
    body = b"".join(chunks)
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def _tone(duration_ms: int = 500, sample_rate: int = 48000, amplitude: float = 0.25) -> bytes:
    count = sample_rate * duration_ms // 1000
    samples = [
        int(32767 * amplitude * math.sin(2 * math.pi * 440 * i / sample_rate))
        for i in range(count)
    ]
    return _wav(samples, sample_rate=sample_rate)


def test_analyse_rejects_non_wav_and_riff_with_wrong_form():
    assert analyse(b"not audio") == {
        "integrated_lufs": None,
        "true_peak_dbtp": None,
        "sample_rate": None,
        "channels": None,
        "status": "unavailable",
    }
    assert analyse(b"RIFF" + b"\x00" * 4 + b"NOPE")["status"] == "unavailable"


def test_analyse_digital_silence_is_done_but_gated():
    result = analyse(_wav([0] * 4000))

    assert result["integrated_lufs"] is None
    assert result["status"] == "done"
    assert result["true_peak_dbtp"] == -237.0
    assert result["sample_rate"] == 8000
    assert result["channels"] == 1


def test_analyse_tone_reports_loudness_and_true_peak():
    data = _tone()
    result = analyse(data)
    expected_peak = round(20 * math.log10(0.25) + 3, 2)

    assert isinstance(result["integrated_lufs"], float)
    assert -60 < result["integrated_lufs"] < 0
    assert result["true_peak_dbtp"] == pytest.approx(expected_peak, abs=0.02)
    assert result["sample_rate"] == 48000
    assert result["channels"] == 1


def test_samples_wav_decodes_widths_stereo_and_unknown_odd_chunk():
    eight = _samples_wav(_wav([0, 128, 255], bits=8))
    sixteen = _samples_wav(_wav([-32768, 0, 32767], bits=16))
    thirty_two = _samples_wav(_wav([-2147483648, 0, 2147483647], bits=32))
    stereo = _samples_wav(
        _wav([(32767, -32768), (16384, 0)], channels=2, bits=16)
    )
    with_list = _samples_wav(
        _wav([16384], chunks_before_data=[(b"LIST", b"odd")])
    )

    assert eight and eight["samples"] == pytest.approx([-1.0, 0.0, 127 / 128])
    assert sixteen and sixteen["samples"] == pytest.approx([-1.0, 0.0, 32767 / 32768])
    assert thirty_two and thirty_two["samples"] == pytest.approx([-1.0, 0.0, 2147483647 / 2147483648])
    assert stereo and stereo["samples"] == pytest.approx([32767 / 32768, 0.5])
    assert with_list and with_list["samples"] == pytest.approx([0.5])


def test_samples_wav_rejects_non_pcm():
    assert _samples_wav(_wav([0, 1], audio_format=3)) is None


def test_analyse_uses_filters_only_at_supported_sample_rates():
    high_rate = analyse(_tone(duration_ms=400, sample_rate=24000))
    low_rate = analyse(
        _wav([int(32767 * 0.1)] * (8000 * 400 // 1000), sample_rate=8000)
    )

    assert high_rate["status"] == "done"
    assert low_rate["status"] == "done"
    assert isinstance(low_rate["integrated_lufs"], float)


def test_short_term_lufs_handles_short_long_and_clamped_regions():
    short = _wav([1000] * 8000, sample_rate=8000)
    long = _wav([1000] * (8000 * 3500 // 1000), sample_rate=8000)

    assert short_term_lufs(b"bad", 0, 1000) is None
    assert short_term_lufs(short, 0, 399) is None
    assert isinstance(short_term_lufs(short, 0, 1000), float)
    assert isinstance(short_term_lufs(long, -1000, 5000), float)
    assert short_term_lufs(long, 5000, 6000) is None


@pytest.mark.parametrize(
    ("base", "compare", "expected"),
    [
        (None, -12.0, (0.0, 0.0)),
        (-18.0, None, (0.0, 0.0)),
        (-18.0, -12.0, (0.0, -6.0)),
        (-12.0, -18.0, (-6.0, 0.0)),
        (-18.0, -18.0, (0.0, 0.0)),
    ],
)
def test_gain_to_match(base, compare, expected):
    assert gain_to_match(base, compare) == expected
