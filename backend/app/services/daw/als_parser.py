"""Parser for Ableton Live project files (.als).

.als files are gzip-compressed XML. We decompress, parse, and extract
tempo, time signature, tracks, devices/plugins and referenced samples.
All extraction is defensive: never raise on unexpected structure.
"""
import gzip
import xml.etree.ElementTree as ET

from .base import DAWInfo, ParseError, TrackInfo

_TRACK_TAGS = {
    "AudioTrack": "audio",
    "MidiTrack": "midi",
    "GroupTrack": "group",
    "ReturnTrack": "return",
    "MasterTrack": "master",
}

_PLUGIN_INFO_TAGS = ("VstPluginInfo", "AudioUnitPluginInfo", "ClapPluginInfo")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _val(el: ET.Element, attr: str = "Value") -> str | None:
    return el.attrib.get(attr)


def _first_descendant(el: ET.Element, local_tag: str) -> ET.Element | None:
    for child in el.iter():
        if _local(child.tag) == local_tag:
            return child
    return None


def _plugin_name(plugin_el: ET.Element) -> str | None:
    """Try to find a human-readable plugin name inside a PluginDevice."""
    for info_tag in _PLUGIN_INFO_TAGS:
        info = _first_descendant(plugin_el, info_tag)
        if info is not None:
            for name_tag in ("PlugName", "Name"):
                name_el = _first_descendant(info, name_tag)
                if name_el is not None and _val(name_el):
                    return _val(name_el)
    return None


def _parse_track(el: ET.Element, kind: str) -> TrackInfo:
    name = ""
    name_el = _first_descendant(el, "EffectiveName")
    if name_el is None:
        name_el = _first_descendant(el, "Name")
    if name_el is not None and _val(name_el):
        name = _val(name_el) or ""
    if not name:
        name = kind.capitalize()

    devices: list[str] = []
    # The first <Devices> container in document order belongs to the
    # track's main device chain (racks nested deeper come later).
    devices_el = _first_descendant(el, "Devices")
    if devices_el is not None:
        for dev in devices_el:
            tag = _local(dev.tag)
            if tag == "PluginDevice":
                pname = _plugin_name(dev)
                devices.append(pname or "PluginDevice")
            elif tag not in ("LomId",):
                devices.append(tag)
    return TrackInfo(name=name, kind=kind, devices=devices)


def parse_als(data: bytes) -> DAWInfo:
    if data[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(data)
        except OSError as exc:
            raise ParseError(f"bad gzip: {exc}") from exc
    else:
        raw = data
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ParseError(f"bad xml: {exc}") from exc

    info = DAWInfo(format="Ableton Live", format_key="als")
    info.version = (
        f"{_val(root, 'MajorVersion')}.{_val(root, 'MinorVersion')}" or ""
    )

    live_set = _first_descendant(root, "LiveSet")
    if live_set is None:
        raise ParseError("no LiveSet found")

    # Tempo
    tempo_el = _first_descendant(live_set, "Tempo")
    if tempo_el is not None:
        manual = _first_descendant(tempo_el, "Manual")
        if manual is not None and _val(manual):
            try:
                info.bpm = float(_val(manual) or 0)
            except ValueError:
                info.bpm = None

    # Time signature
    ts_el = _first_descendant(live_set, "TimeSignature")
    if ts_el is not None:
        num = _first_descendant(ts_el, "Numerator")
        den = _first_descendant(ts_el, "Denominator")
        if num is not None and den is not None:
            info.time_signature = f"{_val(num)}/{_val(den)}"

    # Tracks
    tracks_el = None
    for child in live_set:
        if _local(child.tag) == "Tracks":
            tracks_el = child
            break
    if tracks_el is not None:
        for track_el in tracks_el:
            tag = _local(track_el.tag)
            if tag in _TRACK_TAGS:
                info.tracks.append(_parse_track(track_el, _TRACK_TAGS[tag]))

    # Plugins (also scans inside racks/groups)
    for plugin_el in live_set.iter():
        if _local(plugin_el.tag) == "PluginDevice":
            pname = _plugin_name(plugin_el)
            if pname:
                info.plugins.append(pname)

    # Samples — names live on RelativePathElement inside Path
    for sample_ref in live_set.iter():
        if _local(sample_ref.tag) == "SampleRef":
            rel = _first_descendant(sample_ref, "RelativePathElement")
            if rel is not None:
                name = _val(rel, "Name")
                directory = _val(rel, "Dir")
                if name:
                    info.samples.append(f"{directory}/{name}" if directory else name)

    # Presets — the saved settings of an instrument/device live in preset
    # files (.adv/.adg/.xpl) referenced from the set. We list them so a
    # pushed project keeps the instrument state findable (the full plugin
    # state itself stays inside the project files that get uploaded).
    presets: list[str] = []
    for preset_ref in live_set.iter():
        if _local(preset_ref.tag) == "PresetRef":
            rel = _first_descendant(preset_ref, "RelativePathElement")
            if rel is not None and _val(rel, "Name"):
                directory = _val(rel, "Dir") or ""
                presets.append(f"{directory}/{_val(rel, 'Name')}" if directory else _val(rel, "Name"))
    if presets:
        info.extra["presets"] = sorted(set(presets))

    info.extra["track_count"] = len(info.tracks)
    return info
