"""Asset catalog + recommendation engine.

Bridges the on-chain marketplace (SoundHubMarket listings) and the studio
layer (DAW engine metadata). Each catalog entry describes a listed asset in
DAW terms — BPM range, genre, plugins, format — so recommendations can match
the *project context* a producer is in (BPM, key, genre, devices) to the
assets most likely to fit, and buyers can see verified contents before
purchasing.

The catalog below is seeded with demo assets; production reads listing
metadata from the on-chain SoundHubMarket + a metadata store (IPFS or the
backend DB).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

GENRE_ALIASES = {
    "house": {"house", "deep house", "melodic house", "tech house"},
    "techno": {"techno", "melodic techno", "hard techno"},
    "dubstep": {"dubstep", "riddim", "brostep"},
    "trap": {"trap", "drill", "phonk"},
    "dnb": {"drum and bass", "dnb", "jungle"},
    "cinematic": {"cinematic", "film", "trailer", "orchestral"},
    "ambient": {"ambient", "drone", "textural"},
}


@dataclass
class CatalogAsset:
    """A listed sound asset, enriched with DAW-verifiable metadata."""

    listing_id: int  # SoundHubMarket listing id (0 = not yet listed on-chain)
    name: str
    price_snd: str  # display price in SND
    license: str  # Personal | Commercial | Sync | Exclusive
    uri: str  # soundhub:// pointer to the file
    bpm: tuple[int, int] | None = None  # (min, max) range
    key: str | None = None
    genres: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    format: str | None = None  # als | cpr | rpp | flp | wav | midi | adg
    contents: str = ""  # human-readable verification summary (DAW engine)
    description: str = ""
    verified: bool = True  # contents were parsed/verified by the DAW engine
    # demo payload served by the /assets/{id}/download endpoint
    payload: bytes | None = None
    filename: str = ""

    @property
    def sha256(self) -> str:
        """Content hash of the payload — the asset fingerprint on the receipt."""
        if self.payload is None:
            return ""
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict:
        duration, waveform = _wav_info(self.payload) if self.payload else (0.0, [])
        return {
            "listing_id": self.listing_id,
            "name": self.name,
            "price_snd": self.price_snd,
            "license": self.license,
            "uri": self.uri,
            "bpm": list(self.bpm) if self.bpm else None,
            "key": self.key,
            "genres": self.genres,
            "plugins": self.plugins,
            "format": self.format,
            "contents": self.contents,
            "description": self.description,
            "verified": self.verified,
            "duration_seconds": duration,
            "waveform": waveform,
            "sha256": self.sha256 or None,
        }


def _wav_info(payload: bytes) -> tuple[float, list[int]]:
    """Parse a small 16-bit PCM WAV: (duration_seconds, waveform peaks).

    Returns ~120 peak values (0–255) downsampled from the audio, enough for a
    lightweight preview waveform in the UI and the M4L device.
    """
    if not payload.startswith(b"RIFF") or len(payload) < 44:
        return 0.0, []
    rate = 22050
    channels = 1
    data = b""
    pos = 12
    while pos + 8 <= len(payload):
        cid = payload[pos : pos + 4]
        size = int.from_bytes(payload[pos + 4 : pos + 8], "little")
        body = payload[pos + 8 : pos + 8 + size]
        if cid == b"fmt " and len(body) >= 8:
            channels = int.from_bytes(body[2:4], "little") or 1
            rate = int.from_bytes(body[4:8], "little") or rate
        elif cid == b"data":
            data = body
        pos += 8 + size + (size & 1)  # chunks are word-aligned
    if not data:
        return 0.0, []
    n_samples = len(data) // 2
    if n_samples == 0:
        return 0.0, []
    duration = round(n_samples / rate, 2)
    buckets = 120
    step = max(1, n_samples // buckets)
    peaks: list[int] = []
    for i in range(0, n_samples, step):
        chunk = data[i * 2 : (i + step) * 2]
        vals = [
            int.from_bytes(chunk[j : j + 2], "little", signed=True)
            for j in range(0, len(chunk) - 1, 2)
        ]
        if not vals:
            continue
        peak = max(abs(v) for v in vals)
        peaks.append(min(255, int(peak * 255 / 32768)))
    return duration, peaks


def _wav(name: str, seconds: float = 0.5, freq: int = 220) -> bytes:
    """Tiny deterministic WAV for demo asset payloads."""
    import struct

    rate = 22050
    n = int(rate * seconds)
    data = b"".join(
        struct.pack("<h", int(3000 * (0.5 + 0.5 * __import__("math").sin(2 * 3.14159 * freq * i / rate))))
        for i in range(n)
    )
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt "
    hdr += struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    return hdr + b"data" + struct.pack("<I", len(data)) + data


# The seeded demo listing (#1, live on Base Sepolia) + a few catalog entries
# to make recommendations meaningful before more listings exist on-chain.
CATALOG: list[CatalogAsset] = [
    CatalogAsset(
        listing_id=1,
        name="Neon Dreams — Serum Preset Pack",
        price_snd="50",
        license="Commercial",
        uri="soundhub://assets/neon-dreams-serum-pack",
        bpm=(124, 132),
        key="A minor",
        genres=["techno", "melodic techno", "house"],
        plugins=["Serum", "Vital"],
        format="als",
        contents="24 Serum presets (verified) · project 128 BPM · tracks: Pad, Bass, Arp, Drums",
        description="Synthwave/techno serum presets with a ready 128 BPM Live project.",
        payload=_wav("neon_dreams_demo.wav", 0.8, 440),
        filename="neon-dreams-demo.wav",
    ),
    CatalogAsset(
        listing_id=0,  # catalog-only (recommendation demo; not on-chain yet)
        name="Dark Bass Pack (Techno)",
        price_snd="35",
        license="Commercial",
        uri="soundhub://assets/dark-bass-pack",
        bpm=(126, 138),
        key="D minor",
        genres=["techno", "hard techno"],
        plugins=["Serum", "Massive"],
        format="wav",
        contents="12 bass one-shots + 6 loops, 126–138 BPM, key D minor",
        description="Sub-heavy basses for club techno.",
        payload=_wav("dark_bass_demo.wav", 0.6, 110),
        filename="dark-bass-demo.wav",
    ),
    CatalogAsset(
        listing_id=0,
        name="Cinematic Impacts Vol.1",
        price_snd="25",
        license="Sync",
        uri="soundhub://assets/cinematic-impacts",
        bpm=None,
        key=None,
        genres=["cinematic", "film", "trailer"],
        plugins=[],
        format="wav",
        contents="18 impacts + risers, trailer-ready, 24-bit WAV",
        description="Percussive hits for trailers, game audio, film.",
        payload=_wav("impact_demo.wav", 0.3, 60),
        filename="impact-demo.wav",
    ),
    CatalogAsset(
        listing_id=0,
        name="Melodic House Chords Vol.1",
        price_snd="40",
        license="Commercial",
        uri="soundhub://assets/melodic-house-chords",
        bpm=(118, 124),
        key="A minor",
        genres=["house", "melodic house", "deep house"],
        plugins=["Serum", "Pigments"],
        format="midi",
        contents="32 MIDI chord progressions, 118–124 BPM, A minor family",
        description="Progressions for melodic house and deep house.",
        payload=_wav("chords_demo.wav", 1.0, 330),
        filename="chords-demo.wav",
    ),
]


def get_catalog() -> list[dict]:
    return [a.to_dict() for a in CATALOG]


def search_catalog(
    q: str | None = None,
    genre: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    key: str | None = None,
    license: str | None = None,
    format: str | None = None,
    plugin: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Filter the catalog for the web UI (server-side preview filtering).

    `license` / `format` accept comma-separated lists; bpm_min/bpm_max match
    assets whose BPM range overlaps; key/genre/plugin/q are exact-ish matches.
    """
    assets = list(CATALOG)
    allowed_licenses = {l.strip().lower() for l in (license or "").split(",") if l.strip()}
    allowed_formats = {f.strip().lower() for f in (format or "").split(",") if f.strip()}

    def passes(a: CatalogAsset) -> bool:
        if allowed_licenses and a.license.lower() not in allowed_licenses:
            return False
        if allowed_formats and (a.format or "").lower() not in allowed_formats:
            return False
        if a.bpm:
            lo, hi = a.bpm
            if bpm_min is not None and hi < bpm_min:
                return False
            if bpm_max is not None and lo > bpm_max:
                return False
        elif bpm_min is not None or bpm_max is not None:
            return False
        if key and not (a.key and _norm_key(a.key) == _norm_key(key)):
            return False
        if genre and _genre_hits(a.genres, [g.strip() for g in genre.split(",") if g.strip()]) <= 0:
            return False
        if plugin:
            pl = plugin.strip().lower()
            if not any(pl in p.lower() for p in a.plugins):
                return False
        if q:
            ql = q.strip().lower()
            haystack = " ".join(
                [a.name, a.description, a.contents, a.key or "", " ".join(a.genres)]
            ).lower()
            if ql not in haystack:
                return False
        return True

    return [a.to_dict() for a in assets if passes(a)][:limit]


