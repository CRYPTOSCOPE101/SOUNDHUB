import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.daw.diff_engine import normalize_content, summary_diff  # noqa: E402
from app.services.daw.fixtures import make_als, make_cpr, make_flp, make_rpp  # noqa: E402
from app.services.daw.registry import detect_format, get_daw_info  # noqa: E402


def test_detect_als():
    assert detect_format("x.als") == "als"
    assert detect_format("x.als", make_als()) == "als"
    assert detect_format("unknown.bin", make_als()) == "als"


def test_parse_als():
    info = get_daw_info("Neon.als", make_als(bpm=128.0))
    assert info is not None
    assert info.format == "Ableton Live"
    assert info.bpm == 128.0
    assert info.time_signature == "4/4"
    names = [t.name for t in info.tracks]
    assert "Synth Lead" in names and "Drums" in names and "Master" in names
    assert "Serum" in info.plugins
    assert any("Kick.wav" in s for s in info.samples)


def test_parse_als_changed():
    a = get_daw_info("Neon.als", make_als(bpm=128.0))
    b = get_daw_info(
        "Neon.als",
        make_als(
            bpm=132.0,
            tracks=[
                ("MidiTrack", "Synth Lead", ["Plugin:Serum"]),
                ("MidiTrack", "Pad", ["Plugin:Vital"]),
                ("AudioTrack", "Drums", ["Compressor2"]),
                ("MasterTrack", "Master", ["Limiter"]),
            ],
        ),
    )
    changes = summary_diff(a, b)
    kinds = {c["kind"] for c in changes}
    assert "bpm" in kinds
    assert "track_added" in kinds
    assert "plugin_added" in kinds


def test_parse_cpr():
    info = get_daw_info("Neon.cpr", make_cpr(bpm=120.0))
    assert info is not None
    assert info.format == "Cubase"
    assert info.bpm == 120.0
    names = [t.name for t in info.tracks]
    assert "Synth Lead" in names and "Drums" in names
    assert "Serum" in info.plugins
    assert info.version == "13.0.40"


def test_parse_rpp():
    info = get_daw_info("Neon.rpp", make_rpp(bpm=95.0, time_sig=(7, 8)))
    assert info is not None
    assert info.format == "REAPER"
    assert info.bpm == 95.0
    assert info.time_signature == "7/8"
    names = [t.name for t in info.tracks]
    assert "Drums" in names and "Synth Lead" in names
    assert any("Serum" in p for p in info.plugins)
    assert "6.83/x64" in info.version


def test_parse_flp():
    info = get_daw_info("Neon.flp", make_flp(bpm=140.0))
    assert info is not None
    assert info.format == "FL Studio"
    assert info.bpm == 140.0
    assert info.extra["project_name"] == "Neon Dreams"
    assert "FLhd" in info.extra["chunks"]


def test_parse_flp_deep_channels_plugins_and_patterns():
    """Deep .flp parse: per-channel plugins, patterns with note counts."""
    info = get_daw_info(
        "Neon.flp",
        make_flp(
            bpm=140.0,
            channels=[
                ("Synth Lead", 4, "Serum"),
                ("Kick", 0, None),
                ("Pad", 4, "Vital"),
            ],
            patterns=[("Pattern 1", 8), ("Drops", 32)],
        ),
    )
    assert info is not None
    # channels become tracks with kind + plugin devices
    tracks = {t.name: t for t in info.tracks}
    assert set(tracks) == {"Synth Lead", "Kick", "Pad"}
    assert tracks["Synth Lead"].kind == "instrument"
    assert tracks["Synth Lead"].devices == ["Serum"]
    assert tracks["Kick"].kind == "sampler"
    assert tracks["Kick"].devices == []
    assert "Serum" in info.plugins and "Vital" in info.plugins
    # patterns carry names + note counts
    pats = {p["name"]: p for p in info.extra["patterns"]}
    assert pats["Pattern 1"]["notes"] == 8
    assert pats["Drops"]["notes"] == 32
    assert info.extra["total_notes"] == 40
    assert info.extra["track_count"] == 3


def test_flp_deep_diff_shows_channel_and_plugin_changes():
    """Smart diff on .flp now surfaces added channels + plugins."""
    a = get_daw_info("Neon.flp", make_flp(bpm=140.0))
    b = get_daw_info(
        "Neon.flp",
        make_flp(
            bpm=150.0,
            channels=[("Synth Lead", 4, "Serum"), ("Kick", 0, None), ("Pad", 4, "Vital")],
            patterns=[("Pattern 1", 8)],
        ),
    )
    changes = summary_diff(a, b)
    kinds = {c["kind"] for c in changes}
    assert "bpm" in kinds
    assert "track_added" in kinds
    assert "plugin_added" in kinds


def test_normalize_and_diff():
    a = make_als(bpm=128.0)
    b = make_als(bpm=132.0)
    ta = normalize_content("Neon.als", a)
    tb = normalize_content("Neon.als", b)
    assert ta is not None and tb is not None
    from app.services.daw.diff_engine import unified_diff

    raw, truncated = unified_diff(ta, tb)
    assert raw != ""
    assert truncated is False


def test_flp_is_binary_diff():
    from app.services.daw.diff_engine import normalize_content

    text = normalize_content("Neon.flp", make_flp(bpm=128.0))
    assert "FLhd" in text  # hexdump shows chunk ids
