"""Tags — organize sessions with labels."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import User
from ..schemas import ReviewSessionOut
from ..security import get_current_user
from ..services import tags as tags_svc

router = APIRouter(prefix="/api/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: str
    color: str = "#6366f1"


class TagOut(BaseModel):
    id: int
    name: str
    color: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[TagOut])
def list_tags(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return tags_svc.list_tags(db, user.id)


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(
    body: TagCreate,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return tags_svc.create_tag(db, user.id, body.name, body.color)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    tag = tags_svc.get_tag(db, tag_id)
    if not tag or tag.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    tags_svc.delete_tag(db, tag)


@router.post("/sessions/{session_id}/tags/{tag_id}", status_code=status.HTTP_201_CREATED)
def add_tag_to_session(
    session_id: int,
    tag_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    tag = tags_svc.get_tag(db, tag_id)
    if not tag or tag.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    return tags_svc.add_tag_to_session(db, session_id, tag_id)


@router.delete("/sessions/{session_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tag_from_session(
    session_id: int,
    tag_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    tags_svc.remove_tag_from_session(db, session_id, tag_id)


@router.get("/sessions/{session_id}", response_model=list[TagOut])
def get_session_tags(
    session_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return tags_svc.get_session_tags(db, session_id)


@router.get("/{tag_id}/sessions")
def get_sessions_by_tag(
    tag_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    tag = tags_svc.get_tag(db, tag_id)
    if not tag or tag.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    return {"session_ids": tags_svc.get_sessions_by_tag(db, tag_id)}
