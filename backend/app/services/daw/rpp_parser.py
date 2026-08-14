"""Parser for REAPER project files (.rpp).

.rpp is a plain-text format. The project init line carries version,
tempo and time signature; tracks are <TRACK> blocks containing
<NAME "..." /> lines; FX live in <VST "..."/> / <VST3 "..."/> lines.
"""
import re

from .base import DAWInfo, ParseError, TrackInfo

_TRACK_OPEN = re.compile(r"^\s*<TRACK\b", re.MULTILINE)
_NAME_LINE = re.compile(r'^\s*<NAME\s+"([^"]*)"', re.MULTILINE)
_TEMPO_LINE = re.compile(r"^\s*<TEMPO\s+([\d\.]+)\s+(\d+)\s+(\d+)\s*>", re.MULTILINE)
_REAPER_HEADER = re.compile(r'^<REAPER_PROJECT[^"]*"([^"]+)"', re.MULTILINE)
_FX_LINE = re.compile(r'^\s*<(VST3?|JS|AU|CLAP)[^"]*"([^"]+)"', re.MULTILINE)
_PROJECT_NAME = re.compile(r'^\s*<PROJECT\s+([^\s"]+)', re.IGNORECASE | re.MULTILINE)


def parse_rpp(data: bytes) -> DAWInfo:
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"decode failed: {exc}") from exc

    info = DAWInfo(format="REAPER", format_key="rpp")

    header = _REAPER_HEADER.search(text)
    if header:
        info.version = header.group(1)

    # Tempo + time signature
    tempo = _TEMPO_LINE.search(text)
    if tempo:
        info.bpm = float(tempo.group(1))
        info.time_signature = f"{tempo.group(2)}/{tempo.group(3)}"

    # Tracks: every <TRACK open, name from the next <NAME> line
    lines = text.splitlines()
    in_track = False
    for line in lines:
        if _TRACK_OPEN.match(line):
            in_track = True
            continue
        if in_track and _NAME_LINE.match(line):
            name = _NAME_LINE.match(line).group(1)
            info.tracks.append(TrackInfo(name=name, kind="track"))
            in_track = False

    # FX / plugins
    for m in _FX_LINE.finditer(text):
        kind, name = m.group(1), m.group(2)
        info.plugins.append(f"{kind}: {name}")

    # Items (audio/midi clips)
    info.extra["item_count"] = len(re.findall(r"^\s*<ITEM\b", text, re.MULTILINE))
    info.extra["track_count"] = len(re.findall(r"^\s*<TRACK\b", text, re.MULTILINE))
    return info
