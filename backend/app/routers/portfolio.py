"""Public engineer portfolio — a showcase of approved work.

Engineers mark sessions `portfolio_public` in the share settings; the
portfolio page lists them with the approved version and a delivery link
(when the release package is locked). Preview streams are always
watermarked, so the clean files stay behind the paid delivery gate.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReleasePackage, ReviewSession, ReviewVersion, User
from ..schemas import PortfolioOut, PortfolioTrackOut
from ..services import storage, watermark

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _get_public_engineer(db: Session, username: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Engineer not found")
    return user


@router.get("/{username}", response_model=PortfolioOut)
def portfolio(username: str, db: Session = Depends(get_db)):
    """Public portfolio: published sessions with approved versions."""
    user = _get_public_engineer(db, username)
    sessions = db.scalars(
        select(ReviewSession)
        .where(ReviewSession.owner_id == user.id, ReviewSession.portfolio_public.is_(True))
        .order_by(ReviewSession.updated_at.desc())
    ).all()
    tracks: list[PortfolioTrackOut] = []
    for s in sessions:
        versions = db.scalars(
            select(ReviewVersion)
            .where(ReviewVersion.session_id == s.id)
            .order_by(ReviewVersion.number.desc())
        ).all()
        approved = next((v for v in versions if v.status == "approved"), None)
        pkg = db.scalar(
            select(ReleasePackage)
            .where(ReleasePackage.session_id == s.id, ReleasePackage.status == "ready")
            .order_by(ReleasePackage.id.desc())
            .limit(1)
        )
        tracks.append(
            PortfolioTrackOut(
                session_id=s.id,
                name=s.name,
                status=s.status,
                version_count=len(versions),
                has_approved=approved is not None,
                approved_label=approved.label if approved else "",
                approved_filename=approved.filename if approved else "",
                approved_version_id=approved.id if approved else None,
                approved_duration_s=approved.duration_s if approved else 0.0,
                approved_at=approved.created_at if approved else None,
                delivery_token=pkg.delivery_token if pkg else None,
            )
        )
    return PortfolioOut(username=user.username, track_count=len(tracks), tracks=tracks)


@router.get("/{username}/preview/{version_id}")
def portfolio_preview(username: str, version_id: int, db: Session = Depends(get_db)):
    """Watermarked preview of an approved version on a public portfolio."""
    user = _get_public_engineer(db, username)
    version = db.get(ReviewVersion, version_id)
    if version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    session = db.get(ReviewSession, version.session_id)
    if session is None or session.owner_id != user.id or not session.portfolio_public:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    # portfolio previews are always watermarked — clean files come from the
    # paid delivery link, never from the public showcase
    data = watermark.watermarked_blob(db, version)
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type=f"audio/{version.audio_format}",
        headers={"Content-Disposition": f'inline; filename="{version.filename}"'},
    )
