"""Team roles router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReviewSession, SessionMember, User
from ..schemas import RoleOut, RoleUpdate
from ..security import get_current_user
from ..services import roles as roles_svc

router = APIRouter(prefix="/api/sessions/{session_id}/roles", tags=["roles"])


@router.get("", response_model=list[RoleOut])
def list_roles(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(ReviewSession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    members = db.scalars(
        select(SessionMember).where(SessionMember.session_id == session_id)
    ).all()
    return [RoleOut.model_validate(m, from_attributes=True) for m in members]


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def add_member(session_id: int, payload: RoleUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(ReviewSession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    existing = db.scalar(
        select(SessionMember).where(
            SessionMember.session_id == session_id,
            SessionMember.email == payload.email.lower().strip(),
        )
    )
    if existing:
        existing.role = payload.role
        db.commit()
        return RoleOut.model_validate(existing, from_attributes=True)
    member = SessionMember(
        session_id=session_id,
        email=payload.email.lower().strip(),
        role=payload.role,
        invited_by=user.username,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return RoleOut.model_validate(member, from_attributes=True)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(session_id: int, member_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(ReviewSession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    member = db.get(SessionMember, member_id)
    if member is None or member.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    db.delete(member)
    db.commit()


@router.get("/presets")
def list_presets():
    return roles_svc.list_presets()
