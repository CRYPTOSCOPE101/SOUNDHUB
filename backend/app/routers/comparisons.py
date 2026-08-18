"""Version and reference A/B comparisons."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ReferenceComparison, ReferenceTrack, ReviewSession, ReviewVersion, VersionComparison
from ..schemas import ReferenceComparisonCreate, ReferenceComparisonOut, VersionComparisonCreate, VersionComparisonOut
from ..security import get_current_user

router = APIRouter(prefix="/api/comparisons", tags=["comparisons"])


def _own_version(db: Session, version_id: int, user) -> ReviewVersion:
    version = db.get(ReviewVersion, version_id)
    session = db.get(ReviewSession, version.session_id) if version else None
    if version is None or session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    return version


@router.post("/versions", response_model=VersionComparisonOut, status_code=status.HTTP_201_CREATED)
def create_version_comparison(payload: VersionComparisonCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    base = _own_version(db, payload.base_version_id, user)
    compare = _own_version(db, payload.compare_version_id, user)
    if base.session_id != compare.session_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Versions belong to different sessions")
    comparison = VersionComparison(
        session_id=base.session_id,
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
    version = _own_version(db, payload.version_id, user)
    reference = db.get(ReferenceTrack, payload.reference_id)
    if reference is None or reference.session_id != version.session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reference not found")
    comparison = ReferenceComparison(
        session_id=version.session_id,
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
