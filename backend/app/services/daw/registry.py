"""DAW format detection and info extraction."""
import gzip
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


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
    try:
        xml_data = gzip.decompress(data)
        root = ET.fromstring(xml_data)
        ns = {"a": "http://www.ableton.com/ns/3"}

        bpm = None
        time_sig = None
        tracks = []
        plugins = []

        # Tempo
        tempo_elem = root.find(".//a:Tempo", ns)
        if tempo_elem is not None:
            bpm = float(tempo_elem.get("Value", "120"))

        # Time signature
        time_sig_elem = root.find(".//a:TimeSignature", ns)
        if time_sig_elem is not None:
            num = time_sig_elem.get("TimeSignatureNumerator", "4")
            den = time_sig_elem.get("TimeSignatureDenominator", "4")
            time_sig = f"{num}/{den}"

        # Tracks
        for track in root.findall(".//a:Track", ns):
            name = track.get("Name", "Unnamed")
            tracks.append(name)

        return {
            "format": "ableton",
            "bpm": bpm,
            "time_signature": time_sig,
            "track_count": len(tracks),
            "tracks": tracks[:50],
            "plugin_count": len(plugins),
        }
    except (OSError, EOFError, ET.ParseError, ValueError) as exc:
        logger.warning("ableton parse failed (%d bytes): %s", len(data), exc)
        return {"format": "ableton", "error": "parse_failed", "error_detail": str(exc)[:200]}


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
                        logger.debug("reaper: unparseable TEMPO value %r", parts[1])
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
    except (UnicodeDecodeError, ValueError, IndexError) as exc:
        logger.warning("reaper parse failed (%d bytes): %s", len(data), exc)
        return {"format": "reaper", "error": "parse_failed", "error_detail": str(exc)[:200]}


def _parse_cubase(data: bytes) -> dict:
    """Parse Cubase project (.cpr) — binary/XML format."""
    return {"format": "cubase", "track_count": 0, "plugins": [], "note": "partial parser"}


def _parse_flstudio(data: bytes) -> dict:
    """Parse FL Studio project (.flp) — binary format."""
    return {"format": "flstudio", "track_count": 0, "plugins": [], "note": "partial parser"}
