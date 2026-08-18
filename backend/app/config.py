"""SoundHub backend configuration."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
# Optional local overrides in backend/.env (gitignored). Real environment
# variables always win — load_dotenv does not override what is already set,
# so Render/Fly secrets keep precedence over the local file.
load_dotenv(BASE_DIR / ".env")
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

# Stripe (paid delivery). Leave unset to run in manual-invoice mode.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.environ.get("STRIPE_CURRENCY", "usd")
STRIPE_API_BASE = os.environ.get("STRIPE_API_BASE", "https://api.stripe.com")

# USDC checkout (Base). BASE_RPC_URL unset → USDC flow disabled (card/manual only).
USDC_TOKEN_ADDRESS = os.environ.get(
    "SOUNDHUB_USDC_TOKEN", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # native USDC on Base
)
USDC_DECIMALS = int(os.environ.get("SOUNDHUB_USDC_DECIMALS", "6"))
USDC_CHAIN_ID = int(os.environ.get("SOUNDHUB_USDC_CHAIN_ID", "8453"))  # Base
BASE_RPC_URL = os.environ.get("SOUNDHUB_BASE_RPC_URL", "")  # e.g. https://mainnet.base.org
# Fallback payee when the engineer has no wallet linked yet (dev/demo only).
USDC_FALLBACK_PAYEE = os.environ.get("SOUNDHUB_USDC_FALLBACK_PAYEE", "")

# Reminders. SMTP_HOST unset → log-only transport (no real email sent).
FRONTEND_URL = os.environ.get("SOUNDHUB_FRONTEND_URL", "http://localhost:5173")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "SoundHub <no-reply@soundhub.local>")


def ensure_dirs() -> None:
    for d in (DATA_DIR, BLOB_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)
