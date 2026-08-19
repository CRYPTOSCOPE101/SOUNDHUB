"""2FA / TOTP — Two-factor authentication for SoundHub accounts.

Uses TOTP (Time-based One-Time Password) compatible with Google Authenticator,
Authy, 1Password, etc.

Flow:
  1. POST /2fa/setup — generates secret + QR code URL
  2. User scans QR in their authenticator app
  3. POST /2fa/verify — user enters code to confirm
  4. GET /2fa/status — check if 2FA is enabled
  5. DELETE /2fa — disable 2FA (requires current TOTP code)
"""
from __future__ import annotations

import hashlib
import hmac
import time

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user

router = APIRouter(prefix="/api/2fa", tags=["2fa"])

# In-memory store for TOTP secrets (move to DB for production)
_totp_secrets: dict[int, str] = {}  # user_id -> secret
_totp_enabled: dict[int, bool] = {}  # user_id -> enabled
_totp_backup_codes: dict[int, list[str]] = {}  # user_id -> backup codes


def _generate_backup_codes(count: int = 10) -> list[str]:
    """Generate one-time backup codes."""
    import secrets
    return [secrets.token_hex(4) for _ in range(count)]


# ── Schemas ────────────────────────────────────────────────────────────────

class Setup2FAOut(BaseModel):
    secret: str
    otpauth_url: str
    backup_codes: list[str]

class Verify2FAIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)  # 6-digit TOTP or 8-char backup

class TwoFAStatusOut(BaseModel):
    enabled: bool
    has_secret: bool

class Disable2FAIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/setup", response_model=Setup2FAOut)
def setup_2fa(user: User = Depends(get_current_user)):
    """Generate a new TOTP secret for 2FA setup.

    Returns:
      - secret: Base32-encoded TOTP secret (save this!)
      - otpauth_url: URL for QR code generation
      - backup_codes: One-time recovery codes
    """
    secret = pyotp.random_base32()
    _totp_secrets[user.id] = secret
    _totp_backup_codes[user.id] = _generate_backup_codes()

    totp = pyotp.TOTP(secret)
    otpauth_url = totp.provisioning_uri(
        name=user.username,
        issuer_name="SoundHub",
    )

    return Setup2FAOut(
        secret=secret,
        otpauth_url=otpauth_url,
        backup_codes=_totp_backup_codes[user.id],
    )


@router.post("/verify")
def verify_2fa(payload: Verify2FAIn, user: User = Depends(get_current_user)):
    """Verify a TOTP code to enable 2FA.

    Must call /setup first to generate the secret.
    """
    secret = _totp_secrets.get(user.id)
    if secret is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No 2FA setup in progress. Call /setup first.")

    totp = pyotp.TOTP(secret)

    # Try TOTP code
    if totp.verify(payload.code, valid_window=1):
        _totp_enabled[user.id] = True
        return {"ok": True, "message": "2FA enabled successfully"}

    # Try backup code
    backup_codes = _totp_backup_codes.get(user.id, [])
    if payload.code.lower() in [c.lower() for c in backup_codes]:
        _totp_enabled[user.id] = True
        # Remove used backup code
        _totp_backup_codes[user.id] = [c for c in backup_codes if c.lower() != payload.code.lower()]
        return {"ok": True, "message": "2FA enabled via backup code"}

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code")


@router.get("/status", response_model=TwoFAStatusOut)
def get_2fa_status(user: User = Depends(get_current_user)):
    """Check if 2FA is enabled for the current user."""
    return TwoFAStatusOut(
        enabled=_totp_enabled.get(user.id, False),
        has_secret=user.id in _totp_secrets,
    )


@router.delete("")
def disable_2fa(payload: Disable2FAIn, user: User = Depends(get_current_user)):
    """Disable 2FA — requires a valid TOTP code for confirmation."""
    if not _totp_enabled.get(user.id, False):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "2FA is not enabled")

    secret = _totp_secrets.get(user.id)
    if secret is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No TOTP secret found")

    totp = pyotp.TOTP(secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code")

    _totp_enabled[user.id] = False
    _totp_secrets.pop(user.id, None)
    _totp_backup_codes.pop(user.id, None)

    return {"ok": True, "message": "2FA disabled"}


@router.post("/validate")
def validate_2fa_code(code: str, user_id: int):
    """Validate a TOTP code (internal use for login flow).

    This endpoint is called during login when 2FA is enabled.
    """
    if not _totp_enabled.get(user_id, False):
        return {"valid": True, "message": "2FA not required"}

    secret = _totp_secrets.get(user_id)
    if secret is None:
        return {"valid": False, "message": "No TOTP secret"}

    totp = pyotp.TOTP(secret)
    if totp.verify(code, valid_window=1):
        return {"valid": True}

    # Check backup codes
    backup_codes = _totp_backup_codes.get(user_id, [])
    if code.lower() in [c.lower() for c in backup_codes]:
        _totp_backup_codes[user_id] = [c for c in backup_codes if c.lower() != code.lower()]
        return {"valid": True, "message": "Backup code used"}

    return {"valid": False, "message": "Invalid code"}
