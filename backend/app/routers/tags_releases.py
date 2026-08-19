"""Tags & Releases — Git-style versioning for music projects."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Commit, GitTag, Project, ReleaseNote, User, utcnow
from ..schemas import (
    ReleaseNoteCreate,
    ReleaseNoteOut,
    TagCreate,
    TagOut,
    UserOut,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/projects/{project_id}/tags", tags=["tags"])


def _get_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _tag_out(db: Session, tag: GitTag) -> TagOut:
    creator = db.get(User, tag.created_by)
    return TagOut(
        id=tag.id, project_id=tag.project_id, name=tag.name, message=tag.message,
        commit_id=tag.commit_id, is_release=tag.is_release,
        creator=UserOut.model_validate(creator, from_attributes=True) if creator else UserOut(id=0, username="deleted", created_at=tag.created_at),
        created_at=tag.created_at,
    )


@router.get("", response_model=list[TagOut])
def list_tags(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    tags = db.scalars(select(GitTag).where(GitTag.project_id == project_id).order_by(GitTag.created_at.desc())).all()
    return [_tag_out(db, t) for t in tags]


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(project_id: int, payload: TagCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    existing = db.scalar(select(GitTag).where(GitTag.project_id == project_id, GitTag.name == payload.name))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tag already exists")
    commit = db.get(Commit, payload.commit_id)
    if commit is None or commit.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commit not found")
    tag = GitTag(project_id=project_id, commit_id=payload.commit_id, name=payload.name, message=payload.message, created_by=user.id, is_release=payload.is_release)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return _tag_out(db, tag)


@router.get("/{tag_name}", response_model=TagOut)
def get_tag(project_id: int, tag_name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    tag = db.scalar(select(GitTag).where(GitTag.project_id == project_id, GitTag.name == tag_name))
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    return _tag_out(db, tag)


@router.delete("/{tag_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(project_id: int, tag_name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    tag = db.scalar(select(GitTag).where(GitTag.project_id == project_id, GitTag.name == tag_name))
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    db.delete(tag)
    db.commit()


# ── Release Notes ──

@router.get("/{tag_name}/release-notes", response_model=ReleaseNoteOut | None)
def get_release_notes(project_id: int, tag_name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    tag = db.scalar(select(GitTag).where(GitTag.project_id == project_id, GitTag.name == tag_name))
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    note = db.scalar(select(ReleaseNote).where(ReleaseNote.tag_id == tag.id))
    if note is None:
        return None
    return ReleaseNoteOut(
        id=note.id, tag=_tag_out(db, tag), title=note.title, body=note.body,
        highlights=note.highlights, created_at=note.created_at,
    )


@router.post("/{tag_name}/release-notes", response_model=ReleaseNoteOut, status_code=status.HTTP_201_CREATED)
def create_release_notes(project_id: int, tag_name: str, payload: ReleaseNoteCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    tag = db.scalar(select(GitTag).where(GitTag.project_id == project_id, GitTag.name == tag_name))
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    note = ReleaseNote(tag_id=tag.id, title=payload.title, body=payload.body, highlights=payload.highlights)
    db.add(note)
    tag.is_release = True
    db.commit()
    db.refresh(note)
    return ReleaseNoteOut(id=note.id, tag=_tag_out(db, tag), title=note.title, body=note.body, highlights=note.highlights, created_at=note.created_at)
