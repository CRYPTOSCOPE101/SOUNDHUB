"""Asset endpoints — catalog, recommendations, delivery.

Serves the SoundHub marketplace to the in-DAW (M4L) device and the web app:

- `GET /api/assets` — catalog enriched with DAW-verified metadata.
- `GET /api/assets/recommend` — context-aware ranking (BPM / key / genre /
  devices), the interface the M4L device calls for suggestions.
- `GET /api/assets/{listing_id}/download?token=...` — delivers the purchased
  asset bytes to the device using a short-lived signed token.
- `GET /api/assets/{listing_id}/download64?token=...` — text-safe (base64
  JSON) variant for the M4L device, which cannot write raw binary from
  `httprequest` and cannot use `shell` inside Live.

The catalog metadata + payloads live in `services/catalog.py` (seeded demo);
production reads listings from the SoundHubMarket contract and metadata from
the backend DB / IPFS.
"""

import base64
import re

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from ..config import SECRET_KEY
from ..services import catalog, licenses

router = APIRouter(prefix="/api/assets", tags=["assets"])

_MIME = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".aiff": "audio/aiff",
    ".mid": "audio/midi",
    ".midi": "audio/midi",
    ".adg": "application/octet-stream",
    ".als": "application/octet-stream",
}


def _mime_for(filename: str) -> str:
    dot = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MIME.get(f".{dot}", "application/octet-stream")


@router.get("")
def list_catalog(
    limit: int = Query(default=50, ge=1, le=200),
    q: str | None = Query(default=None, max_length=200),
    genre: str | None = Query(default=None, max_length=256),
    bpm_min: float | None = Query(default=None, ge=20, le=300),
    bpm_max: float | None = Query(default=None, ge=20, le=300),
    key: str | None = Query(default=None, max_length=64),
    license: str | None = Query(default=None, max_length=128),
    format: str | None = Query(default=None, max_length=128),
    plugin: str | None = Query(default=None, max_length=128),
) -> list[dict]:
    """Filterable catalog for the web UI (and the M4L device).

    `license` / `format` accept comma-separated lists; bpm_min/bpm_max match
    assets whose BPM range overlaps; key/genre/plugin/q narrow further.
    """
    return catalog.search_catalog(
        q=q,
        genre=genre,
        bpm_min=bpm_min,
        bpm_max=bpm_max,
        key=key,
        license=license,
        format=format,
        plugin=plugin,
        limit=limit,
    )


@router.get("/recommend")
def recommend_assets(
    bpm: float | None = Query(default=None, ge=20, le=300),
    key: str | None = Query(default=None, max_length=32),
    genre: str | None = Query(default=None, max_length=128),
    devices: str | None = Query(default=None, max_length=512),
    license: str | None = Query(default=None, max_length=64),
    format: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[dict]:
    """Rank catalog assets for the producer's current context.

    `license` (Personal/Commercial/Sync/Exclusive) and `format`
    (als/wav/midi/…) act as hard filters; bpm/key/genre/devices score.
    """
    return catalog.recommend(
        bpm=bpm,
        key=key,
        genre=genre,
        devices=devices,
        license=license,
        format=format,
        limit=limit,
    )


@router.post("/{listing_id}/receipt")
def issue_license_receipt(
    listing_id: int,
    buyer: str = Query(min_length=20, max_length=64),
    seller: str = Query(default="", max_length=64),
) -> dict:
    """Issue a signed license receipt for a purchase.

    States what the buyer may do with the audio (license scope) alongside the
    order facts: asset hash, seller, buyer, price, date, receipt version.

    Prototype note: buyer/seller are reported by the client. Production must
    verify the purchase on-chain (buyer == contract.buyer, escrowed > 0)
    before issuing — same gate as the download token.
    """
    asset = catalog.find_asset(listing_id)
    if asset is None or asset.payload is None:
        raise HTTPException(404, "Asset not found")
    return licenses.make_license_receipt(
        SECRET_KEY,
        listing_id=listing_id,
        asset_name=asset.name,
        license=asset.license,
        seller=seller or "soundhub://demo-seller",
        buyer=buyer,
        price_snd=asset.price_snd,
        asset_hash=asset.sha256,
    )


@router.get("/{listing_id}/preview")
def preview_asset(listing_id: int, request: Request) -> Response:
    """Stream the asset payload inline for the browser preview player.

    Public (no token) — the whole point of a preview is listening before
    buying. Supports single-range requests so the <audio> element can seek.
    """
    asset = catalog.find_asset(listing_id)
    if asset is None or asset.payload is None:
        raise HTTPException(404, "Asset not found or no preview available")
    data = asset.payload
    mime = _mime_for(asset.filename)
    inline = f'inline; filename="{asset.filename}"'

    range_header = request.headers.get("range")
    if range_header:
        m = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if m:
            start_s, end_s = m.groups()
            try:
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else len(data) - 1
                if start < 0 or end < start or start >= len(data):
                    raise ValueError
                end = min(end, len(data) - 1)
            except ValueError:
                return Response(
                    status_code=416,
                    headers={"Content-Range": f"bytes */{len(data)}"},
                )
            return Response(
                content=data[start : end + 1],
                status_code=206,
                media_type=mime,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{len(data)}",
                    "Accept-Ranges": "bytes",
                    "Content-Disposition": inline,
                },
            )

    return Response(
        content=data,
        media_type=mime,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": inline,
        },
    )


