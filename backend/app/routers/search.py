"""Global search router."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReviewSession, User
from ..schemas import SearchResultOut
from ..security import get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResultOut)
def search(q: str = Query(..., min_length=1), user=Depends(get_current_user), db: Session = Depends(get_db)):
    like = f"%{q}%"

    engineers = db.scalars(
        select(User).where(User.username.ilike(like)).limit(10)
    ).all()

    sessions = db.scalars(
        select(ReviewSession)
        .where(ReviewSession.name.ilike(like), ReviewSession.portfolio_public == True)
        .limit(10)
    ).all()

    return SearchResultOut(
        query=q,
        engineers=[
            {"id": e.id, "username": e.username, "bio": e.bio}
            for e in engineers
        ],
        sessions=[
            {"id": s.id, "name": s.name, "owner_username": s.owner.username if s.owner else ""}
            for s in sessions
        ],
    )
