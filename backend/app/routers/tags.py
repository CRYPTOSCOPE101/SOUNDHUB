"""Tags router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReviewSession
from ..schemas import SessionTagCreate, SessionTagLinkCreate, SessionTagLinkOut, SessionTagOut, SessionTagUpdate
from ..security import get_current_user
from ..services import tags as tags_svc

router = APIRouter(prefix="/api/tags", tags=["tags"])


def _own_session(db: Session, session_id: int, user) -> ReviewSession:
    session = db.get(ReviewSession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


def _own_tag(db: Session, tag_id: int, user):
    tag = tags_svc.get_tag(db, tag_id)
    if tag is None or tag.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    return tag


@router.get("", response_model=list[SessionTagOut])
def list_tags(user=Depends(get_current_user), db: Session = Depends(get_db)):
    items = tags_svc.list_tags(db, user.id)
    return [SessionTagOut.model_validate(t, from_attributes=True) for t in items]


@router.post("", response_model=SessionTagOut, status_code=status.HTTP_201_CREATED)
def create_tag(payload: SessionTagCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    tag = tags_svc.create_tag(db, user.id, payload.name, payload.color)
    return SessionTagOut.model_validate(tag, from_attributes=True)


@router.patch("/{tag_id}", response_model=SessionTagOut)
def update_tag(tag_id: int, payload: SessionTagUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    tag = tags_svc.get_tag(db, tag_id)
    if tag is None or tag.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    updated = tags_svc.update_tag(db, tag, payload.name, payload.color)
    return SessionTagOut.model_validate(updated, from_attributes=True)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    tag = tags_svc.get_tag(db, tag_id)
    if tag is None or tag.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    tags_svc.delete_tag(db, tag)


@router.post("/session/{session_id}", response_model=SessionTagLinkOut, status_code=status.HTTP_201_CREATED)
def link_tag(session_id: int, payload: SessionTagLinkCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _own_session(db, session_id, user)
    _own_tag(db, payload.tag_id, user)
    link = tags_svc.link_tag(db, session_id, payload.tag_id)
    return SessionTagLinkOut.model_validate(link, from_attributes=True)


@router.delete("/session/{session_id}/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_tag(session_id: int, tag_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _own_session(db, session_id, user)
    tags_svc.unlink_tag(db, session_id, tag_id)
