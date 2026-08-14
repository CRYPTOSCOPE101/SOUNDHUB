"""Parser for FL Studio project files (.flp).

.flp is a binary chunk format:
  byte 0: magic 0xF4 (legacy) or 0xF5 (FL 21+)
  then repeating [4-byte chunk id][u32 LE size][payload]

Known chunks:
  FLhd — header, first u32 is the FL version marker
  FLPI — project info: [u32 name_len][name][u32 author_len][author]
         [u32 comment_len][comment][double tempo][s32 pitched]
  FLdt — main event data (we only report its size)
"""
import struct

from .base import DAWInfo, ParseError

_FL_VERSION_LABELS = {
    0x0000000B: "FL Studio 11",
    0x0000000C: "FL Studio 12",
    0x0000000D: "FL Studio 12.3+",
    0x00000064: "FL Studio 20",
    0x00000065: "FL Studio 21",
}


def _read_cstr(buf: bytes, off: int) -> tuple[str, int]:
    (length,) = struct.unpack_from("<I", buf, off)
    start = off + 4
    end = start + length
    return buf[start:end].decode("utf-8", errors="replace"), end


def parse_flp(data: bytes) -> DAWInfo:
    if not data or data[0] not in (0xF4, 0xF5):
        raise ParseError("bad flp magic")

    info = DAWInfo(format="FL Studio", format_key="flp")
    info.extra["magic"] = f"0x{data[0]:02X}" + (" (FL 21+)" if data[0] == 0xF5 else "")

    off = 2  # skip magic byte + version byte (usually 0x00)
    chunk_counts: dict[str, int] = {}
    name = ""
    author = ""

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
            try:
                name, off_a = _read_cstr(body, 0)
                author, off_b = _read_cstr(body, off_a)
                _, off_c = _read_cstr(body, off_b)  # comment
                (tempo,) = struct.unpack_from("<d", body, off_c)
                if 1.0 <= tempo <= 999.0:
                    info.bpm = tempo
            except struct.error:
                pass

        off = body_end

    info.extra["chunks"] = chunk_counts
    info.extra["track_count"] = chunk_counts.get("FLCh", 0)  # channel count chunks
    if name:
        info.extra["project_name"] = name
    if author:
        info.extra["author"] = author

    info.extra["note"] = (
        "Binary format — track/plugin detail requires deep event parsing."
    )
    return info
