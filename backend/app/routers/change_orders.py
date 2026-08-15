"""Change orders — late changes after the project was approved / delivered.

The classic freelancer pain: "we came back after three months, fix it for
free". A change order makes the late request explicit and priceable:

    client requests a change
    → engineer quotes: courtesy / paid revision round / new mastering pass
    → client accepts price + deadline
    → invoice paid (Stripe webhook or manual mark)
    → the revision round reopens (Round N) and a new version can be shipped.

Every step lands in the decision ledger (`change_order.created` /
`.quoted` / `.accepted` / `.declined` / `.paid` / `.round_opened`), so the
"new job, not a revision" boundary is auditable end to end.
"""

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ChangeOrder, ReviewSession, utcnow
from ..schemas import ChangeOrderCreate, ChangeOrderOut, ChangeOrderQuote, CheckoutOut
from ..security import get_current_user
from ..services import ledger, stripe_pay

router = APIRouter(prefix="/api/sessions", tags=["change orders"])

ACTIVE = ("requested", "quoted", "accepted")


def _co_out(co: ChangeOrder) -> ChangeOrderOut:
    return ChangeOrderOut(
        id=co.id,
        session_id=co.session_id,
        created_by=co.created_by,
        reason=co.reason,
        description=co.description,
        status=co.status,
        decision=co.decision,
        price_cents=co.price_cents,
        currency=co.currency or "usd",
        deadline_at=co.deadline_at,
        target_round=co.target_round,
        round_granted=co.round_granted,
        quoted_at=co.quoted_at,
        accepted_at=co.accepted_at,
        paid_at=co.paid_at,
        declined_at=co.declined_at,
        created_at=co.created_at,
    )


def grant_change_order_round(db: Session, co_id: int, actor: str = "stripe") -> bool:
    """Credit the accepted change order's round to the session and reopen it.

    Idempotent: a replayed webhook can never grant the same round twice.
    """
    co = db.get(ChangeOrder, co_id)
    if co is None or co.round_granted:
        return False
    session = co.session
    co.round_granted = True
    co.status = "paid"
    co.paid_at = co.paid_at or utcnow()
    session.change_rounds_granted = (session.change_rounds_granted or 0) + 1
    session.rounds_open = True
    session.status = "in_review"
    session.updated_at = utcnow()
    ledger.append(
        db,
        "change_order.paid",
        session_id=session.id,
        actor=actor,
        entity_type="change_order",
        entity_id=co.id,
        payload={
            "reason": co.reason,
            "decision": co.decision,
            "price_cents": co.price_cents,
            "target_round": co.target_round,
        },
    )
    ledger.append(
        db,
        "change_order.round_opened",
        session_id=session.id,
        actor=actor,
        entity_type="round",
        entity_id=session.id,
        payload={"round": co.target_round, "reason": co.reason},
    )
    return True


def _default_price(session: ReviewSession, decision: str, reason: str) -> int | None:
    """Fall back to the service preset's fees when the engineer doesn't quote."""
    if decision == "courtesy":
        return 0
    if decision == "new_mastering_pass":
        return session.recall_fee_cents
    if reason == "mastering_recall":
        return session.recall_fee_cents or session.revision_fee_cents
    return session.revision_fee_cents


def _co_checkout(co: ChangeOrder, success_url: str, cancel_url: str, db: Session) -> CheckoutOut:
    if not stripe_pay.enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Stripe is not configured — set STRIPE_SECRET_KEY or use the manual 'mark paid' flow",
        )
    if co.status != "accepted":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Client must accept the quote before paying")
    if co.round_granted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This change order was already granted")
    amount = co.price_cents or 0
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to charge — this change is a courtesy")
    try:
        session_id, url = stripe_pay.create_checkout_session(
            amount_cents=amount,
            currency=co.currency or "usd",
            package_id=0,
            package_name=f"{co.session.name} — change order ({co.reason.replace('_', ' ')})",
            session_id=co.session_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"kind": "change_order", "change_order_id": str(co.id)},
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    ledger.append(
        db,
        "invoice.checkout_created",
        session_id=co.session_id,
        actor="owner",
        entity_type="change_order",
        entity_id=co.id,
        payload={"kind": "change_order", "stripe_session": session_id, "amount_cents": amount},
    )
    db.commit()
    return CheckoutOut(
        checkout_url=url,
        session_id=session_id,
        amount_due_cents=amount,
        currency=co.currency or "usd",
    )


