"""Public search — findable engineers and public review sessions.

Bandcamp-style: the header search returns real, publicly reachable things —
engineers with a public portfolio and sessions marked `portfolio_public`.
Private sessions never appear here.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReviewSession, User

router = APIRouter(prefix="/api/search", tags=["search"])

MAX_RESULTS = 8


@router.get("")
def search(
    q: str = Query(default="", max_length=64),
    db: Session = Depends(get_db),
) -> dict:
    query = q.strip()
    if not query:
        return {"query": query, "engineers": [], "sessions": []}
    pattern = f"%{query}%"

    # Engineers = users with at least one public session (findable people).
    public_owner_ids = (
        select(ReviewSession.owner_id)
        .where(ReviewSession.portfolio_public.is_(True))
        .distinct()
        .subquery()
    )
    engineers = db.scalars(
        select(User)
        .where(User.username.ilike(pattern), User.id.in_(select(public_owner_ids.c.owner_id)))
        .order_by(User.username)
        .limit(MAX_RESULTS)
    ).all()
    counts = dict(
        db.execute(
            select(ReviewSession.owner_id, func.count(ReviewSession.id))
            .where(ReviewSession.portfolio_public.is_(True))
            .group_by(ReviewSession.owner_id)
        ).all()
    )

    sessions = db.scalars(
        select(ReviewSession)
        .where(ReviewSession.portfolio_public.is_(True), ReviewSession.name.ilike(pattern))
        .order_by(ReviewSession.updated_at.desc())
        .limit(MAX_RESULTS)
    ).all()
    owner_names = {
        u.id: u.username
        for u in db.scalars(select(User).where(User.id.in_({s.owner_id for s in sessions}))).all()
    }

    return {
        "query": query,
        "engineers": [
            {"username": u.username, "session_count": counts.get(u.id, 0)} for u in engineers
        ],
        "sessions": [
            {
                "name": s.name,
                "owner_username": owner_names.get(s.owner_id, ""),
                "share_token": s.share_token,
                "status": s.status,
                "updated_at": s.updated_at,
            }
            for s in sessions
        ],
    }
