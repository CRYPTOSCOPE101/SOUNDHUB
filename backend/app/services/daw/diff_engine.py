"""Smart diff engine for DAW project comparison.

Compares two DAW projects at the structural level: tempo, tracks,
plugins, samples. A revision is a story — never "binary file changed".
"""
import json


def summary_diff(info_a: dict | None, info_b: dict | None) -> dict:
    """Compute a structured summary diff between two DAW project infos."""
    if not info_a and not info_b:
        return {}
    if not info_a:
        return {"added": _full_summary(info_b)}
    if not info_b:
        return {"removed": _full_summary(info_a)}

    summary = {}

    # BPM diff
    bpm_a = info_a.get("bpm")
    bpm_b = info_b.get("bpm")
    if bpm_a != bpm_b:
        summary["bpm"] = {"before": bpm_a, "after": bpm_b}

    # Time signature diff
    ts_a = info_a.get("time_signature")
    ts_b = info_b.get("time_signature")
    if ts_a != ts_b:
        summary["time_signature"] = {"before": ts_a, "after": ts_b}

    # Track diff
    tracks_a = set(info_a.get("tracks", []))
    tracks_b = set(info_b.get("tracks", []))
    added_tracks = tracks_b - tracks_a
    removed_tracks = tracks_a - tracks_b
    if added_tracks or removed_tracks:
        summary["tracks"] = {
            "added": sorted(added_tracks)[:20],
            "removed": sorted(removed_tracks)[:20],
            "count_before": info_a.get("track_count", 0),
            "count_after": info_b.get("track_count", 0),
        }

    # Plugin diff
    plugins_a = set(info_a.get("plugins", []))
    plugins_b = set(info_b.get("plugins", []))
    added_plugins = plugins_b - plugins_a
    removed_plugins = plugins_a - plugins_b
    if added_plugins or removed_plugins:
        summary["plugins"] = {
            "added": sorted(added_plugins)[:20],
            "removed": sorted(removed_plugins)[:20],
            "count_before": info_a.get("plugin_count", 0),
            "count_after": info_b.get("plugin_count", 0),
        }

    return summary


def _full_summary(info: dict) -> dict:
    return {
        "format": info.get("format", "unknown"),
        "bpm": info.get("bpm"),
        "track_count": info.get("track_count", 0),
        "plugin_count": info.get("plugin_count", 0),
    }


def normalize_content(path: str, data: bytes) -> str:
    """Normalize DAW file content for text-based diff."""
    lower = path.lower()
    if lower.endswith(".rpp"):
        return data.decode("utf-8", errors="replace")
    elif lower.endswith(".als"):
        try:
            import gzip
            return gzip.decompress(data).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return ""


def unified_diff(text_a: str, text_b: str, max_lines: int = 500) -> tuple[str, bool]:
    """Generate a unified diff between two normalized texts."""
    if not text_a and not text_b:
        return "", False
    if not text_a:
        return f"+ (new file, {len(text_b.splitlines())} lines)", False
    if not text_b:
        return f"- (file removed, {len(text_a.splitlines())} lines)", False

    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    # Simple line-level diff
    import difflib
    diff = list(difflib.unified_diff(lines_a, lines_b, lineterm="", n=2))
    truncated = len(diff) > max_lines
    result = "\n".join(diff[:max_lines])
    return result, truncated
