from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Project, User
from ..schemas import FileOut
from ..services import storage, versioning
from ..services.daw.registry import get_daw_info
from ..security import get_current_user
from .projects import get_project_or_404

router = APIRouter(prefix="/api/projects", tags=["files"])


@router.get("/{project_id}/files/{path:path}/info", response_model=FileOut)
def file_info(
    project_id: int,
    path: str,
    commit_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        commit = versioning.get_commit(db, project, commit_id)
    except LookupError:
        raise HTTPException(404, "Commit not found")
    snap = versioning.file_in_commit(db, commit, path)
    if snap is None:
        raise HTTPException(404, "File not found")
    data = storage.read_blob(snap.blob_sha)
    info = get_daw_info(path, data)
    return FileOut(
        path=snap.path,
        size=snap.size,
        blob_sha=snap.blob_sha,
        kind="file",
        daw_format=info.format_key if info else None,
        daw_info=info.to_dict() if info else None,
    )


@router.get("/{project_id}/files/{path:path}")
def download_file(
    project_id: int,
    path: str,
    commit_id: int | None = None,
    download: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        commit = versioning.get_commit(db, project, commit_id)
    except LookupError:
        raise HTTPException(404, "Commit not found")
    snap = versioning.file_in_commit(db, commit, path)
    if snap is None:
        raise HTTPException(404, "File not found")
    data = storage.read_blob(snap.blob_sha)
    headers = {"X-Blob-SHA": snap.blob_sha, "X-Size": str(snap.size)}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{path.rsplit("/", 1)[-1]}"'
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers=headers,
    )
