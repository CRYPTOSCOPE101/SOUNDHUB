"""Parser for FL Studio project files (.flp).

.flp is a binary format: a magic byte (0xF4 legacy / 0xF5 FL 21+), then a
sequence of chunks: [4-byte id][u32 LE size][payload]. The two chunks that
matter are:

  FLhd — header; first u32 is the internal FL version marker.
  FLdt — the data chunk: a stream of TLV "events".

Events are the interesting part. Each event is:

  [u8 type][value]

where the value size depends on the type:
  type 0-63    → 1 byte
  type 64-127  → 2 bytes   (WORD  base)
  type 128-191 → 4 bytes   (DWORD base)
  type 192-207 → text      (TEXT  base; varint length + data)
  type 208-255 → data/struct (DATA base; varint length + data)

Known event IDs (this is reverse-engineered; see the FLP community docs /
PyFLP/libflp):
  Project: Tempo = 128+28 (u32, BPM × 1000) · Title = 192+2 ·
           Artists = 192+15 · Genre = 192+14 · FLVersion = 192+7 (ascii)
  Channel: New = 64 (u16 iid) · Type = 21 (u8: 0 sampler, 2 native,
           3 layer, 4 instrument, 5 automation) · Name = 192 ·
           SamplePath = 192+4
  Plugin:  InternalName = 192+9 · Name = 192+11 · Data = 208+5
           (VST blob: [u32 marker 8|10][(u32 id)(i64 len)(data)…],
           id 54 = factory name, 56 = vendor, 55 = path)
  Pattern: New = 65 (u16 iid, occurs twice) · Name = 192+1 ·
           Color = 128+22 · Length = 128+36 · Notes = 208+16
           (repeated 24-byte note structs: position, flags, rack channel,
           length, key, group, fine pitch, release, midi channel, pan,
           velocity, mod x, mod y) · Controllers = 208+15

All extraction is defensive: truncated/corrupt files degrade to what could
be read (the chunk walker already stops at padding).
"""

import logging
import struct

from .base import DAWInfo, ParseError, TrackInfo

logger = logging.getLogger(__name__)

_FL_VERSION_LABELS = {
    0x0000000B: "FL Studio 11",
    0x0000000C: "FL Studio 12",
    0x0000000D: "FL Studio 12.3+",
    0x00000064: "FL Studio 20",
    0x00000065: "FL Studio 21",
}

# event id bases
_WORD = 64
_DWORD = 128
_TEXT = 192
_DATA = 208

# specific ids used by the parser
_EV_PROJECT_TEMPO = _DWORD + 28
_EV_PROJECT_TITLE = _TEXT + 2
_EV_PROJECT_ARTISTS = _TEXT + 15
_EV_PROJECT_GENRE = _TEXT + 14
_EV_PROJECT_FL_VERSION = _TEXT + 7
_EV_CHANNEL_NEW = _WORD
_EV_CHANNEL_TYPE = 21
_EV_CHANNEL_NAME = _TEXT
_EV_CHANNEL_SAMPLE_PATH = _TEXT + 4
_EV_PLUGIN_INTERNAL_NAME = _TEXT + 9
_EV_PLUGIN_NAME = _TEXT + 11
_EV_PLUGIN_DATA = _DATA + 5
_EV_PATTERN_NEW = _WORD + 1
_EV_PATTERN_NAME = _TEXT + 1
_EV_PATTERN_COLOR = _DWORD + 22
_EV_PATTERN_LENGTH = _DWORD + 36
_EV_PATTERN_NOTES = _DATA + 16

# VST sub-event ids inside a Plugin.Data blob
_VST_NAME = 54
_VST_VENDOR = 56

_CHANNEL_TYPE_LABELS = {
    0: "sampler",
    2: "native",
    3: "layer",
    4: "instrument",
    5: "automation",
}

_NOTE_STRUCT_SIZE = 24  # bytes per note in a Pattern.Notes event


def _read_cstr(buf: bytes, off: int) -> tuple[str, int]:
    (length,) = struct.unpack_from("<I", buf, off)
    start = off + 4
    end = start + length
    return buf[start:end].decode("utf-8", errors="replace"), end


def _read_varint(buf: bytes, off: int) -> tuple[int, int]:
    """LEB128-style varint (7 bits per byte, MSB = continuation)."""
    result = 0
    shift = 0
    while True:
        if off >= len(buf):
            raise ParseError("truncated varint")
        b = buf[off]
        off += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, off
        shift += 7


