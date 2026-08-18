"""Reminders router — evaluate and send pending."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user
from ..services import reminders as reminders_svc

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.post("/evaluate")
def evaluate_reminders(user=Depends(get_current_user), db: Session = Depends(get_db)):
    result = reminders_svc.evaluate(db)
    return result


@router.post("/send")
def send_reminders(user=Depends(get_current_user), db: Session = Depends(get_db)):
    result = reminders_svc.send_pending(db)
    return result


@router.post("/run-all")
def run_all_reminders(user=Depends(get_current_user), db: Session = Depends(get_db)):
    result = reminders_svc.run_all(db)
    return result
