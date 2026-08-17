"""Generators for realistic sample DAW project files.

Used by the demo seed script and the test suite.
"""
import gzip
import struct

# ---------------------------------------------------------------------------
# Ableton Live (.als) — gzip-compressed XML
# ---------------------------------------------------------------------------


def _als_track(kind: str, name: str, devices: list[str]) -> str:
    dev_xml = ""
    for d in devices:
        if d.startswith("Plugin:"):
            plug = d.split(":", 1)[1]
            dev_xml += (
                f"<PluginDevice><PluginDesc><VstPluginInfo>"
                f"<PlugName Value=\"{plug}\"/></VstPluginInfo></PluginDesc></PluginDevice>"
            )
        else:
            dev_xml += f"<{d}/>"
    return (
        f"<{kind}><Name><EffectiveName Value=\"{name}\"/></Name>"
        f"<DeviceChain><DeviceChain><Devices>{dev_xml}</Devices>"
        f"</DeviceChain></DeviceChain></{kind}>"
    )


def make_als(
    bpm: float = 128.0,
    time_sig: tuple[int, int] = (4, 4),
    tracks: list[tuple[str, str, list[str]]] | None = None,
    samples: list[str] | None = None,
    major: str = "12",
    minor: str = "0",
) -> bytes:
    if tracks is None:
        tracks = [
            ("MidiTrack", "Synth Lead", ["Plugin:Serum"]),
            ("AudioTrack", "Drums", ["Compressor2"]),
            ("MasterTrack", "Master", ["Limiter"]),
        ]
    tracks_xml = "".join(_als_track(k, n, d) for k, n, d in tracks)
    samples_xml = "".join(
        f"<SampleRef><FileRef><Path><RelativePathElement Dir=\"Samples\" "
        f"Name=\"{s}\"/></Path></FileRef></SampleRef>"
        for s in (samples or ["Kick.wav", "Clap.wav"])
    )
    num, den = time_sig
    xml = (
        f"<Ableton MajorVersion=\"{major}\" MinorVersion=\"{minor}\">"
        f"<LiveSet><LomId Value=\"0\"/>"
        f"<Tracks>{tracks_xml}</Tracks>"
        f"<Tempo><Manual Value=\"{bpm}\"/></Tempo>"
        f"<TimeSignature><Numerator Value=\"{num}\"/><Denominator Value=\"{den}\"/></TimeSignature>"
        f"<SampleRefs>{samples_xml}</SampleRefs>"
        f"</LiveSet></Ableton>"
    )
    return gzip.compress(xml.encode())


# ---------------------------------------------------------------------------
# Cubase (.cpr) — plain XML
# ---------------------------------------------------------------------------


def make_cpr(
    bpm: float = 128.0,
    version: str = "13.0.40",
    tracks: list[tuple[str, str]] | None = None,
) -> bytes:
    if tracks is None:
        tracks = [("MidiTrack", "Synth Lead"), ("AudioTrack", "Drums")]
    tracks_xml = ""
    for kind, name in tracks:
        if kind == "MidiTrack":
            tracks_xml += (
                f"<MidiTrack Name=\"{name}\"><Events/><Inserts>"
                f"<Vst3Plugin Name=\"Serum\"/></Inserts></MidiTrack>"
            )
        else:
            tracks_xml += f"<{kind} Name=\"{name}\"><Events/></{kind}>"
    xml = (
        f"<CubaseProject Version=\"{version}\">"
        f"<SoloProject ProjectName=\"Neon Dreams\"><Project>{tracks_xml}</Project>"
        f"<TempoTrack><Tempo Value=\"{bpm}\"/></TempoTrack>"
        f"</SoloProject></CubaseProject>"
    )
    return xml.encode()


# ---------------------------------------------------------------------------
# REAPER (.rpp) — text format
# ---------------------------------------------------------------------------


def make_rpp(
    bpm: float = 128.0,
    time_sig: tuple[int, int] = (4, 4),
    version: str = "6.83/x64",
    tracks: list[tuple[str, str]] | None = None,
) -> bytes:
    if tracks is None:
        tracks = [("Drums", "VST3:ReaComp (Cockos)"), ("Synth Lead", "VST3:Serum (Xfer Records)")]
    num, den = time_sig
    lines = [
        f'<REAPER_PROJECT 0.1 "{version}" 1712345678',
        "  <RIPPLE 0>",
        "  <PROJECT Bay",
        f"  <TEMPO {bpm} {num} {den}>",
    ]
    for name, fx in tracks:
        lines.append("  <TRACK")
        lines.append(f'    <NAME "{name}"')
        lines.append("    <FXCHAIN")
        lines.append(f'      <VST "{fx}" reaper.dll 0 "" 1 0')
        lines.append("    >")
        lines.append("  >")
    lines.append("  <ITEM")
    lines.append("    <POSITION 0 0 0 0 0 0 0 0>")
    lines.append("    <LENGTH 4 0 0 0 0 0 0 0>")
    lines.append("  >")
    lines.append(">")
    return "\n".join(lines).encode()


