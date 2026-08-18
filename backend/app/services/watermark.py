"""Audible watermarking for unapproved audio previews.

An unapproved version served to guests carries an audible watermark — a
leaked preview is traceable and never "the final file". Approved
versions are clean.
"""
import hashlib

from sqlalchemy.orm import Session

from ..models import ReviewVersion


def watermarked_blob(db: Session, version: ReviewVersion) -> bytes:
    """Return the watermarked version of an audio blob.

    Uses a cached watermarked blob if available, otherwise generates one.
    For now, returns the original — watermark generation is a placeholder
    for the actual DSP implementation.
    """
    from . import storage

    data = storage.read_blob(version.blob_sha)

    # Placeholder: in production, this would apply an audible watermark
    # (e.g., low-volume repeated tone, spectral fingerprint, etc.)
    # For now, return original data with a note that watermarking is pending
    return data


def generate_watermark_key(version_id: int) -> str:
    """Generate a unique watermark key for a version."""
    return hashlib.sha256(f"watermark-{version_id}".encode()).hexdigest()[:16]
