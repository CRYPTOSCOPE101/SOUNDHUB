"""Ownership lookups shared by the API routers.

Every owner-scoped endpoint answers 404 (never 403) for rows belonging to
someone else, so a caller can't probe which ids exist.
"""
from typing import Protocol, TypeVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import Project, ReviewSession, User


class Owned(Protocol):
    """Row with a single owning user."""

    owner_id: int


T = TypeVar("T", bound=Owned)


def not_found(label: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")


def require_owner(obj: T | None, user: User, label: str) -> T:
    """Return `obj` when it exists and `user` owns it, else raise 404."""
    if obj is None or obj.owner_id != user.id:
        raise not_found(label)
    return obj


def owned_or_404(db: Session, model: type[T], obj_id: int, user: User, label: str) -> T:
    """Load `model` by primary key and require `user` to own it."""
    return require_owner(db.get(model, obj_id), user, label)


def session_or_404(db: Session, session_id: int, user: User) -> ReviewSession:
    return owned_or_404(db, ReviewSession, session_id, user, "Session")


def project_or_404(db: Session, project_id: int, user: User) -> Project:
    return owned_or_404(db, Project, project_id, user, "Project")
