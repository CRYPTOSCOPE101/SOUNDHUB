"""Session templates — reusable session configurations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import User
from ..schemas import ReviewSessionDetailOut
from ..security import get_current_user
from ..services import templates as tpl_svc

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    service_type: str = "mix_master"
    genre: str = ""
    included_rounds: int = 2
    extra_round_price_cents: int = 0
    deposit_due_cents: int = 0
    required_deliverables: str = "master,instrumental"
    brief_template: str = ""
    is_public: bool = False


class TemplateOut(BaseModel):
    id: int
    name: str
    description: str
    service_type: str
    genre: str
    included_rounds: int
    extra_round_price_cents: int
    deposit_due_cents: int
    required_deliverables: str
    brief_template: str
    is_public: bool
    use_count: int

    class Config:
        from_attributes = True


@router.get("", response_model=list[TemplateOut])
def list_templates(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return tpl_svc.list_templates(db, user.id)


@router.get("/public", response_model=list[TemplateOut])
def list_public_templates(db: DbSession = Depends(get_db)):
    return tpl_svc.list_public_templates(db)


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    body: TemplateCreate,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    return tpl_svc.create_template(db, user.id, **body.model_dump())


@router.get("/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    t = tpl_svc.get_template(db, template_id)
    if not t or (t.owner_id != user.id and not t.is_public):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return t


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    t = tpl_svc.get_template(db, template_id)
    if not t or t.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    tpl_svc.delete_template(db, t)
