"""Webhook management — create, test, and inspect delivery history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services import webhooks as wh_svc

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: str
    events: str = "*"
    secret: str | None = None


class WebhookUpdate(BaseModel):
    url: str | None = None
    events: str | None = None
    secret: str | None = None
    is_active: bool | None = None


class WebhookOut(BaseModel):
    id: int
    url: str
    events: str
    is_active: bool
    last_status: int | None
    last_error: str
    created_at: str | None

    class Config:
        from_attributes = True


class DeliveryOut(BaseModel):
    id: int
    event_type: str
    status_code: int | None
    success: bool
    duration_ms: int | None
    response_body: str
    created_at: str | None

    class Config:
        from_attributes = True


@router.get("", response_model=list[WebhookOut])
def list_webhooks(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    whs = wh_svc.list_webhooks(db, user.id)
    return [
        WebhookOut(
            id=w.id, url=w.url, events=w.events, is_active=w.is_active,
            last_status=w.last_status, last_error=w.last_error,
            created_at=w.created_at.isoformat() if w.created_at else None,
        )
        for w in whs
    ]


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def create_webhook(
    body: WebhookCreate,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    wh = wh_svc.create_webhook(db, user.id, **body.model_dump())
    return WebhookOut(
        id=wh.id, url=wh.url, events=wh.events, is_active=wh.is_active,
        last_status=wh.last_status, last_error=wh.last_error,
        created_at=wh.created_at.isoformat() if wh.created_at else None,
    )


@router.get("/{webhook_id}", response_model=WebhookOut)
def get_webhook(
    webhook_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    wh = wh_svc.get_webhook(db, webhook_id)
    if not wh or wh.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    return WebhookOut(
        id=wh.id, url=wh.url, events=wh.events, is_active=wh.is_active,
        last_status=wh.last_status, last_error=wh.last_error,
        created_at=wh.created_at.isoformat() if wh.created_at else None,
    )


@router.patch("/{webhook_id}", response_model=WebhookOut)
def update_webhook(
    webhook_id: int,
    body: WebhookUpdate,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    wh = wh_svc.get_webhook(db, webhook_id)
    if not wh or wh.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    updated = wh_svc.update_webhook(db, wh, **body.model_dump(exclude_unset=True))
    return WebhookOut(
        id=updated.id, url=updated.url, events=updated.events,
        is_active=updated.is_active, last_status=updated.last_status,
        last_error=updated.last_error,
        created_at=updated.created_at.isoformat() if updated.created_at else None,
    )


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    wh = wh_svc.get_webhook(db, webhook_id)
    if not wh or wh.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    wh_svc.delete_webhook(db, wh)


@router.post("/{webhook_id}/test")
def test_webhook(
    webhook_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """Send a test event to verify the webhook endpoint."""
    wh = wh_svc.get_webhook(db, webhook_id)
    if not wh or wh.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    deliveries = wh_svc.trigger_webhooks(
        db, "webhook.test", {"message": "Test webhook from SoundHub"}, owner_id=user.id
    )
    if deliveries:
        d = deliveries[0]
        return {"ok": d.success, "status_code": d.status_code, "duration_ms": d.duration_ms}
    return {"ok": False, "error": "No matching webhook found"}


@router.get("/{webhook_id}/deliveries")
def get_deliveries(
    webhook_id: int,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    wh = wh_svc.get_webhook(db, webhook_id)
    if not wh or wh.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    deliveries = wh_svc.get_delivery_history(db, webhook_id, limit)
    return {
        "deliveries": [
            DeliveryOut(
                id=d.id, event_type=d.event_type, status_code=d.status_code,
                success=d.success, duration_ms=d.duration_ms,
                response_body=d.response_body,
                created_at=d.created_at.isoformat() if d.created_at else None,
            )
            for d in deliveries
        ]
    }
