"""Folder organization for sessions."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SessionGroup, SessionGroupLink


def list_groups(db: Session, user_id: int) -> list[SessionGroup]:
    return list(
        db.scalars(
            select(SessionGroup)
            .where(SessionGroup.owner_id == user_id)
            .order_by(SessionGroup.sort_order, SessionGroup.name)
        ).all()
    )


def get_group(db: Session, group_id: int) -> SessionGroup | None:
    return db.get(SessionGroup, group_id)


def create_group(db: Session, user_id: int, data: dict) -> SessionGroup:
    group = SessionGroup(owner_id=user_id, **data)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def update_group(db: Session, group: SessionGroup, data: dict) -> SessionGroup:
    for k, v in data.items():
        if v is not None:
            setattr(group, k, v)
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, group: SessionGroup) -> None:
    # Unlink all sessions first
    links = db.scalars(
        select(SessionGroupLink).where(SessionGroupLink.group_id == group.id)
    ).all()
    for link in links:
        db.delete(link)
    db.delete(group)
    db.commit()


def link_session(db: Session, session_id: int, group_id: int) -> SessionGroupLink:
    link = SessionGroupLink(session_id=session_id, group_id=group_id)
    db.add(link)
    db.commit()
    return link


def unlink_session(db: Session, session_id: int, group_id: int) -> None:
    link = db.scalar(
        select(SessionGroupLink).where(
            SessionGroupLink.session_id == session_id,
            SessionGroupLink.group_id == group_id,
        )
    )
    if link:
        db.delete(link)
        db.commit()


def group_sessions(db: Session, group_id: int) -> list[int]:
    links = db.scalars(
        select(SessionGroupLink).where(SessionGroupLink.group_id == group_id)
    ).all()
    return [l.session_id for l in links]