@router.get("/{listing_id}/token")
def issue_download_token(listing_id: int) -> dict:
    """Issue a short-lived download token for the M4L device (prototype).

    Production gate: verify the caller purchased `listing_id` (buyer ==
    wallet, escrowed > 0) before issuing. The prototype issues tokens for
    demo payloads so the in-DAW flow can be tested end-to-end.
    """
    asset = catalog.find_asset(listing_id)
    if asset is None or asset.payload is None:
        raise HTTPException(404, "Asset not found or no payload available")
    token = catalog.make_download_token(SECRET_KEY, listing_id)
    return {
        "listing_id": listing_id,
        "token": token,
        "expires_in": 300,
        "name": asset.name,
        "filename": asset.filename,
        "format": asset.format,
        "license": asset.license,
        "size": len(asset.payload),
    }


@router.get("/{listing_id}/download64")
def download_asset_base64(listing_id: int, token: str = Query(min_length=20, max_length=256)) -> dict:
    """Text-safe asset delivery for the M4L device (JSON + base64 payload).

    The Max for Live `httprequest` object can mangle raw binary responses,
    and the `shell` object is blocked in Live — so the device fetches the
    payload as base64 JSON and writes the bytes itself (Max `file` object).
    """
    authorized = catalog.verify_download_token(SECRET_KEY, token)
    if authorized != listing_id:
        raise HTTPException(401, "Invalid or expired download token")
    asset = catalog.find_asset(listing_id)
    if asset is None or asset.payload is None:
        raise HTTPException(404, "Asset not found or no payload available")
    return {
        "listing_id": listing_id,
        "filename": asset.filename,
        "name": asset.name,
        "format": asset.format,
        "license": asset.license,
        "size": len(asset.payload),
        "data": base64.b64encode(asset.payload).decode("ascii"),
    }


@router.get("/{listing_id}/download")
def download_asset(
    listing_id: int,
    token: str = Query(min_length=20, max_length=256),
) -> Response:
    """Deliver the asset payload to a buyer/device (short-lived signed token).

    In production the token is issued only after an on-chain purchase check
    (buyer == caller, escrowed > 0). The prototype keeps the token
    deterministic so the M4L device can fetch assets end-to-end.
    """
    authorized = catalog.verify_download_token(SECRET_KEY, token)
    if authorized != listing_id:
        raise HTTPException(401, "Invalid or expired download token")
    asset = catalog.find_asset(listing_id)
    if asset is None or asset.payload is None:
        raise HTTPException(404, "Asset not found or no payload available")
    return Response(
        content=asset.payload,
        media_type=_mime_for(asset.filename),
        headers={
            "Content-Disposition": f'attachment; filename="{asset.filename}"',
            "X-Asset-Name": asset.name.encode("ascii", "replace").decode(),
            "X-License": asset.license,
        },
    )
