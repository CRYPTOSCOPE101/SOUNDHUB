"""Tags — organize sessions with labels."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import SessionTag, SessionTagLink


def create_tag(db: DbSession, owner_id: int, name: str, color: str = "#6366f1") -> SessionTag:
    tag = SessionTag(owner_id=owner_id, name=name, color=color)
    db.add(tag)
    db.flush()
    return tag


def list_tags(db: DbSession, owner_id: int) -> list[SessionTag]:
    return list(
        db.scalars(
            select(SessionTag)
            .where(SessionTag.owner_id == owner_id)
            .order_by(SessionTag.name)
        ).all()
    )


def get_tag(db: DbSession, tag_id: int) -> SessionTag | None:
    return db.get(SessionTag, tag_id)


def delete_tag(db: DbSession, tag: SessionTag) -> None:
    # delete all links first
    db.query(SessionTagLink).filter(SessionTagLink.tag_id == tag.id).delete()
    db.delete(tag)
    db.flush()


def add_tag_to_session(db: DbSession, session_id: int, tag_id: int) -> SessionTagLink:
    existing = db.scalar(
        select(SessionTagLink).where(
            SessionTagLink.session_id == session_id,
            SessionTagLink.tag_id == tag_id,
        )
    )
    if existing:
        return existing
    link = SessionTagLink(session_id=session_id, tag_id=tag_id)
    db.add(link)
    db.flush()
    return link


def remove_tag_from_session(db: DbSession, session_id: int, tag_id: int) -> None:
    db.query(SessionTagLink).filter(
        SessionTagLink.session_id == session_id,
        SessionTagLink.tag_id == tag_id,
    ).delete()
    db.flush()


def get_session_tags(db: DbSession, session_id: int) -> list[SessionTag]:
    links = list(
        db.scalars(
            select(SessionTagLink).where(SessionTagLink.session_id == session_id)
        ).all()
    )
    if not links:
        return []
    tag_ids = [l.tag_id for l in links]
    return list(db.scalars(select(SessionTag).where(SessionTag.id.in_(tag_ids))).all())


def get_sessions_by_tag(db: DbSession, tag_id: int) -> list[int]:
    return list(
        db.scalars(
            select(SessionTagLink.session_id).where(SessionTagLink.tag_id == tag_id)
        ).all()
    )
