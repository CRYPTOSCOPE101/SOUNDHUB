"""Version pins — mark important versions for quick access."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from ..database import get_db
from ..models import User, VersionPin
from ..security import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["pins"])


class PinCreate(BaseModel):
    version_id: int
    label: str = ""


class PinOut(BaseModel):
    id: int
    session_id: int
    version_id: int
    label: str
    created_at: str | None

    class Config:
        from_attributes = True


@router.get("/{session_id}/pins")
def list_pins(
    session_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    pins = list(
        db.scalars(
            select(VersionPin).where(VersionPin.session_id == session_id)
        ).all()
    )
    return {
        "pins": [
            PinOut(
                id=p.id, session_id=p.session_id, version_id=p.version_id,
                label=p.label,
                created_at=p.created_at.isoformat() if p.created_at else None,
            )
            for p in pins
        ]
    }


@router.post("/{session_id}/pins", response_model=PinOut, status_code=status.HTTP_201_CREATED)
def pin_version(
    session_id: int,
    body: PinCreate,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    existing = db.scalar(
        select(VersionPin).where(
            VersionPin.session_id == session_id,
            VersionPin.version_id == body.version_id,
        )
    )
    if existing:
        return PinOut(
            id=existing.id, session_id=existing.session_id,
            version_id=existing.version_id, label=existing.label,
            created_at=existing.created_at.isoformat() if existing.created_at else None,
        )
    pin = VersionPin(
        session_id=session_id,
        version_id=body.version_id,
        pinned_by=user.id,
        label=body.label,
    )
    db.add(pin)
    db.flush()
    return PinOut(
        id=pin.id, session_id=pin.session_id, version_id=pin.version_id,
        label=pin.label,
        created_at=pin.created_at.isoformat() if pin.created_at else None,
    )


@router.delete("/{session_id}/pins/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
def unpin_version(
    session_id: int,
    pin_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    pin = db.get(VersionPin, pin_id)
    if not pin or pin.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pin not found")
    db.delete(pin)
    db.flush()
