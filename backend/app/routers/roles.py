"""Team roles & approval-chain endpoints (owner manages the team; the chain
itself runs on guest approvals via member emails)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SessionMember, User
from ..schemas import (
    ApprovalPolicyOut,
    ApprovalPresetUpdate,
    SessionMemberCreate,
    SessionMemberOut,
)
from ..security import get_current_user
from ..services import ledger, roles
from .sessions import get_session_or_404

router = APIRouter(prefix="/api/sessions", tags=["team roles"])


def _member_out(m: SessionMember) -> SessionMemberOut:
    return SessionMemberOut.model_validate(m, from_attributes=True)


@router.get("/{session_id}/team", response_model=ApprovalPolicyOut)
def get_team_policy(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Engineer view: the approval preset + invited members for this session."""
    session = get_session_or_404(db, user, session_id)
    policy = roles.policy_for_session(session)
    policy["roles"] = [roles.ROLE_LABELS.get(r, r) for r in policy["roles"]]
    return policy


@router.get("/{session_id}/members", response_model=list[SessionMemberOut])
def list_members(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user, session_id)
    rows = db.scalars(
        select(SessionMember)
        .where(SessionMember.session_id == session.id)
        .order_by(SessionMember.id)
    ).all()
    return [_member_out(m) for m in rows]


@router.post("/{session_id}/members", response_model=SessionMemberOut, status_code=status.HTTP_201_CREATED)
def invite_member(
    session_id: int,
    payload: SessionMemberCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invite a participant by email + role (artist, A&R, label admin, …)."""
    session = get_session_or_404(db, user, session_id)
    email = payload.email.strip().lower()
    existing = db.scalar(
        select(SessionMember).where(
            SessionMember.session_id == session.id,
            SessionMember.email == email,
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{email} is already on the team")
    member = SessionMember(
        session_id=session.id,
        email=email,
        role=payload.role,
        invited_by=user.username,
    )
    db.add(member)
    db.flush()
    session.updated_at = session.updated_at
    ledger.append(
        db,
        "team.member_invited",
        session_id=session.id,
        actor=user.username,
        entity_type="session",
        entity_id=member.id,
        payload={"email": email, "role": payload.role},
    )
    db.commit()
    db.refresh(member)
    return _member_out(member)


@router.delete("/{session_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    session_id: int,
    member_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user, session_id)
    member = db.get(SessionMember, member_id)
    if member is None or member.session_id != session.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    email = member.email
    role = member.role
    db.delete(member)
    db.flush()
    ledger.append(
        db,
        "team.member_removed",
        session_id=session.id,
        actor=user.username,
        entity_type="session",
        entity_id=member_id,
        payload={"email": email, "role": role},
    )
    db.commit()


@router.put("/{session_id}/approval-preset", response_model=ApprovalPolicyOut)
def set_approval_preset(
    session_id: int,
    payload: ApprovalPresetUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pick the workflow preset. Default is solo_client — no enterprise noise."""
    session = get_session_or_404(db, user, session_id)
    if session.approval_preset != payload.preset:
        session.approval_preset = payload.preset
        session.updated_at = session.updated_at
        ledger.append(
            db,
            "team.preset_updated",
            session_id=session.id,
            actor=user.username,
            entity_type="session",
            entity_id=session.id,
            payload={"from": session.approval_preset, "to": payload.preset},
        )
    db.commit()
    return roles.policy_for_session(session)
