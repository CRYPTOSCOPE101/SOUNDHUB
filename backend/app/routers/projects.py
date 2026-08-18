"""Projects router — CRUD, commits, branches."""
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import project_or_404
from ..database import get_db
from ..models import Branch, Commit, FileSnapshot, Project, User, utcnow
from ..schemas import BranchCreate, BranchOut, CommitCreate, CommitOut, ProjectCreate, ProjectOut, ProjectUpdate
from ..security import get_current_user
from ..services import storage, versioning

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:160]


@router.get("", response_model=list[ProjectOut])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc())
    ).all()
    return [ProjectOut.model_validate(p, from_attributes=True) for p in projects]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    slug = _slugify(payload.name)
    existing = db.scalar(
        select(Project).where(Project.owner_id == user.id, Project.slug == slug)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A project with this name already exists")
    project = Project(owner_id=user.id, name=payload.name.strip(), slug=slug, description=payload.description)
    db.add(project)
    db.flush()
    branch = Branch(project_id=project.id, name="main")
    db.add(branch)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project, from_attributes=True)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_or_404(db, project_id, user)
    return ProjectOut.model_validate(project, from_attributes=True)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_or_404(db, project_id, user)
    if payload.name is not None:
        project.name = payload.name.strip()
        project.slug = _slugify(payload.name)
    if payload.description is not None:
        project.description = payload.description
    project.updated_at = utcnow()
    db.commit()
    return ProjectOut.model_validate(project, from_attributes=True)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_or_404(db, project_id, user)
    db.delete(project)
    db.commit()


@router.get("/{project_id}/branches", response_model=list[BranchOut])
def list_branches(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project_or_404(db, project_id, user)
    branches = db.scalars(
        select(Branch).where(Branch.project_id == project_id)
    ).all()
    return [
        BranchOut(
            name=b.name,
            is_default=b.is_default,
            head_commit_id=b.head_commit_id,
            created_at=b.created_at,
        )
        for b in branches
    ]


@router.post("/{project_id}/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
def create_branch(project_id: int, payload: BranchCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project_or_404(db, project_id, user)
    existing = db.scalar(
        select(Branch).where(Branch.project_id == project_id, Branch.name == payload.name)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Branch already exists")
    branch = Branch(project_id=project_id, name=payload.name)
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return BranchOut(name=branch.name, is_default=branch.is_default, created_at=branch.created_at)


@router.post("/{project_id}/commits", response_model=CommitOut, status_code=status.HTTP_201_CREATED)
def create_commit(project_id: int, payload: CommitCreate, files: list[dict] = [], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = project_or_404(db, project_id, user)

    branch = db.scalar(
        select(Branch).where(Branch.project_id == project_id, Branch.name == payload.branch)
    )
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Branch '{payload.branch}' not found")

    commit = Commit(
        project_id=project_id,
        author_id=user.id,
        parent_id=branch.head_commit_id,
        message=payload.message,
    )
    db.add(commit)
    db.flush()

    for f in files:
        snap = FileSnapshot(commit_id=commit.id, path=f["path"], blob_sha=f["blob_sha"], size=f.get("size", 0))
        db.add(snap)

    branch.head_commit_id = commit.id
    project.updated_at = utcnow()
    db.commit()
    db.refresh(commit)
    return CommitOut.model_validate(commit, from_attributes=True)
