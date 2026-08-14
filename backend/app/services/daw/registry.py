"""Detect DAW project formats and dispatch to parsers."""
from pathlib import PurePosixPath

from .als_parser import parse_als
from .base import DAWInfo, ParseError
from .cpr_parser import parse_cpr
from .flp_parser import parse_flp
from .rpp_parser import parse_rpp

EXTENSIONS: dict[str, str] = {
    ".als": "als",
    ".cpr": "cpr",
    ".rpp": "rpp",
    ".flp": "flp",
}

_PARSERS = {
    "als": parse_als,
    "cpr": parse_cpr,
    "rpp": parse_rpp,
    "flp": parse_flp,
}


def detect_format(path: str, data: bytes | None = None) -> str | None:
    """Return format key by extension, then by magic bytes."""
    ext = PurePosixPath(path).suffix.lower()
    if ext in EXTENSIONS:
        return EXTENSIONS[ext]
    if data is not None:
        if data[:2] == b"\x1f\x8b" or b"<LiveSet" in data[:4096]:
            return "als"
        if b"<CubaseProject" in data[:8192]:
            return "cpr"
        if b"<REAPER_PROJECT" in data[:2048]:
            return "rpp"
        if data[:1] in (b"\xf4", b"\xf5"):
            return "flp"
    return None


def get_daw_info(path: str, data: bytes) -> DAWInfo | None:
    fmt = detect_format(path, data)
    if fmt is None:
        return None
    try:
        return _PARSERS[fmt](data)
    except (ParseError, Exception):  # noqa: BLE001 - never fail on analysis
        return None


def is_daw_path(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in EXTENSIONS
