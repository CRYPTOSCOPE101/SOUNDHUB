"""Discussions — forum for music projects."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Discussion, DiscussionComment, Project, User, utcnow
from ..schemas import (
    DiscussionCommentCreate,
    DiscussionCommentOut,
    DiscussionCreate,
    DiscussionOut,
    DiscussionUpdate,
    UserOut,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/projects/{project_id}/discussions", tags=["discussions"])


def _get_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _disc_out(db: Session, d: Discussion) -> DiscussionOut:
    author = db.get(User, d.author_id)
    comment_count = len(db.scalars(select(DiscussionComment).where(DiscussionComment.discussion_id == d.id)).all())
    return DiscussionOut(
        id=d.id, project_id=d.project_id,
        author=UserOut.model_validate(author, from_attributes=True) if author else UserOut(id=0, username="deleted", created_at=d.created_at),
        title=d.title, body=d.body, category=d.category,
        pinned=d.pinned, locked=d.locked, comment_count=comment_count,
        created_at=d.created_at, updated_at=d.updated_at,
    )


@router.get("", response_model=list[DiscussionOut])
def list_discussions(
    project_id: int, category: str | None = Query(None),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    q = select(Discussion).where(Discussion.project_id == project_id)
    if category:
        q = q.where(Discussion.category == category)
    items = db.scalars(q.order_by(Discussion.pinned.desc(), Discussion.created_at.desc())).all()
    return [_disc_out(db, d) for d in items]


@router.post("", response_model=DiscussionOut, status_code=status.HTTP_201_CREATED)
def create_discussion(project_id: int, payload: DiscussionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    d = Discussion(project_id=project_id, author_id=user.id, title=payload.title, body=payload.body, category=payload.category)
    db.add(d)
    db.commit()
    db.refresh(d)
    return _disc_out(db, d)


@router.get("/{disc_id}", response_model=DiscussionOut)
def get_discussion(project_id: int, disc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    d = db.get(Discussion, disc_id)
    if d is None or d.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discussion not found")
    return _disc_out(db, d)


@router.patch("/{disc_id}", response_model=DiscussionOut)
def update_discussion(project_id: int, disc_id: int, payload: DiscussionUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    d = db.get(Discussion, disc_id)
    if d is None or d.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discussion not found")
    for field in ("title", "body", "category", "pinned", "locked"):
        val = getattr(payload, field)
        if val is not None:
            setattr(d, field, val)
    d.updated_at = utcnow()
    db.commit()
    return _disc_out(db, d)


@router.delete("/{disc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discussion(project_id: int, disc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    d = db.get(Discussion, disc_id)
    if d is None or d.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discussion not found")
    db.delete(d)
    db.commit()


@router.post("/{disc_id}/comments", response_model=DiscussionCommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(project_id: int, disc_id: int, payload: DiscussionCommentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    d = db.get(Discussion, disc_id)
    if d is None or d.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discussion not found")
    if d.locked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Discussion is locked")
    c = DiscussionComment(discussion_id=disc_id, author_id=user.id, author_name=user.username, body=payload.body)
    db.add(c)
    db.commit()
    db.refresh(c)
    return DiscussionCommentOut(id=c.id, author=UserOut.model_validate(user, from_attributes=True), author_name=user.username, body=c.body, is_answer=c.is_answer, created_at=c.created_at)


@router.get("/{disc_id}/comments", response_model=list[DiscussionCommentOut])
def list_comments(project_id: int, disc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    comments = db.scalars(select(DiscussionComment).where(DiscussionComment.discussion_id == disc_id)).all()
    return [DiscussionCommentOut(id=c.id, author=UserOut.model_validate(db.get(User, c.author_id), from_attributes=True) if c.author_id else None, author_name=c.author_name, body=c.body, is_answer=c.is_answer, created_at=c.created_at) for c in comments]


@router.patch("/{disc_id}/comments/{comment_id}/accept", response_model=DiscussionCommentOut)
def accept_answer(project_id: int, disc_id: int, comment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    c = db.get(DiscussionComment, comment_id)
    if c is None or c.discussion_id != disc_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    # Unmark previous answers
    prev = db.scalars(select(DiscussionComment).where(DiscussionComment.discussion_id == disc_id, DiscussionComment.is_answer == True)).all()
    for p in prev:
        p.is_answer = False
    c.is_answer = True
    d = db.get(Discussion, disc_id)
    if d:
        d.answer_id = comment_id
    db.commit()
    return DiscussionCommentOut(id=c.id, author=UserOut.model_validate(db.get(User, c.author_id), from_attributes=True) if c.author_id else None, author_name=c.author_name, body=c.body, is_answer=True, created_at=c.created_at)
