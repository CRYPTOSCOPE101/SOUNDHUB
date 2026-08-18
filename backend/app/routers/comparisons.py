"""Version and reference A/B comparisons."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReferenceComparison, ReviewSession, VersionComparison
from ..schemas import ReferenceComparisonCreate, ReferenceComparisonOut, VersionComparisonCreate, VersionComparisonOut
from ..security import get_current_user

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])


@router.post("/versions", response_model=VersionComparisonOut, status_code=status.HTTP_201_CREATED)
def create_version_comparison(payload: VersionComparisonCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    comparison = VersionComparison(
        session_id=0,  # will be set from version
        base_version_id=payload.base_version_id,
        compare_version_id=payload.compare_version_id,
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
        level_match=payload.level_match,
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return VersionComparisonOut.model_validate(comparison, from_attributes=True)


@router.post("/references", response_model=ReferenceComparisonOut, status_code=status.HTTP_201_CREATED)
def create_reference_comparison(payload: ReferenceComparisonCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    comparison = ReferenceComparison(
        session_id=0,
        version_id=payload.version_id,
        reference_id=payload.reference_id,
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
        level_match=payload.level_match,
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return ReferenceComparisonOut.model_validate(comparison, from_attributes=True)
