"""SoundHub backend configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = Path(os.environ.get("SOUNDHUB_DATA_DIR", BASE_DIR / "data"))
BLOB_DIR = DATA_DIR / "blobs"
TMP_DIR = DATA_DIR / "tmp"

DATABASE_URL = os.environ.get(
    "SOUNDHUB_DATABASE_URL", f"sqlite:///{DATA_DIR / 'soundhub.db'}"
)

# Dev-only default; override via env in production.
SECRET_KEY = os.environ.get(
    "SOUNDHUB_SECRET_KEY", "dev-secret-change-me-9f8e7d6c5b4a39281706"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("SOUNDHUB_TOKEN_EXPIRE_MINUTES", "10080")
)  # 7 days by default

MAX_UPLOAD_SIZE = int(os.environ.get("SOUNDHUB_MAX_UPLOAD_SIZE", str(2 * 1024**3)))  # 2 GiB


def ensure_dirs() -> None:
    for d in (DATA_DIR, BLOB_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)
