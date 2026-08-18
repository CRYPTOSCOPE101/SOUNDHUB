"""Reference tracks for sessions."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReferenceTrack, ReviewSession, User
from ..schemas import ReferenceTrackCreate, ReferenceTrackOut
from ..security import get_current_user
from ..services import storage

router = APIRouter(prefix="/api/sessions/{session_id}/references", tags=["references"])


def _get_session(db: Session, session_id: int, user: User) -> ReviewSession:
    session = db.get(ReviewSession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


@router.get("", response_model=list[ReferenceTrackOut])
def list_references(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_session(db, session_id, user)
    refs = db.scalars(
        select(ReferenceTrack).where(ReferenceTrack.session_id == session_id)
    ).all()
    return [ReferenceTrackOut.model_validate(r, from_attributes=True) for r in refs]


@router.post("", response_model=ReferenceTrackOut, status_code=status.HTTP_201_CREATED)
def create_reference(session_id: int, payload: ReferenceTrackCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_session(db, session_id, user)
    ref = ReferenceTrack(
        session_id=session_id,
        title=payload.title,
        artist=payload.artist,
        source_type=payload.source_type,
        external_url=payload.external_url,
        purpose=payload.purpose,
        visibility=payload.visibility,
        note=payload.note,
        created_by=user.username,
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)
    return ReferenceTrackOut.model_validate(ref, from_attributes=True)


@router.delete("/{reference_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reference(session_id: int, reference_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_session(db, session_id, user)
    ref = db.get(ReferenceTrack, reference_id)
    if ref is None or ref.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reference not found")
    db.delete(ref)
    db.commit()
