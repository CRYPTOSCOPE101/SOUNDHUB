"""Groups (folders) router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import SessionGroupCreate, SessionGroupLinkCreate, SessionGroupLinkOut, SessionGroupOut, SessionGroupUpdate
from ..security import get_current_user
from ..services import groups as groups_svc

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("", response_model=list[SessionGroupOut])
def list_groups(user=Depends(get_current_user), db: Session = Depends(get_db)):
    items = groups_svc.list_groups(db, user.id)
    return [SessionGroupOut.model_validate(g, from_attributes=True) for g in items]


@router.post("", response_model=SessionGroupOut, status_code=status.HTTP_201_CREATED)
def create_group(payload: SessionGroupCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    group = groups_svc.create_group(db, user.id, payload.model_dump())
    return SessionGroupOut.model_validate(group, from_attributes=True)


@router.patch("/{group_id}", response_model=SessionGroupOut)
def update_group(group_id: int, payload: SessionGroupUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    group = groups_svc.get_group(db, group_id)
    if group is None or group.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    updated = groups_svc.update_group(db, group, payload.model_dump(exclude_unset=True))
    return SessionGroupOut.model_validate(updated, from_attributes=True)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    group = groups_svc.get_group(db, group_id)
    if group is None or group.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    groups_svc.delete_group(db, group)


@router.post("/session/{session_id}", response_model=SessionGroupLinkOut, status_code=status.HTTP_201_CREATED)
def link_session(session_id: int, payload: SessionGroupLinkCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    link = groups_svc.link_session(db, session_id, payload.group_id)
    return SessionGroupLinkOut.model_validate(link, from_attributes=True)


@router.delete("/session/{session_id}/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_session(session_id: int, group_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    groups_svc.unlink_session(db, session_id, group_id)
