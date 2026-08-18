"""Session groups — folders for organizing sessions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services import groups as groups_svc

router = APIRouter(prefix="/api/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#3b82f6"
    parent_id: int | None = None
    sort_order: int = 0


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    color: str
    parent_id: int | None
    sort_order: int

    class Config:
        from_attributes = True


@router.get("", response_model=list[GroupOut])
def list_groups(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return groups_svc.list_groups(db, user.id)


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    body: GroupCreate,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return groups_svc.create_group(db, user.id, **body.model_dump())


@router.get("/{group_id}", response_model=GroupOut)
def get_group(
    group_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    g = groups_svc.get_group(db, group_id)
    if not g or g.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return g


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(
    group_id: int,
    body: GroupUpdate,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    g = groups_svc.get_group(db, group_id)
    if not g or g.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return groups_svc.update_group(db, g, **body.model_dump(exclude_unset=True))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    g = groups_svc.get_group(db, group_id)
    if not g or g.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    groups_svc.delete_group(db, g)


@router.post("/sessions/{session_id}/groups/{group_id}", status_code=status.HTTP_201_CREATED)
def add_session_to_group(
    session_id: int,
    group_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    g = groups_svc.get_group(db, group_id)
    if not g or g.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return groups_svc.add_session_to_group(db, session_id, group_id)


@router.delete("/sessions/{session_id}/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_session_from_group(
    session_id: int,
    group_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    groups_svc.remove_session_from_group(db, session_id, group_id)


@router.get("/{group_id}/sessions")
def get_group_sessions(
    group_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    g = groups_svc.get_group(db, group_id)
    if not g or g.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return {"session_ids": groups_svc.get_group_sessions(db, group_id)}
