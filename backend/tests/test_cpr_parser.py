from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.daw.base import ParseError  # noqa: E402
from app.services.daw.cpr_parser import parse_cpr  # noqa: E402
from app.services.daw.fixtures import make_cpr  # noqa: E402


def test_parse_cpr_extracts_metadata_tracks_plugins_and_samples():
    info = parse_cpr(
        make_cpr(
            bpm=122.5,
            version="14.0",
            tracks=[("MidiTrack", "Keys"), ("AudioTrack", "Vocal")],
        )
    )

    assert info.format == "Cubase"
    assert info.format_key == "cpr"
    assert info.bpm == 122.5
    assert info.version == "14.0"
    assert [(track.name, track.kind) for track in info.tracks] == [
        ("Keys", "midi"),
        ("Vocal", "audio"),
    ]
    assert info.plugins == ["Serum"]
    assert info.extra["track_count"] == len(info.tracks)


def test_parse_cpr_handles_namespaces_all_track_kinds_and_fallback_attributes():
    xml = b"""
    <Project xmlns="urn:cubase" Version="12">
      <Tempo Bpm="118"/>
      <MidiTrack Name="MIDI"/>
      <AudioTrack TrackName="Audio"/>
      <InstrumentTrack Name="Instrument"/>
      <GroupTrack Name="Group"/>
      <FolderTrack Name="Folder"/>
      <MarkerTrack Name="Marker"/>
      <ArrangerTrack Name="Arranger"/>
      <ReWireTrack Name="ReWire"/>
      <SamplerTrack Name="Sampler"/>
      <Vst3Plugin PluginName="FallbackPlugin"/>
      <VstPlugin/>
      <Sample Name="only-name.wav"/>
    </Project>
    """
    info = parse_cpr(xml)

    assert info.bpm == 118.0
    assert [track.kind for track in info.tracks] == [
        "midi",
        "audio",
        "instrument",
        "group",
        "folder",
        "marker",
        "arranger",
        "rewire",
        "sampler",
    ]
    assert [track.name for track in info.tracks][1] == "Audio"
    assert info.plugins == ["FallbackPlugin"]
    assert info.samples == ["only-name.wav"]


def test_parse_cpr_skips_bad_tempo_until_valid_and_supports_plugin_name():
    xml = b"""
    <Project Version="1">
      <Tempo Value="not-a-number"/>
      <ProjectTempo Value="124"/>
      <Vst2Plugin PluginName="Synth"/>
    </Project>
    """

    info = parse_cpr(xml)

    assert info.bpm == 124.0
    assert info.plugins == ["Synth"]


def test_parse_cpr_without_tempo_leaves_bpm_none():
    info = parse_cpr(b"<Project Version='1'><Track/></Project>")
    assert info.bpm is None


def test_parse_cpr_summary_and_dict_are_normalized():
    info = parse_cpr(make_cpr())

    summary = info.summary_text()
    as_dict = info.to_dict()

    assert "FORMAT: Cubase (13.0.40)" in summary
    assert "TRACK: Synth Lead [midi]" in summary
    assert "PLUGIN: Serum" in summary
    assert as_dict["format_key"] == "cpr"
    assert as_dict["extra"]["track_count"] == 2


@pytest.mark.parametrize("data", [b"", b"not xml", b"<Project>"])
def test_parse_cpr_rejects_malformed_xml(data):
    with pytest.raises(ParseError):
        parse_cpr(data)
