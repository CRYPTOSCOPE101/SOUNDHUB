"""Public portfolio and engineer profiles."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReviewSession, User
from ..schemas import UserOut
from ..security import get_current_user
from ..services import catalog, reputation

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=list[dict])
def list_public_portfolios(db: Session = Depends(get_db)):
    return catalog.list_engineers(db)


@router.get("/{username}")
def get_portfolio(username: str, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Engineer not found")

    sessions = db.scalars(
        select(ReviewSession).where(
            ReviewSession.owner_id == user.id,
            ReviewSession.portfolio_public == True,
            ReviewSession.status == "approved",
        ).order_by(ReviewSession.updated_at.desc())
    ).all()

    rep = reputation.compute_reputation(db, user.id)
    badge = reputation.badge_for_score(rep["score"])

    return {
        "user": UserOut.model_validate(user, from_attributes=True),
        "sessions": [
            {
                "id": s.id,
                "name": s.name,
                "service_type": s.service_type,
                "genre": s.genre,
                "share_token": s.share_token,
            }
            for s in sessions
        ],
        "reputation": rep,
        "badge": badge,
    }
