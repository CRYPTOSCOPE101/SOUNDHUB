"""Session templates router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import SessionTemplateCreate, SessionTemplateOut, SessionTemplateUpdate
from ..security import get_current_user
from ..services import templates as templates_svc

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[SessionTemplateOut])
def list_templates(user=Depends(get_current_user), db: Session = Depends(get_db)):
    items = templates_svc.list_templates(db, user.id)
    return [SessionTemplateOut.model_validate(t, from_attributes=True) for t in items]


@router.post("", response_model=SessionTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(payload: SessionTemplateCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    template = templates_svc.create_template(db, user.id, payload.model_dump())
    return SessionTemplateOut.model_validate(template, from_attributes=True)


@router.get("/{template_id}", response_model=SessionTemplateOut)
def get_template(template_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    template = templates_svc.get_template(db, template_id)
    if template is None or (template.owner_id != user.id and not template.is_public):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return SessionTemplateOut.model_validate(template, from_attributes=True)


@router.patch("/{template_id}", response_model=SessionTemplateOut)
def update_template(template_id: int, payload: SessionTemplateUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    template = templates_svc.get_template(db, template_id)
    if template is None or template.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    updated = templates_svc.update_template(db, template, payload.model_dump(exclude_unset=True))
    return SessionTemplateOut.model_validate(updated, from_attributes=True)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    template = templates_svc.get_template(db, template_id)
    if template is None or template.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    templates_svc.delete_template(db, template)
