"""Content-addressed blob storage.

Files are deduplicated by SHA-256 and stored flat under BLOB_DIR.
"""
import hashlib
import shutil
from pathlib import Path

from ..config import BLOB_DIR, TMP_DIR, ensure_dirs


def put_blob(data: bytes) -> str:
    ensure_dirs()
    sha = hashlib.sha256(data).hexdigest()
    dest = BLOB_DIR / sha
    if not dest.exists():
        dest.write_bytes(data)
    return sha


def get_blob_path(sha: str) -> Path:
    return BLOB_DIR / sha


def read_blob(sha: str) -> bytes:
    return get_blob_path(sha).read_bytes()


def blob_exists(sha: str) -> bool:
    return get_blob_path(sha).exists()


def put_upload_file(file, max_size: int) -> bytes:
    """Stream an UploadFile into memory (with size guard) and store as blob."""
    ensure_dirs()
    tmp = TMP_DIR / file.filename.replace("/", "_")
    size = 0
    with tmp.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_size:
                tmp.unlink(missing_ok=True)
                raise ValueError(f"File exceeds max size of {max_size} bytes")
            out.write(chunk)
    data = tmp.read_bytes()
    tmp.unlink(missing_ok=True)
    return data


def human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024
    return f"{size:.1f} TB"


def copy_blob_to(sha: str, dest: Path) -> None:
    shutil.copyfile(get_blob_path(sha), dest)
