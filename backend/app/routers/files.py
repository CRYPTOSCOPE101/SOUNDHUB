"""File upload and download router."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_SIZE
from ..database import get_db
from ..security import get_current_user
from ..services import storage

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload")
def upload_file(file: UploadFile = ..., user=Depends(get_current_user)):
    try:
        data = storage.put_upload_file(file, MAX_UPLOAD_SIZE)
    except ValueError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))
    sha = storage.put_blob(data)
    return {"sha": sha, "size": len(data), "filename": file.filename}


@router.get("/{sha}")
def download_file(sha: str, user=Depends(get_current_user)):
    try:
        data = storage.read_blob(sha)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return Response(content=data, media_type="application/octet-stream")