def find_asset(listing_id: int) -> CatalogAsset | None:
    for a in CATALOG:
        if a.listing_id == listing_id:
            return a
    return None


# ---------------------------------------------------------------------------
# Recommendation scoring
# ---------------------------------------------------------------------------


def _genre_hits(asset_genres: list[str], context_genres: list[str]) -> int:
    hits = 0
    for g in context_genres:
        g = g.strip().lower()
        for ag in asset_genres:
            alias = GENRE_ALIASES.get(ag.lower(), {ag.lower()})
            if g in alias:
                hits += 1
    return hits


def _bpm_score(asset: CatalogAsset, bpm: float | None) -> float:
    if bpm is None or asset.bpm is None:
        return 0.0
    lo, hi = asset.bpm
    if lo <= bpm <= hi:
        return 1.0
    # distance penalty: 0.5 at one BPM outside the range, → 0 at 10+
    dist = min(abs(bpm - lo), abs(bpm - hi))
    return max(0.0, 1.0 - dist / 10.0)


def _key_match(asset: CatalogAsset, key: str | None) -> float:
    if not key or not asset.key:
        return 0.0
    return 1.0 if _norm_key(asset.key) == _norm_key(key) else 0.0


def _norm_key(k: str) -> str:
    return (
        k.strip().lower()
        .replace("-", " ")
        .replace(" minor", "m")
        .replace(" major", "")
        .replace("#", "s")
    )


