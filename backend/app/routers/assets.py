"""Asset endpoints — catalog, recommendations, delivery.

Serves the SoundHub marketplace to the in-DAW (M4L) device and the web app:

- `GET /api/assets` — catalog enriched with DAW-verified metadata.
- `GET /api/assets/recommend` — context-aware ranking (BPM / key / genre /
  devices), the interface the M4L device calls for suggestions.
- `GET /api/assets/{listing_id}/download?token=...` — delivers the purchased
  asset bytes to the device using a short-lived signed token.

The catalog metadata + payloads live in `services/catalog.py` (seeded demo);
production reads listings from the SoundHubMarket contract and metadata from
the backend DB / IPFS.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..config import SECRET_KEY
from ..services import catalog

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
def list_catalog(limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    return catalog.get_catalog()[:limit]


@router.get("/recommend")
def recommend_assets(
    bpm: float | None = Query(default=None, ge=20, le=300),
    key: str | None = Query(default=None, max_length=32),
    genre: str | None = Query(default=None, max_length=128),
    devices: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=5, ge=1, le=20),
) -> list[dict]:
    """Rank catalog assets for the producer's current context."""
    return catalog.recommend(
        bpm=bpm,
        key=key,
        genre=genre,
        devices=devices,
        limit=limit,
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
    return {"listing_id": listing_id, "token": token, "expires_in": 300}


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
