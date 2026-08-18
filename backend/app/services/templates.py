"""Session template management."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SessionTemplate, User


def list_templates(db: Session, user_id: int) -> list[SessionTemplate]:
    """List all templates for a user (own + public)."""
    return list(
        db.scalars(
            select(SessionTemplate).where(
                (SessionTemplate.owner_id == user_id) | (SessionTemplate.is_public == True)
            ).order_by(SessionTemplate.use_count.desc())
        ).all()
    )


def get_template(db: Session, template_id: int) -> SessionTemplate | None:
    return db.get(SessionTemplate, template_id)


def create_template(db: Session, user_id: int, data: dict) -> SessionTemplate:
    template = SessionTemplate(owner_id=user_id, **data)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(db: Session, template: SessionTemplate, data: dict) -> SessionTemplate:
    for k, v in data.items():
        if v is not None:
            setattr(template, k, v)
    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template: SessionTemplate) -> None:
    db.delete(template)
    db.commit()


def use_template(db: Session, template: SessionTemplate) -> None:
    template.use_count += 1
    db.commit()
