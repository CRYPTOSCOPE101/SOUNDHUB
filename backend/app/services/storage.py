"""Content-addressed blob storage.

Files are stored by their SHA-256 hash — identical files are stored once,
re-pushing the same .als costs nothing. Dedup is automatic.
"""
import hashlib
from pathlib import Path

from fastapi import UploadFile

from ..config import BLOB_DIR


def _blob_path(sha: str) -> Path:
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
    path = _blob_path(sha)
    if not path.exists():
        raise FileNotFoundError(f"Blob {sha} not found")
    return path.read_bytes()


def blob_exists(sha: str) -> bool:
    return _blob_path(sha).exists()


def put_upload_file(upload: UploadFile, max_size: int) -> bytes:
    """Read an UploadFile into memory, enforcing a size limit."""
    data = upload.file.read()
    if len(data) > max_size:
        raise ValueError(f"File exceeds maximum size of {max_size} bytes")
    return data


def blob_size(sha: str) -> int:
    path = _blob_path(sha)
    return path.stat().st_size if path.exists() else 0
