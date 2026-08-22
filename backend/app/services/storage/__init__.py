"""SoundHub pluggable object storage.

Provider is selected via SOUNDHUB_STORAGE_PROVIDER env var:
- ``local`` (default) — content-addressed filesystem in data/blobs/
- ``s3``             — AWS S3 / MinIO / Cloudflare R2 (requires boto3)

All legacy ``from ..services.storage import put_blob`` imports keep working.
"""
from __future__ import annotations

import os

from .base import ObjectStorage
from .local import LocalObjectStorage

# ── Singleton provider instance ─────────────────────────────────────────

_provider: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    """Return the configured ObjectStorage backend (lazy singleton)."""
    global _provider
    if _provider is not None:
        return _provider

    backend = os.environ.get("SOUNDHUB_STORAGE_PROVIDER", "local").lower()
    if backend == "s3":
        from .s3 import S3ObjectStorage

        _provider = S3ObjectStorage()
    else:
        _provider = LocalObjectStorage()
    return _provider


# ── Re-export legacy convenience API ────────────────────────────────────

from .local import (  # noqa: E402, F401 — backward-compatible re-exports
    blob_exists,
    blob_size,
    put_blob,
    put_upload_file,
    read_blob,
)

# Re-export config constants used by tests and legacy code
from ...config import BLOB_DIR  # noqa: E402, F401

__all__ = [
    # Protocol
    "ObjectStorage",
    # Provider factory
    "get_storage",
    # Legacy convenience functions
    "put_blob",
    "read_blob",
    "blob_exists",
    "put_upload_file",
    "blob_size",
]
