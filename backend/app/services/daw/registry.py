"""DAW format detection and info extraction."""


def detect_format(path: str, data: bytes) -> str:
    """Detect the DAW format from file path and content."""
    lower = path.lower()
    if lower.endswith(".als"):
        return "ableton"
    elif lower.endswith(".cpr"):
        return "cubase"
    elif lower.endswith(".rpp"):
        return "reaper"
    elif lower.endswith(".flp"):
        return "flstudio"
    return "unknown"


def get_daw_info(path: str, data: bytes) -> dict | None:
    """Extract structured info from a DAW project file."""
    fmt = detect_format(path, data)
    if fmt == "ableton":
        return _parse_ableton(data)
    elif fmt == "reaper":
        return _parse_reaper(data)
    elif fmt == "cubase":
        return _parse_cubase(data)
    elif fmt == "flstudio":
        return _parse_flstudio(data)
    return None


def _parse_ableton(data: bytes) -> dict:
    """Parse Ableton Live Set (.als) — gzip-compressed XML."""
    from .als_parser import parse_als

    try:
        info = parse_als(data)
        return {
            "format": "ableton",
            "bpm": info.bpm,
            "time_signature": info.time_signature,
            "track_count": info.extra.get("track_count", len(info.tracks)),
            "tracks": [t.name for t in info.tracks[:50]],
            "plugin_count": len(info.plugins),
            "plugins": info.plugins[:50],  # Limit to first 50 plugins
        }
    except Exception:
        return {"format": "ableton", "error": "parse_failed"}


def _parse_reaper(data: bytes) -> dict:
    """Parse REAPER project (.rpp) — text-based format."""
    try:
        text = data.decode("utf-8", errors="replace")
        lines = text.split("\n")

        bpm = None
        tracks = []
        plugins = []

        for line in lines:
            if line.startswith("TEMPO "):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        bpm = float(parts[1])
                    except ValueError:
                        pass
            elif line.startswith("TRACK "):
                tracks.append(line)
            elif "VST" in line or "AU" in line or "JSFX" in line:
                plugins.append(line.strip()[:100])

        return {
            "format": "reaper",
            "bpm": bpm,
            "track_count": len(tracks),
            "tracks": [t.split('"')[1] if '"' in t else t for t in tracks[:50]],
            "plugin_count": len(plugins),
            "plugins": plugins[:30],
        }
    except Exception:
        return {"format": "reaper", "error": "parse_failed"}


def _parse_cubase(data: bytes) -> dict:
    """Parse Cubase project (.cpr) — binary/XML format."""
    return {"format": "cubase", "track_count": 0, "plugins": [], "note": "partial parser"}


def _parse_flstudio(data: bytes) -> dict:
    """Parse FL Studio project (.flp) — binary format."""
    return {"format": "flstudio", "track_count": 0, "plugins": [], "note": "partial parser"}
