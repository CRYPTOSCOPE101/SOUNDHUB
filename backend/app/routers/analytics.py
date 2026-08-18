"""Analytics router."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import AnalyticsOut
from ..security import get_current_user
from ..services import analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
def get_analytics(user=Depends(get_current_user), db: Session = Depends(get_db)):
    result = analytics.get_user_analytics(db, user.id)
    return AnalyticsOut(**result)
