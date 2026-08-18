"""Session groups — folders for organizing sessions."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import SessionGroup, SessionGroupLink


def create_group(
    db: DbSession,
    owner_id: int,
    *,
    name: str,
    description: str = "",
    color: str = "#3b82f6",
    parent_id: int | None = None,
    sort_order: int = 0,
) -> SessionGroup:
    g = SessionGroup(
        owner_id=owner_id,
        name=name,
        description=description,
        color=color,
        parent_id=parent_id,
        sort_order=sort_order,
    )
    db.add(g)
    db.flush()
    return g


def list_groups(db: DbSession, owner_id: int) -> list[SessionGroup]:
    return list(
        db.scalars(
            select(SessionGroup)
            .where(SessionGroup.owner_id == owner_id, SessionGroup.parent_id.is_(None))
            .order_by(SessionGroup.sort_order, SessionGroup.name)
        ).all()
    )


def get_group(db: DbSession, group_id: int) -> SessionGroup | None:
    return db.get(SessionGroup, group_id)


def update_group(db: DbSession, group: SessionGroup, **fields) -> SessionGroup:
    for k, v in fields.items():
        if hasattr(group, k) and v is not None:
            setattr(group, k, v)
    db.flush()
    return group


def delete_group(db: DbSession, group: SessionGroup) -> None:
    # move children up one level
    for child in group.children:
        child.parent_id = group.parent_id
    db.query(SessionGroupLink).filter(SessionGroupLink.group_id == group.id).delete()
    db.delete(group)
    db.flush()


def add_session_to_group(db: DbSession, session_id: int, group_id: int) -> SessionGroupLink:
    existing = db.scalar(
        select(SessionGroupLink).where(
            SessionGroupLink.session_id == session_id,
            SessionGroupLink.group_id == group_id,
        )
    )
    if existing:
        return existing
    link = SessionGroupLink(session_id=session_id, group_id=group_id)
    db.add(link)
    db.flush()
    return link


def remove_session_from_group(db: DbSession, session_id: int, group_id: int) -> None:
    db.query(SessionGroupLink).filter(
        SessionGroupLink.session_id == session_id,
        SessionGroupLink.group_id == group_id,
    ).delete()
    db.flush()


def get_group_sessions(db: DbSession, group_id: int) -> list[int]:
    return list(
        db.scalars(
            select(SessionGroupLink.session_id).where(SessionGroupLink.group_id == group_id)
        ).all()
    )
