"""SoundHub backend configuration."""
import os
import secrets
import warnings
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # soundhub-backend/
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.environ.get("SOUNDHUB_DATA_DIR", BASE_DIR / "data"))
BLOB_DIR = DATA_DIR / "blobs"
TMP_DIR = DATA_DIR / "tmp"

DATABASE_URL = os.environ.get(
    "SOUNDHUB_DATABASE_URL", f"sqlite:///{DATA_DIR / 'soundhub.db'}"
)

ENV = os.environ.get("SOUNDHUB_ENV", "development").lower()
IS_PRODUCTION = ENV in {"production", "prod"}


def _secret_key() -> str:
    key = os.environ.get("SOUNDHUB_SECRET_KEY", "").strip()
    if key:
        return key
    if IS_PRODUCTION:
        raise RuntimeError(
            "SOUNDHUB_SECRET_KEY must be set when SOUNDHUB_ENV=production"
        )
    warnings.warn(
        "SOUNDHUB_SECRET_KEY is not set — generating an ephemeral key. "
        "Tokens will be invalidated on restart.",
        stacklevel=2,
    )
    return secrets.token_urlsafe(48)


SECRET_KEY = _secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("SOUNDHUB_TOKEN_EXPIRE_MINUTES", "10080")
)  # 7 days

MAX_UPLOAD_SIZE = int(os.environ.get("SOUNDHUB_MAX_UPLOAD_SIZE", str(2 * 1024**3)))  # 2 GiB

# Stripe
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.environ.get("STRIPE_CURRENCY", "usd")
STRIPE_API_BASE = os.environ.get("STRIPE_API_BASE", "https://api.stripe.com")

# USDC on Base
USDC_TOKEN_ADDRESS = os.environ.get(
    "SOUNDHUB_USDC_TOKEN", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
)
USDC_DECIMALS = int(os.environ.get("SOUNDHUB_USDC_DECIMALS", "6"))
USDC_CHAIN_ID = int(os.environ.get("SOUNDHUB_USDC_CHAIN_ID", "8453"))
BASE_RPC_URL = os.environ.get("SOUNDHUB_BASE_RPC_URL", "")
USDC_FALLBACK_PAYEE = os.environ.get("SOUNDHUB_USDC_FALLBACK_PAYEE", "")

# CORS — comma-separated list of allowed browser origins.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "SOUNDHUB_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# Email / Reminders
FRONTEND_URL = os.environ.get("SOUNDHUB_FRONTEND_URL", "http://localhost:5173")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "SoundHub <no-reply@soundhub.local>")


def ensure_dirs() -> None:
    for d in (DATA_DIR, BLOB_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)
