"""Version pins router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReviewSession, ReviewVersion, VersionPin
from ..schemas import VersionPinCreate, VersionPinOut
from ..security import get_current_user

router = APIRouter(prefix="/api/sessions/{session_id}/pins", tags=["pins"])


def _own_session(db: Session, session_id: int, user) -> ReviewSession:
    session = db.get(ReviewSession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


@router.get("", response_model=list[VersionPinOut])
def list_pins(session_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _own_session(db, session_id, user)
    pins = db.scalars(
        select(VersionPin).where(VersionPin.session_id == session_id)
    ).all()
    return [VersionPinOut.model_validate(p, from_attributes=True) for p in pins]


@router.post("", response_model=VersionPinOut, status_code=status.HTTP_201_CREATED)
def pin_version(session_id: int, payload: VersionPinCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _own_session(db, session_id, user)
    version = db.get(ReviewVersion, payload.version_id)
    if version is None or version.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    existing = db.scalar(
        select(VersionPin).where(
            VersionPin.session_id == session_id,
            VersionPin.version_id == payload.version_id,
        )
    )
    if existing:
        return VersionPinOut.model_validate(existing, from_attributes=True)
    pin = VersionPin(
        session_id=session_id,
        version_id=payload.version_id,
        pinned_by=user.id,
        label=payload.label,
    )
    db.add(pin)
    db.commit()
    db.refresh(pin)
    return VersionPinOut.model_validate(pin, from_attributes=True)


@router.delete("/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def unpin_version(session_id: int, version_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _own_session(db, session_id, user)
    pin = db.scalar(
        select(VersionPin).where(
            VersionPin.session_id == session_id,
            VersionPin.version_id == version_id,
            VersionPin.pinned_by == user.id,
        )
    )
    if pin:
        db.delete(pin)
        db.commit()
