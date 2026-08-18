"""Assets router — stems and audio assets."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_SIZE
from ..database import get_db
from ..models import ReviewSession, ReviewVersion, StemAsset
from ..security import get_current_user
from ..services import storage

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("/stems")
def upload_stem(version_id: int = ..., logical_name: str = ..., display_name: str = ..., file: UploadFile = ..., user=Depends(get_current_user), db: Session = Depends(get_db)):
    version = db.get(ReviewVersion, version_id)
    session = db.get(ReviewSession, version.session_id) if version else None
    if version is None or session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    try:
        data = storage.put_upload_file(file, MAX_UPLOAD_SIZE)
    except ValueError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))
    sha = storage.put_blob(data)
    stem = StemAsset(
        version_id=version_id,
        logical_name=logical_name,
        display_name=display_name,
        blob_sha=sha,
        size=len(data),
    )
    db.add(stem)
    db.commit()
    return {"id": stem.id, "blob_sha": sha}
