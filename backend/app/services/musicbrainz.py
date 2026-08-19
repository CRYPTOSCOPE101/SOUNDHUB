"""MusicBrainz API integration for ISRC and track metadata validation.

MusicBrainz is a free, open music encyclopedia. We use it to:
  - Validate ISRC codes (International Standard Recording Code)
  - Look up track metadata (title, artist, album, duration)
  - Enrich project files with accurate metadata
  - Detect duplicates (same ISRC already in the database)

API docs: https://musicbrainz.org/doc/MusicBrainz_API
Rate limit: 1 request per second (be nice!)
"""
from __future__ import annotations

import time
import urllib.request
import urllib.parse
import json
from dataclasses import dataclass, field


BASE_URL = "https://musicbrainz.org/ws/2"
USER_AGENT = "SoundHub/0.1.0 ( https://github.com/soundXlab/SoundHub )"
RATE_LIMIT_MS = 1100  # 1.1s between requests

_last_request_time: float = 0.0


@dataclass
class ISRCResult:
    """Result of an ISRC lookup."""
    isrc: str
    found: bool = False
    title: str = ""
    artist: str = ""
    album: str = ""
    duration_ms: int = 0
    release_date: str = ""
    country: str = ""
    label: str = ""
    error: str = ""


@dataclass
class TrackMetadata:
    """Enriched track metadata from MusicBrainz."""
    title: str = ""
    artist: str = ""
    album: str = ""
    release_date: str = ""
    isrc: str = ""
    duration_ms: int = 0
    genre: str = ""
    tags: list[str] = field(default_factory=list)


def _rate_limit() -> None:
    """Enforce MusicBrainz rate limit (1 req/sec)."""
    global _last_request_time
    now = time.time()
    elapsed = (now - _last_request_time) * 1000
    if elapsed < RATE_LIMIT_MS:
        time.sleep((RATE_LIMIT_MS - elapsed) / 1000)
    _last_request_time = time.time()


def _get(path: str, params: dict | None = None) -> dict | None:
    """Make a GET request to MusicBrainz API."""
    _rate_limit()

    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        return None
    except Exception:
        return None


def validate_isrc(isrc: str) -> ISRCResult:
    """Look up an ISRC code on MusicBrainz.

    Args:
        isrc: 12-character ISRC code (e.g., "USRC12345678")

    Returns:
        ISRCResult with metadata if found, or error details.
    """
    # Normalize ISRC
    clean = isrc.upper().replace("-", "").replace(" ", "")
    if len(clean) != 12:
        return ISRCResult(isrc=isrc, error=f"Invalid ISRC format: expected 12 chars, got {len(clean)}")

    data = _get(f"/isrc/{clean}", {"fmt": "json"})
    if data is None:
        return ISRCResult(isrc=clean, found=False)

    recordings = data.get("recordings", [])
    if not recordings:
        return ISRCResult(isrc=clean, found=False)

    # Take the first recording
    rec = recordings[0]
    title = rec.get("title", "")
    artist = ""
    artists = rec.get("artist-credit", [])
    if artists:
        artist = artists[0].get("name", "")

    album = ""
    duration_ms = int(rec.get("length", 0) or 0)

    # Try to get release info
    releases = rec.get("releases", [])
    if releases:
        rel = releases[0]
        album = rel.get("title", "")
        release_date = rel.get("date", "")
        country = rel.get("country", "")
        labels = rel.get("label-info", [])
        label = labels[0].get("label", {}).get("name", "") if labels else ""
    else:
        release_date = ""
        country = ""
        label = ""

    return ISRCResult(
        isrc=clean,
        found=True,
        title=title,
        artist=artist,
        album=album,
        duration_ms=duration_ms,
        release_date=release_date,
        country=country,
        label=label,
    )


def search_track(title: str, artist: str = "", limit: int = 5) -> list[TrackMetadata]:
    """Search for a track on MusicBrainz.

    Args:
        title: Track title
        artist: Optional artist name
        limit: Max results (default 5)

    Returns:
        List of TrackMetadata matches.
    """
    query_parts = [f'recording:"{title}"']
    if artist:
        query_parts.append(f'artist:"{artist}"')

    params = {
        "query": " AND ".join(query_parts),
        "limit": str(limit),
        "fmt": "json",
    }

    data = _get("/recording", params)
    if data is None:
        return []

    results = []
    for rec in data.get("recordings", []):
        artist = ""
        artists = rec.get("artist-credit", [])
        if artists:
            artist = artists[0].get("name", "")

        results.append(TrackMetadata(
            title=rec.get("title", ""),
            artist=artist,
            duration_ms=int(rec.get("length", 0) or 0),
        ))

    return results


def enrich_from_isrc(isrc: str) -> TrackMetadata | None:
    """Look up an ISRC and return enriched metadata.

    Convenience function: validates ISRC, returns TrackMetadata if found.
    """
    result = validate_isrc(isrc)
    if not result.found:
        return None

    return TrackMetadata(
        title=result.title,
        artist=result.artist,
        album=result.album,
        release_date=result.release_date,
        isrc=result.isrc,
        duration_ms=result.duration_ms,
    )
