"""Assets router — stems and audio assets."""
from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import StemAsset
from ..security import get_current_user
from ..services import storage

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("/stems")
def upload_stem(version_id: int = ..., logical_name: str = ..., display_name: str = ..., file: UploadFile = ..., user=Depends(get_current_user), db: Session = Depends(get_db)):
    data = file.file.read()
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