# ---------------------------------------------------------------------------
# FL Studio (.flp) — binary chunk format
# ---------------------------------------------------------------------------


def _flp_chunk(cid: bytes, body: bytes) -> bytes:
    return cid + struct.pack("<I", len(body)) + body


def _flp_ev(etype: int, value: bytes) -> bytes:
    """Serialize one FLdt event: [u8 type][value], length-prefixed for 192+."""
    if etype < 64:
        return bytes([etype]) + value[:1]
    if etype < 128:
        return bytes([etype]) + value[:2]
    if etype < 192:
        return bytes([etype]) + value[:4]
    # 192+: varint length + data
    length = len(value)
    varint = bytearray()
    while True:
        b = length & 0x7F
        length >>= 7
        if length:
            varint.append(b | 0x80)
        else:
            varint.append(b)
            break
    return bytes([etype]) + bytes(varint) + value


def _flp_text(s: str) -> bytes:
    """UTF-16-LE text, as real FL Studio writes it."""
    return s.encode("utf-16-le")


def _flp_note(position: int, key: int, velocity: int = 100, length: int = 96) -> bytes:
    """A 24-byte note struct as stored in a Pattern.Notes event."""
    return struct.pack(
        "<IHHIHHBBBBBBBB",
        position,  # u32
        0,         # u16 flags
        0,         # u16 rack channel
        length,    # u32
        key,       # u16
        0,         # u16 group
        120,       # u8 fine pitch
        0,         # u8
        64,        # u8 release
        0,         # u8 midi channel
        64,        # u8 pan
        velocity,  # u8
        128,       # u8 mod x
        128,       # u8 mod y
    )


def make_flp(
    bpm: float = 140.0,
    project_name: str = "Neon Dreams",
    author: str = "SoundHub",
    fl_version: int = 0x00000064,
    channels: list[tuple[str, int, str | None]] | None = None,
    patterns: list[tuple[str, int]] | None = None,
) -> bytes:
    """A realistic .flp: FLhd + FLPI (legacy info) + FLdt with events.

    channels: (name, type, plugin_name|None) — type 4 = instrument, 0 = sampler.
    patterns: (name, note_count).
    """
    flhd = struct.pack("<I", fl_version)

    def cstr(s: str) -> bytes:
        b = s.encode("utf-8")
        return struct.pack("<I", len(b)) + b

    flpi = (
        cstr(project_name)
        + cstr(author)
        + cstr("")
        + struct.pack("<d", bpm)
        + struct.pack("<i", 0)  # pitched
        + struct.pack("<i", 0)  # new tempo type
    )

    # ---- FLdt events: project meta + channels + patterns ----
    events = bytearray()
    # project: tempo (u32, BPM × 1000), title, artists, FL version (ascii)
    events += _flp_ev(156, struct.pack("<I", int(bpm * 1000)))
    events += _flp_ev(194, _flp_text(project_name))
    events += _flp_ev(207, _flp_text(author))
    events += _flp_ev(199, f"{fl_version >> 24}.0.0".encode("ascii"))

    if channels is None:
        channels = [("Synth Lead", 4, "Serum"), ("Kick", 0, None)]
    for i, (ch_name, ch_type, plugin) in enumerate(channels, start=1):
        events += _flp_ev(64, struct.pack("<H", i))       # Channel.New
        events += _flp_ev(192, _flp_text(ch_name))          # Channel.Name
        events += _flp_ev(21, bytes([ch_type]))             # Channel.Type
        if plugin:
            events += _flp_ev(203, _flp_text(plugin))       # Plugin.Name

    if patterns is None:
        patterns = [("Pattern 1", 8), ("Pattern 2", 16)]
    for i, (pat_name, note_count) in enumerate(patterns, start=1):
        events += _flp_ev(65, struct.pack("<H", i))        # Pattern.New
        notes = b"".join(_flp_note(0, 60 + (k % 12)) for k in range(note_count))
        events += _flp_ev(224, notes)                       # Pattern.Notes
        events += _flp_ev(65, struct.pack("<H", i))        # Pattern.New (2nd occurrence)
        events += _flp_ev(193, _flp_text(pat_name))         # Pattern.Name
        events += _flp_ev(164, struct.pack("<I", note_count * 96))  # Pattern.Length

    fldt = bytes(events)

    return b"\xf5\x00" + _flp_chunk(b"FLhd", flhd) + _flp_chunk(b"FLPI", flpi) + _flp_chunk(b"FLdt", fldt)


# ---------------------------------------------------------------------------
# tiny fake audio file for samples
# ---------------------------------------------------------------------------


def make_wav(duration_ms: int = 200) -> bytes:
    """A minimal valid WAV (44-byte header + silent samples)."""
    import math

    rate = 8000
    n = int(rate * duration_ms / 1000)
    data = bytearray()
    for i in range(n):
        v = int(32767 * 0.3 * math.sin(2 * math.pi * 440 * i / rate))
        data += struct.pack("<h", v)
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    return bytes(header) + bytes(data)