def recommend(
    bpm: float | None = None,
    key: str | None = None,
    genre: str | None = None,
    devices: str | None = None,
    license: str | None = None,
    format: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Rank catalog assets against producer context.

    Scoring: genre match (3) + BPM proximity (2) + key (1) + device overlap (1).
    The `devices` parameter is where the DAW engine feeds parsed project
    devices/plugins (from the M4L device or a parsed .als file).

    Hard filters (not scored): `license` (Personal/Commercial/Sync/Exclusive,
    comma-separated allowed) and `format` (als/cpr/rpp/flp/wav/midi/adg).
    """
    context_genres = [g.strip() for g in (genre or "").split(",") if g.strip()]
    context_devices = [d.strip().lower() for d in (devices or "").split(",") if d.strip()]
    allowed_licenses = {
        l.strip().lower() for l in (license or "").split(",") if l.strip()
    }
    allowed_formats = {
        f.strip().lower() for f in (format or "").split(",") if f.strip()
    }

    scored: list[tuple[float, CatalogAsset, list[str]]] = []
    for asset in CATALOG:
        if allowed_licenses and asset.license.lower() not in allowed_licenses:
            continue
        if allowed_formats and (asset.format or "").lower() not in allowed_formats:
            continue
        score = 0.0
        reasons: list[str] = []
        gh = _genre_hits(asset.genres, context_genres)
        score = 0.0
        reasons: list[str] = []
        gh = _genre_hits(asset.genres, context_genres)
        if gh:
            score += 3.0 * min(gh, 2)
            reasons.append("genre match")
        bs = _bpm_score(asset, bpm)
        if bs > 0:
            score += 2.0 * bs
            reasons.append("BPM fit")
        if _key_match(asset, key):
            score += 1.0
            reasons.append("key match")
        dev_hits = sum(1 for d in context_devices if any(d in p.lower() for p in asset.plugins))
        if dev_hits:
            score += 1.0 * min(dev_hits, 2)
            reasons.append("device/plugin overlap")
        # Hard filters (license/format) make an asset eligible even without
        # context match; otherwise only ranked (score > 0) assets are shown.
        if allowed_licenses or allowed_formats or score > 0:
            scored.append((score, asset, reasons))

    scored.sort(key=lambda t: -t[0])
    out = []
    for score, asset, reasons in scored[:limit]:
        d = asset.to_dict()
        d["match_score"] = round(score, 2)
        d["match_reasons"] = reasons
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Signed download URLs (short-lived, for the M4L device / buyers)
# ---------------------------------------------------------------------------


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_download_token(secret: str, listing_id: int, expires_in: int = 300) -> str:
    """Short-lived token authorizing a download of `listing_id`'s payload."""
    exp = int(time.time()) + expires_in
    payload = f"{listing_id}:{exp}"
    return f"{payload}:{_sign(secret, payload)}"


def verify_download_token(secret: str, token: str) -> int | None:
    """Return listing_id if the token is valid and unexpired, else None."""
    try:
        payload, sig = token.rsplit(":", 1)
        listing_id_s, exp_s = payload.split(":")
        listing_id, exp = int(listing_id_s), int(exp_s)
    except (ValueError, AttributeError):
        return None
    if not hmac.compare_digest(_sign(secret, payload), sig):
        return None
    if time.time() > exp:
        return None
    return listing_id
