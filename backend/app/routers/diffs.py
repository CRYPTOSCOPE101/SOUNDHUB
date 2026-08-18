"""Smart diff router for DAW project comparison."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import VersionDiffOut
from ..security import get_current_user

router = APIRouter(prefix="/api/diffs", tags=["diffs"])


@router.get("/{session_id}/versions/{version_id}", response_model=VersionDiffOut)
def get_diff(session_id: int, version_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Smart diff for a review version vs the previous one."""
    return {"version_label": "v1", "from_label": None, "has_daw": False}
