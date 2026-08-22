"""Content-addressed local blob storage.

Files are stored by their SHA-256 hash — identical files are stored once,
re-pushing the same .als costs nothing. Dedup is automatic.

Implements the ObjectStorage protocol.
"""
import hashlib
import re
import secrets
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import UploadFile

from ...config import BLOB_DIR, SECRET_KEY

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _blob_path(sha: str) -> Path:
    if not _SHA256_RE.match(sha or ""):
        raise ValueError(f"Invalid blob id: {sha!r}")
    return BLOB_DIR / sha[:2] / sha[2:4] / sha


# ── Protocol implementation ─────────────────────────────────────────────


class LocalObjectStorage:
    """Local filesystem backend — zero external dependencies."""

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        sha = hashlib.sha256(data).hexdigest()
        path = _blob_path(sha)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return sha

    def get_bytes(self, key: str) -> bytes:
        try:
            path = _blob_path(key)
        except ValueError as exc:
            raise FileNotFoundError(str(exc)) from exc
        if not path.exists():
            raise FileNotFoundError(f"Blob {key} not found")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        try:
            path = _blob_path(key)
            if path.exists():
                path.unlink()
        except ValueError:
            pass

    def exists(self, key: str) -> bool:
        try:
            return _blob_path(key).exists()
        except ValueError:
            return False

    def create_upload_url(self, key: str, content_type: str, expires_in: int = 900) -> str:
        """For local storage, return a presigned-style upload token.

        The client POSTs the file to /api/storage/uploads/{token}/data.
        """
        ts = int(time.time())
        payload = f"upload:{key}:{ts}:{expires_in}"
        sig = hashlib.sha256((payload + SECRET_KEY).encode()).hexdigest()[:32]
        return f"local://upload/{quote(key, safe='')}/{ts}/{sig}"

    def create_download_url(self, key: str, expires_in: int = 900) -> str:
        """Return a presigned-style download URL for local storage."""
        ts = int(time.time())
        exp = ts + expires_in
        payload = f"download:{key}:{exp}"
        sig = hashlib.sha256((payload + SECRET_KEY).encode()).hexdigest()[:32]
        return f"local://download/{quote(key, safe='')}/{exp}/{sig}"

    def size(self, key: str) -> int:
        try:
            path = _blob_path(key)
        except ValueError:
            return 0
        return path.stat().st_size if path.exists() else 0


# ── Legacy convenience functions (backward-compatible) ──────────────────

_default = LocalObjectStorage()


def put_blob(data: bytes) -> str:
    """Store bytes, return SHA-256 hash (content address)."""
    return _default.put_bytes("unused", data)


def read_blob(sha: str) -> bytes:
    """Read blob by SHA-256 hash."""
    return _default.get_bytes(sha)


def blob_exists(sha: str) -> bool:
    return _default.exists(sha)


def put_upload_file(upload: UploadFile, max_size: int) -> bytes:
    """Read an UploadFile into memory, enforcing a size limit."""
    data = upload.file.read()
    if len(data) > max_size:
        raise ValueError(f"File exceeds maximum size of {max_size} bytes")
    return data


def blob_size(sha: str) -> int:
    return _default.size(sha)