# ---------- client side (public share link) ----------


@router.post("/public/{share_token}/change-orders", response_model=ChangeOrderOut, status_code=status.HTTP_201_CREATED)
def client_request_change(
    share_token: str,
    payload: ChangeOrderCreate,
    actor: str = "",
    password: str | None = None,
    db: Session = Depends(get_db),
):
    from .sessions import _require_share_permission, get_public_session

    session = get_public_session(db, share_token)
    _require_share_permission(session, "comment", actor, password)
    if session.status != "approved":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Change orders are for approved projects — approve the final version first",
        )
    active = db.scalars(
        select(ChangeOrder).where(
            ChangeOrder.session_id == session.id,
            ChangeOrder.status.in_(ACTIVE),
        )
    ).all()
    if active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "There is already an open change request for this project — wait for the engineer's quote",
        )
    co = ChangeOrder(
        session_id=session.id,
        created_by=actor.strip()[:128] or "Client",
        reason=payload.reason,
        description=payload.description.strip(),
        target_round=session.round_number,
    )
    db.add(co)
    db.flush()
    ledger.append(
        db,
        "change_order.created",
        session_id=session.id,
        actor=co.created_by,
        entity_type="change_order",
        entity_id=co.id,
        payload={"reason": co.reason, "description": co.description.strip()[:200], "target_round": co.target_round},
    )
    session.updated_at = utcnow()
    db.commit()
    db.refresh(co)
    return _co_out(co)


@router.get("/public/{share_token}/change-orders", response_model=list[ChangeOrderOut])
def client_list_change_orders(
    share_token: str,
    actor: str = "",
    password: str | None = None,
    db: Session = Depends(get_db),
):
    from .sessions import _check_share_access, get_public_session

    session = get_public_session(db, share_token)
    _check_share_access(session, actor, password)
    rows = db.scalars(
        select(ChangeOrder).where(ChangeOrder.session_id == session.id).order_by(ChangeOrder.created_at.desc())
    ).all()
    return [_co_out(co) for co in rows]


@router.post("/public/{share_token}/change-orders/{co_id}/accept", response_model=ChangeOrderOut)
def client_accept_quote(
    share_token: str,
    co_id: int,
    actor: str = "",
    password: str | None = None,
    db: Session = Depends(get_db),
):
    from .sessions import _check_share_access, get_public_session

    session = get_public_session(db, share_token)
    _check_share_access(session, actor, password)
    co = db.get(ChangeOrder, co_id)
    if co is None or co.session_id != session.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change order not found")
    if co.status != "quoted":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot accept a '{co.status}' change order")
    co.status = "accepted"
    co.accepted_at = utcnow()
    session.updated_at = utcnow()
    ledger.append(
        db,
        "change_order.accepted",
        session_id=session.id,
        actor=actor.strip()[:128] or "Client",
        entity_type="change_order",
        entity_id=co.id,
        payload={
            "decision": co.decision,
            "price_cents": co.price_cents,
            "deadline": co.deadline_at.isoformat() if co.deadline_at else "",
        },
    )
    # Courtesy change: no invoice — the round reopens immediately on accept.
    if not (co.price_cents and co.price_cents > 0):
        grant_change_order_round(db, co.id, actor=actor.strip()[:128] or "Client")
    db.commit()
    db.refresh(co)
    return _co_out(co)


