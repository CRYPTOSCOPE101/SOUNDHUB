"""Marketplace catalog service."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Optional
import hashlib
import time

from ..models import ReviewSession, User, Package
from .. import config


def list_public_sessions(db: Session, limit: int = 50, offset: int = 0) -> list[dict]:
    """List public portfolio sessions."""
    sessions = db.scalars(
        select(ReviewSession)
        .where(ReviewSession.portfolio_public == True, ReviewSession.status == "approved")
        .order_by(ReviewSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "service_type": s.service_type,
            "genre": s.genre,
            "share_token": s.share_token,
            "owner_username": s.owner.username if s.owner else "",
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]


def list_engineers(db: Session, limit: int = 50) -> list[dict]:
    """List engineers with public profiles."""
    users = db.scalars(
        select(User).where(User.bio != "").limit(limit)
    ).all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "bio": u.bio,
            "specialty": u.specialty,
            "location": u.location,
        }
        for u in users
    ]


def find_asset(db: Session, asset_id: int) -> Optional[Package]:
    """Find an asset by ID."""
    return db.get(Package, asset_id)


def make_download_token(secret_key: str, listing_id: int, expires_in: int = 3600) -> str:
    """Create a download token for an asset."""
    # Simple token implementation for testing
    # In production, this would use proper signing like itsdangerous
    import hashlib
    timestamp = str(int(time.time()) + expires_in)
    data = f"{listing_id}:{timestamp}"
    signature = hashlib.sha256((data + secret_key).encode()).hexdigest()
    return f"{data}:{signature}"
