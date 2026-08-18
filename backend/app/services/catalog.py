"""Marketplace catalog service."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ReviewSession, User


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
