"""Diff engine for DAW project files.

Two views:
  * summary  — structured metadata changes (BPM, tracks, plugins, samples)
  * raw      — unified diff of normalized content (pretty XML / text / hex)
"""
import difflib
import gzip
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

from .base import DAWInfo

RAW_DIFF_CAP = 400  # max lines of raw diff returned


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalize_content(path: str, data: bytes) -> str | None:
    """Return a stable, diffable textual form, or None for unknown formats."""
    ext = PurePosixPath(path).suffix.lower()
    if ext == ".als":
        raw = gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
        try:
            root = ET.fromstring(raw)
            ET.indent(root, space="  ")
            return ET.tostring(root, encoding="unicode")
        except ET.ParseError:
            return raw.decode("utf-8", errors="replace")
    if ext == ".cpr":
        try:
            root = ET.fromstring(data)
            ET.indent(root, space="  ")
            return ET.tostring(root, encoding="unicode")
        except ET.ParseError:
            return data.decode("utf-8", errors="replace")
    if ext == ".rpp":
        return data.decode("utf-8", errors="replace")
    if ext == ".flp":
        return hexdump(data)
    return None


def hexdump(data: bytes, width: int = 16) -> str:
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}  {hex_part:<48}  {ascii_part}")
    return "\n".join(lines)


def unified_diff(a_text: str, b_text: str) -> tuple[str, bool]:
    a_lines = a_text.splitlines()
    b_lines = b_text.splitlines()
    diff = list(
        difflib.unified_diff(
            a_lines, b_lines, fromfile="a", tofile="b", lineterm=""
        )
    )
    truncated = len(diff) > RAW_DIFF_CAP
    if truncated:
        diff = diff[:RAW_DIFF_CAP]
        diff.append(f"... (truncated, {len(b_lines) - 0} lines total)")
    return "\n".join(diff), truncated


def _names(info: DAWInfo | None) -> set[str]:
    return {t.name for t in info.tracks} if info else set()


def _set_diff(old: set[str], new: set[str], label: str) -> list[dict]:
    changes = []
    for name in sorted(old - new):
        changes.append(
            {"kind": f"{label}_removed", "label": name, "old": name, "new": None}
        )
    for name in sorted(new - old):
        changes.append(
            {"kind": f"{label}_added", "label": name, "old": None, "new": name}
        )
    return changes


def summary_diff(a: DAWInfo | None, b: DAWInfo | None) -> list[dict]:
    changes: list[dict] = []

    if a is None and b is None:
        return changes
    if a is None:
        changes.append(
            {"kind": "info", "label": "File created", "old": None, "new": b.format}
        )
        return changes
    if b is None:
        changes.append(
            {"kind": "info", "label": "File deleted", "old": a.format, "new": None}
        )
        return changes

    if a.bpm != b.bpm:
        changes.append(
            {
                "kind": "bpm",
                "label": "Tempo (BPM)",
                "old": f"{a.bpm:g}" if a.bpm is not None else "-",
                "new": f"{b.bpm:g}" if b.bpm is not None else "-",
            }
        )
    if a.time_signature != b.time_signature:
        changes.append(
            {
                "kind": "info",
                "label": "Time signature",
                "old": a.time_signature or "-",
                "new": b.time_signature or "-",
            }
        )
    if a.version != b.version:
        changes.append(
            {
                "kind": "info",
                "label": "DAW version",
                "old": a.version or "-",
                "new": b.version or "-",
            }
        )

    changes.extend(_set_diff(_names(a), _names(b), "track"))
    changes.extend(_set_diff(set(a.plugin_set), set(b.plugin_set), "plugin"))
    changes.extend(_set_diff(set(a.samples), set(b.samples), "sample"))
    return changes
