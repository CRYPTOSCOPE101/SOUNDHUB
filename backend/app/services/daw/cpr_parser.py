"""Parser for Steinberg Cubase project files (.cpr).

.cpr files are XML. Cubase's schema is sprawling, so we scan
generically: track elements by tag name, plugins by tag containing
"Plugin", samples by "Sample" tags with a path-ish attribute.
"""
import xml.etree.ElementTree as ET

from .base import DAWInfo, ParseError, TrackInfo
from .xmlutil import local_name

_TRACK_TAGS = {
    "MidiTrack": "midi",
    "AudioTrack": "audio",
    "InstrumentTrack": "instrument",
    "GroupTrack": "group",
    "FolderTrack": "folder",
    "MarkerTrack": "marker",
    "ArrangerTrack": "arranger",
    "ReWireTrack": "rewire",
    "SamplerTrack": "sampler",
}


def parse_cpr(data: bytes) -> DAWInfo:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ParseError(f"bad xml: {exc}") from exc

    info = DAWInfo(format="Cubase", format_key="cpr")
    info.version = root.attrib.get("Version", "")

    # Tempo — look for <TempoTrack><Tempo Value="..."/></TempoTrack> style nodes
    for el in root.iter():
        tag = local_name(el.tag)
        if tag in ("Tempo", "TempoTrack", "ProjectTempo"):
            value = el.attrib.get("Value")
            if value is None:
                value = el.attrib.get("Bpm")
            if value:
                try:
                    info.bpm = float(value)
                    break
                except ValueError:
                    continue

    # Tracks
    for el in root.iter():
        tag = local_name(el.tag)
        if tag in _TRACK_TAGS:
            name = el.attrib.get("Name") or el.attrib.get("TrackName") or ""
            info.tracks.append(TrackInfo(name=name, kind=_TRACK_TAGS[tag]))

    # Plugins: Vst3Plugin / VstPlugin / Vst2Plugin elements carry Name
    for el in root.iter():
        tag = local_name(el.tag)
        if "Plugin" in tag or tag in ("Vst3", "Vst2"):
            name = el.attrib.get("Name") or el.attrib.get("PluginName")
            if name:
                info.plugins.append(name)

    # Samples
    for el in root.iter():
        if local_name(el.tag) == "Sample":
            path = el.attrib.get("Path") or el.attrib.get("Name")
            if path:
                info.samples.append(path)

    info.extra["track_count"] = len(info.tracks)
    return info
