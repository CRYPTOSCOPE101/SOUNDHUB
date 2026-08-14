import unicodedata
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_SIZE
from ..database import get_db
from ..models import Commit, FileSnapshot, Project, User
from ..schemas import (
    BranchCreate,
    BranchOut,
    CommitDetailOut,
    CommitOut,
    FileOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    ReleaseIn,
    TreeOut,
)
from ..services import storage, versioning
from ..services.daw import is_daw_path
from ..services.daw.registry import get_daw_info
from ..security import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])

# simple in-memory cache: blob_sha -> daw dict
_daw_cache: dict[str, dict] = {}
DAW_ANALYZE_MAX = 200 * 1024 * 1024  # don't decompress huge files for listing


def get_project_or_404(db: Session, user: User, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def sanitize_path(name: str) -> str:
    name = name.replace("\\", "/")
    parts = [p for p in name.split("/") if p not in ("", ".", "..")]
    return "/".join(parts) or "unnamed"


def slugify(name: str) -> str:
    norm = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in norm.lower())
    slug = "-".join(s for s in slug.split("-") if s)
    return slug[:80] or "project"


def unique_slug(db: Session, owner_id: int, name: str) -> str:
    base = slugify(name)
    slug = base
    n = 2
    while db.scalar(select(Project).where(Project.owner_id == owner_id, Project.slug == slug)):
        slug = f"{base}-{n}"
        n += 1
    return slug


def _commit_out(db: Session, commit: Commit) -> CommitOut:
    files = db.query(FileSnapshot).filter(FileSnapshot.commit_id == commit.id).all()
    return CommitOut(
        id=commit.id,
        message=commit.message,
        created_at=commit.created_at,
        parent_id=commit.parent_id,
        author=commit.author,
        file_count=len(files),
        total_size=sum(f.size for f in files),
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc())
    ).all()


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = Project(
        owner_id=user.id,
        name=payload.name.strip(),
        slug=unique_slug(db, user.id, payload.name),
        description=payload.description.strip(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_project_or_404(db, user, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    if payload.name is not None and payload.name.strip() != project.name:
        project.name = payload.name.strip()
        project.slug = unique_slug(db, user.id, project.name)
    if payload.description is not None:
        project.description = payload.description.strip()
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    db.delete(project)
    db.commit()


@router.get("/{project_id}/branches", response_model=list[BranchOut])
def list_branches(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    return versioning.list_branches(db, project)


@router.post("/{project_id}/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
def create_branch(
    project_id: int,
    payload: BranchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        row = versioning.create_branch(db, project, payload.name.strip(), payload.from_branch)
    except LookupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    head = db.get(Commit, row.head_commit_id) if row.head_commit_id else None
    return BranchOut(
        name=row.name,
        is_default=row.name == project.default_branch,
        head_commit_id=row.head_commit_id,
        head_message=head.message if head else "",
        head_sha=f"{head.id:08x}"[:7] if head else None,
        head_author=head.author.username if head and head.author else "",
        head_date=head.created_at if head else None,
        commit_count=len(versioning.iter_commits(db, project, row.name)),
        created_at=row.created_at,
    )


@router.delete("/{project_id}/branches/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(
    project_id: int,
    name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        deleted = versioning.delete_branch(db, project, name)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Branch not found")


@router.get("/{project_id}/tree", response_model=TreeOut)
def get_tree(
    project_id: int,
    commit_id: int | None = None,
    branch: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        commit = versioning.get_commit(db, project, commit_id, branch)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commit not found")
    snapshots = versioning.tree_files(db, commit)
    files: list[FileOut] = []
    for snap in sorted(snapshots, key=lambda s: s.path):
        ext = PurePosixPath(snap.path).suffix.lower()
        daw_format = ext.lstrip(".") if is_daw_path(snap.path) else None
        daw_info: dict | None = None
        if daw_format and snap.size <= DAW_ANALYZE_MAX:
            daw_info = _analyze_cached(snap)
        files.append(
            FileOut(
                path=snap.path,
                size=snap.size,
                blob_sha=snap.blob_sha,
                kind="file",
                daw_format=daw_format,
                daw_info=daw_info,
            )
        )
    return TreeOut(
        commit_id=commit.id, commit_message=commit.message, files=files
    )


def _analyze_cached(snap: FileSnapshot) -> dict | None:
    if snap.blob_sha in _daw_cache:
        return _daw_cache[snap.blob_sha]
    try:
        data = storage.read_blob(snap.blob_sha)
        info = get_daw_info(snap.path, data)
    except Exception:  # noqa: BLE001
        info = None
    result = info.to_dict() if info else None
    _daw_cache[snap.blob_sha] = result
    return result


@router.get("/{project_id}/commits", response_model=list[CommitOut])
def list_commits(
    project_id: int,
    branch: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    commits = versioning.iter_commits(db, project, branch)
    return [_commit_out(db, c) for c in commits]


@router.get("/{project_id}/commits/{commit_id}", response_model=CommitDetailOut)
def get_commit(
    project_id: int,
    commit_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        commit = versioning.get_commit(db, project, commit_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commit not found")
    snapshots = versioning.tree_files(db, commit)
    out = CommitDetailOut(
        id=commit.id,
        message=commit.message,
        created_at=commit.created_at,
        parent_id=commit.parent_id,
        author=commit.author,
        file_count=len(snapshots),
        total_size=sum(s.size for s in snapshots),
        files=[
            FileOut(
                path=s.path,
                size=s.size,
                blob_sha=s.blob_sha,
                kind="file",
                daw_format=PurePosixPath(s.path).suffix.lstrip(".") or None,
            )
            for s in sorted(snapshots, key=lambda x: x.path)
        ],
    )
    return out


@router.post("/{project_id}/release", response_model=ProjectOut)
def bind_release(
    project_id: int,
    payload: ReleaseIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bind an on-chain SoundHubRelease NFT to this project."""
    project = get_project_or_404(db, user, project_id)
    project.release_token_id = payload.token_id
    project.release_contract = payload.contract_address
    project.release_name = payload.name
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}/release", response_model=ProjectOut)
def unbind_release(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    project.release_token_id = None
    project.release_contract = None
    project.release_name = None
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/commits", response_model=CommitOut, status_code=status.HTTP_201_CREATED)
def create_commit(
    project_id: int,
    message: str = Form(""),
    branch: str = Form("main"),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    tree: dict[str, bytes] = {}
    for f in files:
        path = sanitize_path(f.filename or "")
        try:
            data = storage.put_upload_file(f, MAX_UPLOAD_SIZE)
        except ValueError as exc:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))
        if path in tree:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Duplicate path: {path}")
        tree[path] = data
    commit = versioning.create_commit(db, project, user, message.strip(), tree, branch=branch.strip() or "main")
    return _commit_out(db, commit)
