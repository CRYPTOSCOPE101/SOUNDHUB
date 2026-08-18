"""Tag management for sessions."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SessionTag, SessionTagLink


def list_tags(db: Session, user_id: int) -> list[SessionTag]:
    return list(
        db.scalars(
            select(SessionTag).where(SessionTag.owner_id == user_id).order_by(SessionTag.name)
        ).all()
    )


def get_tag(db: Session, tag_id: int) -> SessionTag | None:
    return db.get(SessionTag, tag_id)


def create_tag(db: Session, user_id: int, name: str, color: str = "#6366f1") -> SessionTag:
    tag = SessionTag(owner_id=user_id, name=name, color=color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def update_tag(db: Session, tag: SessionTag, name: str | None = None, color: str | None = None) -> SessionTag:
    if name is not None:
        tag.name = name
    if color is not None:
        tag.color = color
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag: SessionTag) -> None:
    db.delete(tag)
    db.commit()


def link_tag(db: Session, session_id: int, tag_id: int) -> SessionTagLink:
    link = SessionTagLink(session_id=session_id, tag_id=tag_id)
    db.add(link)
    db.commit()
    return link


def unlink_tag(db: Session, session_id: int, tag_id: int) -> None:
    link = db.scalar(
        select(SessionTagLink).where(
            SessionTagLink.session_id == session_id,
            SessionTagLink.tag_id == tag_id,
        )
    )
    if link:
        db.delete(link)
        db.commit()


def session_tags(db: Session, session_id: int) -> list[SessionTag]:
    links = db.scalars(
        select(SessionTagLink).where(SessionTagLink.session_id == session_id)
    ).all()
    return [db.get(SessionTag, l.tag_id) for l in links if db.get(SessionTag, l.tag_id)]
