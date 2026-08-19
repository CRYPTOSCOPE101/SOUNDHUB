"""Webhooks router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import owned_or_404
from ..database import get_db
from ..models import Webhook, WebhookDelivery
from ..schemas import WebhookCreate, WebhookDeliveryOut, WebhookOut, WebhookUpdate
from ..security import get_current_user
from ..services import webhooks as webhooks_svc

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _validated_url(url: str) -> str:
    try:
        return webhooks_svc.validate_url(url)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("", response_model=list[WebhookOut])
def list_webhooks(user=Depends(get_current_user), db: Session = Depends(get_db)):
    hooks = db.scalars(
        select(Webhook).where(Webhook.owner_id == user.id).order_by(Webhook.created_at.desc())
    ).all()
    return [WebhookOut.model_validate(h, from_attributes=True) for h in hooks]


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def create_webhook(payload: WebhookCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    hook = Webhook(
        owner_id=user.id,
        url=_validated_url(payload.url),
        secret=payload.secret,
        events=payload.events,
        is_active=payload.is_active,
    )
    db.add(hook)
    db.commit()
    db.refresh(hook)
    return WebhookOut.model_validate(hook, from_attributes=True)


@router.patch("/{webhook_id}", response_model=WebhookOut)
def update_webhook(webhook_id: int, payload: WebhookUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    hook = owned_or_404(db, Webhook, webhook_id, user, "Webhook")
    if payload.url is not None:
        hook.url = _validated_url(payload.url)
    if payload.secret is not None:
        hook.secret = payload.secret
    if payload.events is not None:
        hook.events = payload.events
    if payload.is_active is not None:
        hook.is_active = payload.is_active
    db.commit()
    return WebhookOut.model_validate(hook, from_attributes=True)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(webhook_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    hook = owned_or_404(db, Webhook, webhook_id, user, "Webhook")
    db.delete(hook)
    db.commit()


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryOut])
def list_deliveries(webhook_id: int, limit: int = 50, user=Depends(get_current_user), db: Session = Depends(get_db)):
    owned_or_404(db, Webhook, webhook_id, user, "Webhook")
    deliveries = db.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    ).all()
    return [WebhookDeliveryOut.model_validate(d, from_attributes=True) for d in deliveries]
