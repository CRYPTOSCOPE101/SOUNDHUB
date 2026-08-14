from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Commit, Project, User
from ..schemas import DiffOut
from ..services import storage, versioning
from ..services.daw.diff_engine import normalize_content, summary_diff, unified_diff
from ..services.daw.registry import detect_format, get_daw_info
from ..security import get_current_user
from .projects import get_project_or_404

router = APIRouter(prefix="/api/projects", tags=["diffs"])


@router.get("/{project_id}/diff", response_model=DiffOut)
def get_diff(
    project_id: int,
    path: str = Query(...),
    from_commit: int | None = None,
    to_commit: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        commit_b = versioning.get_commit(db, project, to_commit)
        if from_commit is not None:
            commit_a = versioning.get_commit(db, project, from_commit)
        elif commit_b.parent_id is not None:
            commit_a = db.get(Commit, commit_b.parent_id)
        else:
            commit_a = commit_b  # root commit: nothing to compare against
    except LookupError:
        raise HTTPException(404, "Commit not found")

    snap_a = versioning.file_in_commit(db, commit_a, path)
    snap_b = versioning.file_in_commit(db, commit_b, path)

    data_a = storage.read_blob(snap_a.blob_sha) if snap_a else b""
    data_b = storage.read_blob(snap_b.blob_sha) if snap_b else b""

    fmt = detect_format(path, data_b or data_a)
    info_a = get_daw_info(path, data_a) if data_a else None
    info_b = get_daw_info(path, data_b) if data_b else None

    summary = summary_diff(info_a, info_b)

    text_a = normalize_content(path, data_a) if data_a else ""
    text_b = normalize_content(path, data_b) if data_b else ""
    raw, truncated = unified_diff(text_a, text_b)

    return DiffOut(
        path=path,
        format=fmt,
        summary=summary,
        raw=raw,
        binary=fmt == "flp" or (data_a or data_b)[:1] in (b"\xf4", b"\xf5"),
        truncated=truncated,
    )
