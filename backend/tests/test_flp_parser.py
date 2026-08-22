from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.daw.base import ParseError  # noqa: E402
from app.services.daw.flp_parser import (  # noqa: E402
    _decode_text,
    _iter_events,
    _read_cstr,
    _read_varint,
    _vst_plugin_name,
    parse_flp,
)
from app.services.daw.fixtures import _flp_ev, _flp_text, make_flp  # noqa: E402


def _chunk(chunk_id: bytes, body: bytes) -> bytes:
    return chunk_id + struct.pack("<I", len(body)) + body


def test_parse_flp_extracts_project_channels_patterns_and_known_version():
    info = parse_flp(
        make_flp(
            bpm=132.5,
            channels=[
                ("Sampler", 0, None),
                ("Native", 2, "Vital"),
                ("Layer", 3, None),
                ("Instrument", 4, "Serum"),
                ("Automation", 5, None),
            ],
            patterns=[("Verse", 3)],
        )
    )

    assert info.format == "FL Studio"
    assert info.format_key == "flp"
    assert info.bpm == 132.5
    assert info.version == "FL Studio 20"
    assert info.extra["project_name"] == "Neon Dreams"
    assert info.extra["author"] == "SoundHub"
    assert [track.name for track in info.tracks] == [
        "Sampler",
        "Native",
        "Layer",
        "Instrument",
        "Automation",
    ]
    assert [track.kind for track in info.tracks] == [
        "sampler",
        "native",
        "layer",
        "instrument",
        "automation",
    ]
    assert info.plugins == ["Vital", "Serum"]
    assert info.extra["patterns"] == [{"name": "Verse", "notes": 3, "length_steps": 288}]
    assert info.extra["total_notes"] == 3


def test_parse_flp_unknown_version_and_channel_sample_and_vst_metadata():
    events = bytearray()
    events += _flp_ev(206, _flp_text("House"))
    events += _flp_ev(64, struct.pack("<H", 1))
    events += _flp_ev(192, _flp_text("Sampler"))
    events += _flp_ev(21, b"\x00")
    events += _flp_ev(196, _flp_text("Samples/Kick.wav"))
    vst = struct.pack("<I", 8)
    vst += struct.pack("<Iq", 54, 4) + b"Plug"
    vst += struct.pack("<Iq", 56, 6) + b"Vendor"
    events += _flp_ev(213, vst)
    data = b"\xf4\x00" + _chunk(b"FLhd", struct.pack("<I", 0x12345678))
    data += _chunk(b"FLdt", bytes(events))

    info = parse_flp(data)

    assert info.version == "FL (marker 0x12345678)"
    assert info.extra["genre"] == "House"
    assert info.samples == ["Samples/Kick.wav"]
    assert info.plugins == ["Plug"]
    assert info.tracks[0].devices == ["Plug"]
    assert info.extra["track_count"] == 1


def test_flp_event_helpers_cover_size_classes_varint_and_text_decoding():
    events = (
        _flp_ev(7, b"A")
        + _flp_ev(64, b"BC")
        + _flp_ev(128, b"DEFG")
        + _flp_ev(192, b"text")
        + _flp_ev(208, b"x" * 130)
    )
    parsed = list(_iter_events(events))

    assert [event_id for event_id, _ in parsed] == [7, 64, 128, 192, 208]
    assert parsed[0][1] == b"A"
    assert parsed[1][1] == b"BC"
    assert parsed[2][1] == b"DEFG"
    assert parsed[3][1] == b"text"
    assert len(parsed[4][1]) == 130
    assert _read_varint(b"\xAC\x02", 0) == (300, 2)
    assert _decode_text("café".encode("utf-16-le")) == "café"
    assert _decode_text(b"plain\x00") == "plain"
    assert _read_cstr(struct.pack("<I", 3) + b"abc", 0) == ("abc", 7)


def test_vst_plugin_name_stops_on_invalid_subrecord():
    blob = struct.pack("<I", 10) + struct.pack("<Iq", 54, 4) + b"Name"
    blob += struct.pack("<Iq", 56, 100) + b"Vendor"

    assert _vst_plugin_name(blob) == ("Name", "")
    assert _vst_plugin_name(b"short") == ("", "")


def test_flp_truncation_and_padding_degrade_without_raising():
    valid = make_flp(patterns=[("One", 1)])
    truncated_event = b"\xf5\x00" + _chunk(b"FLdt", b"\xc2\x05ab")
    truncated_chunk = b"\xf5\x00" + b"FLhd" + struct.pack("<I", 100) + b"\x00"

    info = parse_flp(valid + b"\x00\x00\x00")

    assert info.extra["pattern_count"] == 1
    assert parse_flp(truncated_event).extra["track_count"] == 0
    assert parse_flp(truncated_chunk).extra["track_count"] == 0


@pytest.mark.parametrize("data", [b"", b"\x00\x00"])
def test_parse_flp_rejects_wrong_or_short_input(data):
    with pytest.raises(ParseError):
        parse_flp(data)


def test_parse_flp_accepts_magic_without_complete_chunks():
    assert parse_flp(b"\xf5").format_key == "flp"
