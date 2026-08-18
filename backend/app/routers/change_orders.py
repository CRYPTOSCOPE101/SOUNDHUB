"""Change orders router — late change requests after approval."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ChangeOrder, ReviewSession, User, utcnow
from ..schemas import ChangeOrderCreate, ChangeOrderOut, ChangeOrderQuote
from ..security import get_current_user
from ..services import ledger

router = APIRouter(prefix="/api/sessions/{session_id}/change-orders", tags=["change orders"])


def _get_session(db: Session, session_id: int, user: User) -> ReviewSession:
    session = db.get(ReviewSession, session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return session


@router.get("", response_model=list[ChangeOrderOut])
def list_change_orders(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_session(db, session_id, user)
    orders = db.scalars(
        select(ChangeOrder).where(ChangeOrder.session_id == session_id).order_by(ChangeOrder.created_at.desc())
    ).all()
    return [ChangeOrderOut.model_validate(o, from_attributes=True) for o in orders]


@router.post("", response_model=ChangeOrderOut, status_code=status.HTTP_201_CREATED)
def create_change_order(session_id: int, payload: ChangeOrderCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = _get_session(db, session_id, user)
    order = ChangeOrder(
        session_id=session_id,
        created_by=user.username,
        reason=payload.reason,
        description=payload.description,
    )
    db.add(order)
    ledger.append(db, "change_order.created", session_id=session_id, actor=user.username, entity_type="change_order", entity_id=order.id, payload={"reason": payload.reason})
    db.commit()
    db.refresh(order)
    return ChangeOrderOut.model_validate(order, from_attributes=True)


@router.patch("/{order_id}/quote", response_model=ChangeOrderOut)
def quote_change_order(session_id: int, order_id: int, payload: ChangeOrderQuote, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_session(db, session_id, user)
    order = db.get(ChangeOrder, order_id)
    if order is None or order.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change order not found")
    order.decision = payload.decision
    order.price_cents = payload.price_cents
    order.deadline_at = payload.deadline_at
    order.status = "quoted"
    order.quoted_at = utcnow()
    order.quote_version += 1
    db.commit()
    return ChangeOrderOut.model_validate(order, from_attributes=True)


@router.patch("/{order_id}/accept", response_model=ChangeOrderOut)
def accept_change_order(session_id: int, order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_session(db, session_id, user)
    order = db.get(ChangeOrder, order_id)
    if order is None or order.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change order not found")
    order.status = "accepted"
    order.accepted_at = utcnow()
    # Grant the round
    if not order.round_granted:
        session = db.get(ReviewSession, session_id)
        if session:
            session.change_rounds_granted += 1
        order.round_granted = True
    db.commit()
    return ChangeOrderOut.model_validate(order, from_attributes=True)


@router.patch("/{order_id}/decline", response_model=ChangeOrderOut)
def decline_change_order(session_id: int, order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_session(db, session_id, user)
    order = db.get(ChangeOrder, order_id)
    if order is None or order.session_id != session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change order not found")
    order.status = "declined"
    order.declined_at = utcnow()
    db.commit()
    return ChangeOrderOut.model_validate(order, from_attributes=True)
