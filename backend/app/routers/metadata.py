"""Metadata validation endpoints using MusicBrainz API.

Provides ISRC validation and track metadata lookup for music projects.
"""
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..services.musicbrainz import (
    ISRCResult,
    TrackMetadata,
    enrich_from_isrc,
    search_track,
    validate_isrc,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


class ISRCValidationOut(BaseModel):
    isrc: str
    found: bool
    title: str = ""
    artist: str = ""
    album: str = ""
    duration_ms: int = 0
    release_date: str = ""
    country: str = ""
    label: str = ""
    error: str = ""


class TrackSearchResultOut(BaseModel):
    title: str
    artist: str
    duration_ms: int


class ISRCEnrichOut(BaseModel):
    title: str
    artist: str
    album: str
    release_date: str
    isrc: str
    duration_ms: int


@router.get("/isrc/{isrc}", response_model=ISRCValidationOut)
def validate_isrc_endpoint(isrc: str):
    """Validate an ISRC code and return metadata if found.

    ISRC (International Standard Recording Code) uniquely identifies
    a sound recording worldwide. Format: CC-XXX-YY-NNNNN
    (country, registrant, year, designation)

    Example: USRC12345678
    """
    result = validate_isrc(isrc)
    return ISRCValidationOut(
        isrc=result.isrc,
        found=result.found,
        title=result.title,
        artist=result.artist,
        album=result.album,
        duration_ms=result.duration_ms,
        release_date=result.release_date,
        country=result.country,
        label=result.label,
        error=result.error,
    )


@router.get("/isrc/{isrc}/enrich", response_model=ISRCEnrichOut | None)
def enrich_from_isrc_endpoint(isrc: str):
    """Look up ISRC and return enriched track metadata.

    Returns None if ISRC not found.
    """
    meta = enrich_from_isrc(isrc)
    if meta is None:
        return None
    return ISRCEnrichOut(
        title=meta.title,
        artist=meta.artist,
        album=meta.album,
        release_date=meta.release_date,
        isrc=meta.isrc,
        duration_ms=meta.duration_ms,
    )


@router.get("/search", response_model=list[TrackSearchResultOut])
def search_tracks(
    title: str = Query(..., min_length=1, max_length=200),
    artist: str = Query("", max_length=200),
    limit: int = Query(5, ge=1, le=20),
):
    """Search for a track on MusicBrainz.

    Returns matching recordings with title, artist, and duration.
    """
    results = search_track(title, artist, limit)
    return [
        TrackSearchResultOut(
            title=r.title,
            artist=r.artist,
            duration_ms=r.duration_ms,
        )
        for r in results
    ]
