"""Session templates — reusable session configurations."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..models import SessionTemplate


def create_template(
    db: DbSession,
    owner_id: int,
    *,
    name: str,
    description: str = "",
    service_type: str = "mix_master",
    genre: str = "",
    included_rounds: int = 2,
    extra_round_price_cents: int = 0,
    deposit_due_cents: int = 0,
    required_deliverables: str = "master,instrumental",
    brief_template: str = "",
    is_public: bool = False,
) -> SessionTemplate:
    t = SessionTemplate(
        owner_id=owner_id,
        name=name,
        description=description,
        service_type=service_type,
        genre=genre,
        included_rounds=included_rounds,
        extra_round_price_cents=extra_round_price_cents,
        deposit_due_cents=deposit_due_cents,
        required_deliverables=required_deliverables,
        brief_template=brief_template,
        is_public=is_public,
    )
    db.add(t)
    db.flush()
    return t


def list_templates(db: DbSession, owner_id: int) -> list[SessionTemplate]:
    return list(
        db.scalars(
            select(SessionTemplate)
            .where(SessionTemplate.owner_id == owner_id)
            .order_by(SessionTemplate.name)
        ).all()
    )


def list_public_templates(db: DbSession) -> list[SessionTemplate]:
    return list(
        db.scalars(
            select(SessionTemplate)
            .where(SessionTemplate.is_public.is_(True))
            .order_by(SessionTemplate.use_count.desc())
        ).all()
    )


def get_template(db: DbSession, template_id: int) -> SessionTemplate | None:
    return db.get(SessionTemplate, template_id)


def delete_template(db: DbSession, template: SessionTemplate) -> None:
    db.delete(template)
    db.flush()
