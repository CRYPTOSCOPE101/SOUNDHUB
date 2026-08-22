"""ObjectStorage interface — pluggable backend for SoundHub assets.

Implementations:
- LocalObjectStorage  (default, content-addressed filesystem)
- S3ObjectStorage     (AWS S3 / MinIO / Cloudflare R2 / any S3-compatible)
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ObjectStorage(Protocol):
    """Minimal contract every storage backend must satisfy."""

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        """Store bytes under *key*. Returns the content-address (SHA-256 hex)."""
        ...

    def get_bytes(self, key: str) -> bytes:
        """Read blob by storage key."""
        ...

    def delete(self, key: str) -> None:
        """Delete a blob. Idempotent — no error if missing."""
        ...

    def exists(self, key: str) -> bool:
        """Return True if the blob exists in this backend."""
        ...

    def create_upload_url(self, key: str, content_type: str, expires_in: int = 900) -> str:
        """Return a short-lived URL the client can PUT/POST a file to directly."""
        ...

    def create_download_url(self, key: str, expires_in: int = 900) -> str:
        """Return a short-lived URL for the client to download a file."""
        ...

    def size(self, key: str) -> int:
        """Return blob size in bytes, or 0 if not found."""
        ...