@router.post("/public/{share_token}/change-orders/{co_id}/checkout", response_model=CheckoutOut)
def client_change_order_checkout(
    share_token: str,
    co_id: int,
    success_url: str = Form(""),
    cancel_url: str = Form(""),
    db: Session = Depends(get_db),
):
    from .sessions import get_public_session

    session = get_public_session(db, share_token)
    co = db.get(ChangeOrder, co_id)
    if co is None or co.session_id != session.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change order not found")
    origin = success_url or f"http://localhost:5173/r/{share_token}?paid=1"
    return _co_checkout(
        co,
        success_url=origin,
        cancel_url=cancel_url or f"http://localhost:5173/r/{share_token}",
        db=db,
    )


# ---------- engineer side (owner) ----------


@router.get("/{session_id}/change-orders", response_model=list[ChangeOrderOut])
def owner_list_change_orders(
    session_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from .sessions import get_session_or_404

    get_session_or_404(db, user, session_id)
    rows = db.scalars(
        select(ChangeOrder).where(ChangeOrder.session_id == session_id).order_by(ChangeOrder.created_at.desc())
    ).all()
    return [_co_out(co) for co in rows]


def _owner_change_order(db: Session, session_id: int, co_id: int, user) -> ChangeOrder:
    from .sessions import get_session_or_404

    session = get_session_or_404(db, user, session_id)
    co = db.get(ChangeOrder, co_id)
    if co is None or co.session_id != session.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change order not found")
    return co


@router.patch("/{session_id}/change-orders/{co_id}", response_model=ChangeOrderOut)
def owner_quote_change_order(
    session_id: int,
    co_id: int,
    payload: ChangeOrderQuote,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    co = _owner_change_order(db, session_id, co_id, user)
    if co.status != "requested":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot quote a '{co.status}' change order")
    session = co.session
    price = payload.price_cents
    if price is None:
        price = _default_price(session, payload.decision, co.reason)
    if payload.decision == "courtesy":
        price = 0
    if price is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Set a price for this change (or add a revision/recall fee to the service preset)",
        )
    co.decision = payload.decision
    co.price_cents = price
    if payload.deadline_at is not None:
        co.deadline_at = payload.deadline_at
    co.status = "quoted"
    co.quoted_at = utcnow()
    session.updated_at = utcnow()
    ledger.append(
        db,
        "change_order.quoted",
        session_id=session.id,
        actor=user.username,
        entity_type="change_order",
        entity_id=co.id,
        payload={"decision": payload.decision, "price_cents": price, "reason": co.reason},
    )
    db.commit()
    db.refresh(co)
    return _co_out(co)


@router.post("/{session_id}/change-orders/{co_id}/decline", response_model=ChangeOrderOut)
def owner_decline_change_order(
    session_id: int,
    co_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    co = _owner_change_order(db, session_id, co_id, user)
    if co.status not in ("requested", "quoted"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot decline a '{co.status}' change order")
    co.status = "declined"
    co.declined_at = utcnow()
    co.session.updated_at = utcnow()
    ledger.append(
        db,
        "change_order.declined",
        session_id=session_id,
        actor=user.username,
        entity_type="change_order",
        entity_id=co.id,
        payload={"reason": co.reason, "description": co.description.strip()[:200]},
    )
    db.commit()
    db.refresh(co)
    return _co_out(co)


@router.post("/{session_id}/change-orders/{co_id}/mark-paid", response_model=ChangeOrderOut)
def owner_mark_change_order_paid(
    session_id: int,
    co_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manual 'paid' for Stripe-less mode — grants the round like the webhook."""
    co = _owner_change_order(db, session_id, co_id, user)
    if co.status != "accepted":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Client must accept the quote before payment")
    granted = grant_change_order_round(db, co.id, actor=user.username)
    if not granted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This change order was already granted")
    db.commit()
    db.refresh(co)
    return _co_out(co)


@router.post("/{session_id}/change-orders/{co_id}/checkout", response_model=CheckoutOut)
def owner_change_order_checkout(
    session_id: int,
    co_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    co = _owner_change_order(db, session_id, co_id, user)
    origin = "http://localhost:5173"
    return _co_checkout(
        co,
        success_url=f"{origin}/sessions?paid=1",
        cancel_url=f"{origin}/sessions",
        db=db,
    )
