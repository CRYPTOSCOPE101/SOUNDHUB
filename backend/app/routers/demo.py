"""Demo endpoints for public-facing sample review."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from ..database import get_db
from ..models import ReviewSession, ReviewVersion, User
from ..security import get_current_user

router = APIRouter(prefix="/api/demo", tags=["demo"])

DEMO_TOKEN = "demo-review-token"
DEMO_SESSION_NAME = "Neon Warehouse — sample review"


@router.get("/review")
def demo_review(db=Depends(get_db)):
    """Return (or create) the fixed demo review session."""
    # Find existing demo session
    session = db.scalar(
        select(ReviewSession).where(ReviewSession.share_token == DEMO_TOKEN)
    )

    if session is None:
        # Find or create the demo user
        user = db.scalar(select(User).where(User.username == "demo"))
        if user is None:
            from ..security import hash_password
            user = User(
                username="demo",
                password_hash=hash_password("demo123"),
                bio="SoundHub demo engineer",
                specialty="Mixing & Mastering",
                location="Berlin, DE",
            )
            db.add(user)
            db.flush()

        session = ReviewSession(
            owner_id=user.id,
            name=DEMO_SESSION_NAME,
            share_token=DEMO_TOKEN,
            share_permission="download",
        )
        db.add(session)
        db.flush()

    # Count versions
    version_count = db.scalar(
        select(ReviewVersion.id).where(ReviewVersion.session_id == session.id)
    )

    return {
        "share_token": session.share_token,
        "name": session.name,
        "url": f"/r/{session.share_token}",
        "version_count": 1 if version_count else 0,
    }
