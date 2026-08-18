"""Content-addressed blob storage.

Files are stored by their SHA-256 hash — identical files are stored once,
re-pushing the same .als costs nothing. Dedup is automatic.
"""
import hashlib
import re
from pathlib import Path

from fastapi import UploadFile

from ..config import BLOB_DIR

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _blob_path(sha: str) -> Path:
    if not _SHA256_RE.match(sha or ""):
        raise ValueError(f"Invalid blob id: {sha!r}")
    return BLOB_DIR / sha[:2] / sha[2:4] / sha


def put_blob(data: bytes) -> str:
    """Store bytes, return SHA-256 hash (content address)."""
    sha = hashlib.sha256(data).hexdigest()
    path = _blob_path(sha)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return sha


def read_blob(sha: str) -> bytes:
    """Read blob by SHA-256 hash."""
    try:
        path = _blob_path(sha)
    except ValueError as exc:
        raise FileNotFoundError(str(exc)) from exc
    if not path.exists():
        raise FileNotFoundError(f"Blob {sha} not found")
    return path.read_bytes()


def blob_exists(sha: str) -> bool:
    try:
        return _blob_path(sha).exists()
    except ValueError:
        return False


def put_upload_file(upload: UploadFile, max_size: int) -> bytes:
    """Read an UploadFile into memory, enforcing a size limit."""
    data = upload.file.read()
    if len(data) > max_size:
        raise ValueError(f"File exceeds maximum size of {max_size} bytes")
    return data


def blob_size(sha: str) -> int:
    try:
        path = _blob_path(sha)
    except ValueError:
        return 0
    return path.stat().st_size if path.exists() else 0