def _decode_text(data: bytes) -> str:
    """Strings in .flp are UTF-16-LE (older files: plain ascii)."""
    if len(data) >= 2 and data[1::2] == b"\x00" * (len(data) // 2):
        return data.decode("utf-16-le", errors="replace").rstrip("\x00")
    return data.decode("utf-8", errors="replace").rstrip("\x00")


def _iter_events(body: bytes):
    """Yield (event_id, value_bytes) from an FLdt payload."""
    off = 0
    n = len(body)
    while off < n:
        etype = body[off]
        off += 1
        if etype < _WORD:
            size = 1
        elif etype < _DWORD:
            size = 2
        elif etype < _TEXT:
            size = 4
        else:
            try:
                size, off = _read_varint(body, off)
            except ParseError as exc:
                logger.debug("flp: corrupt event varint at offset %d: %s", off, exc)
                return
        if off + size > n:
            return  # truncated — stop, keep what we have
        yield etype, body[off : off + size]
        off += size


def _u16(v: bytes) -> int:
    return struct.unpack("<H", v[:2])[0] if len(v) >= 2 else 0


def _u32(v: bytes) -> int:
    return struct.unpack("<I", v[:4])[0] if len(v) >= 4 else 0


def _vst_plugin_name(data: bytes) -> tuple[str, str]:
    """Parse a Plugin.Data VST blob → (name, vendor). Best-effort."""
    if len(data) < 4:
        return "", ""
    off = 4  # skip the 8|10 marker
    name = ""
    vendor = ""
    while off + 12 <= len(data):
        (sub_id,) = struct.unpack_from("<I", data, off)
        (length,) = struct.unpack_from("<q", data, off + 4)
        start = off + 12
        end = start + length
        if length < 0 or end > len(data):
            break
        payload = data[start:end]
        if sub_id == _VST_NAME:
            name = payload.decode("utf-8", errors="replace").rstrip("\x00")
        elif sub_id == _VST_VENDOR:
            vendor = payload.decode("utf-8", errors="replace").rstrip("\x00")
        off = end
    return name, vendor


def parse_flp(data: bytes) -> DAWInfo:
    if not data or data[0] not in (0xF4, 0xF5):
        raise ParseError("bad flp magic")

    info = DAWInfo(format="FL Studio", format_key="flp")
    info.extra["magic"] = f"0x{data[0]:02X}" + (" (FL 21+)" if data[0] == 0xF5 else "")

    off = 2  # skip magic byte + version byte (usually 0x00)
    chunk_counts: dict[str, int] = {}
    name = ""
    author = ""

    # collected from FLdt events
    project_title = ""
    project_artists = ""
    project_genre = ""
    project_tempo: float | None = None
    project_fl_version = ""

    channels: dict[int, dict] = {}  # iid -> {name, type, plugins: [str]}
    cur_channel: int | None = None
    patterns: dict[int, dict] = {}  # iid -> {name, note_count, length}
    cur_pattern: int | None = None

    while off + 8 <= len(data):
        chunk_id = data[off : off + 4]
        (size,) = struct.unpack_from("<I", data, off + 4)
        body_off = off + 8
        body_end = body_off + size
        if body_end > len(data):
            break  # truncated or trailing padding
        body = data[body_off:body_end]
        key = chunk_id.decode("latin-1", errors="replace")
        chunk_counts[key] = chunk_counts.get(key, 0) + 1

        if key == "FLhd" and len(body) >= 4:
            (ver,) = struct.unpack_from("<I", body, 0)
            info.extra["fl_version_marker"] = f"0x{ver:08X}"
            info.version = _FL_VERSION_LABELS.get(ver, f"FL (marker 0x{ver:08X})")

        elif key == "FLPI" and len(body) >= 8:
            # Legacy/alternate project-info chunk (kept for compatibility).
            try:
                name, off_a = _read_cstr(body, 0)
                author, off_b = _read_cstr(body, off_a)
                _, off_c = _read_cstr(body, off_b)  # comment
                (tempo,) = struct.unpack_from("<d", body, off_c)
                if 1.0 <= tempo <= 999.0:
                    info.bpm = tempo
            except struct.error as exc:
                logger.debug("flp: unreadable FLPI chunk (%d bytes): %s", len(body), exc)

        elif key == "FLdt":
            # Deep parsing: channels, plugins, patterns, project metadata.
            for etype, value in _iter_events(body):
                if etype == _EV_CHANNEL_NEW:
                    iid = _u16(value)
                    cur_channel = iid
                    channels.setdefault(iid, {"name": "", "type": "", "plugins": []})
                elif etype == _EV_CHANNEL_NAME and cur_channel is not None:
                    channels[cur_channel]["name"] = _decode_text(value)
                elif etype == _EV_CHANNEL_TYPE and cur_channel is not None:
                    channels[cur_channel]["type"] = _CHANNEL_TYPE_LABELS.get(
                        value[0], f"type_{value[0]}"
                    )
                elif etype == _EV_CHANNEL_SAMPLE_PATH and cur_channel is not None:
                    sp = _decode_text(value)
                    if sp and sp not in info.samples:
                        info.samples.append(sp)
                elif etype == _EV_PATTERN_NEW:
                    iid = _u16(value)
                    cur_pattern = iid
                    patterns.setdefault(iid, {"name": "", "note_count": 0, "length": 0})
                elif etype == _EV_PATTERN_NAME and cur_pattern is not None:
                    patterns[cur_pattern]["name"] = _decode_text(value)
                elif etype == _EV_PATTERN_LENGTH and cur_pattern is not None:
                    patterns[cur_pattern]["length"] = _u32(value)
                elif etype == _EV_PATTERN_NOTES and cur_pattern is not None:
                    if _NOTE_STRUCT_SIZE and len(value) % _NOTE_STRUCT_SIZE == 0:
                        patterns[cur_pattern]["note_count"] = len(value) // _NOTE_STRUCT_SIZE
                elif etype == _EV_PLUGIN_NAME and cur_channel is not None:
                    pname = _decode_text(value)
                    if pname and pname not in channels[cur_channel]["plugins"]:
                        channels[cur_channel]["plugins"].append(pname)
                elif etype == _EV_PLUGIN_DATA and cur_channel is not None:
                    vst_name, _vendor = _vst_plugin_name(value)
                    if vst_name and vst_name not in channels[cur_channel]["plugins"]:
                        channels[cur_channel]["plugins"].append(vst_name)
                elif etype == _EV_PROJECT_TEMPO:
                    t = _u32(value) / 1000.0
                    if 1.0 <= t <= 999.0:
                        project_tempo = t
                elif etype == _EV_PROJECT_TITLE:
                    project_title = _decode_text(value)
                elif etype == _EV_PROJECT_ARTISTS:
                    project_artists = _decode_text(value)
                elif etype == _EV_PROJECT_GENRE:
                    project_genre = _decode_text(value)
                elif etype == _EV_PROJECT_FL_VERSION:
                    project_fl_version = _decode_text(value)

        off = body_end

    # ---- fold the deep data into DAWInfo ----
    if project_tempo is not None and info.bpm is None:
        info.bpm = project_tempo
    if project_fl_version and not info.version:
        info.version = f"FL {project_fl_version}"
    if project_title:
        info.extra["project_name"] = project_title
    if project_artists:
        info.extra["author"] = project_artists
    if project_genre:
        info.extra["genre"] = project_genre

    for iid in sorted(channels):
        ch = channels[iid]
        devices = list(ch["plugins"])
        info.tracks.append(
            TrackInfo(name=ch["name"] or f"Channel {iid}", kind=ch["type"] or "audio", devices=devices)
        )
        for p in ch["plugins"]:
            if p not in info.plugins:
                info.plugins.append(p)

    if patterns:
        info.extra["patterns"] = [
            {
                "name": p["name"] or f"Pattern {iid}",
                "notes": p["note_count"],
                "length_steps": p["length"],
            }
            for iid, p in sorted(patterns.items())
        ]
        info.extra["pattern_count"] = len(patterns)
        info.extra["total_notes"] = sum(p["note_count"] for p in patterns.values())

    info.extra["chunks"] = chunk_counts
    info.extra["track_count"] = len(channels)
    if name:
        info.extra["project_name"] = info.extra.get("project_name") or name
    if author:
        info.extra["author"] = info.extra.get("author") or author

    info.extra["note"] = (
        "Deep parse: channels + plugins (VST names where stored), patterns "
        "with note counts. Settings may be incomplete for very old files."
    )
    return info
