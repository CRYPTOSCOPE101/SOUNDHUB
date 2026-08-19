"""Music Tasks — GitHub Issues for music production."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MusicTask, Project, TaskComment, TaskLabel, User, utcnow
from ..schemas import (
    MusicTaskCreate,
    MusicTaskOut,
    MusicTaskUpdate,
    TaskCommentCreate,
    TaskCommentOut,
    UserOut,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["tasks"])


def _get_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _task_out(db: Session, t: MusicTask) -> MusicTaskOut:
    author = db.get(User, t.author_id)
    assignee = db.get(User, t.assignee_id) if t.assignee_id else None
    labels = db.scalars(select(TaskLabel).where(TaskLabel.task_id == t.id)).all()
    comment_count = db.scalar(select(TaskComment.id).where(TaskComment.task_id == t.id).limit(1000)) or 0
    return MusicTaskOut(
        id=t.id, project_id=t.project_id,
        author=UserOut.model_validate(author, from_attributes=True) if author else UserOut(id=0, username="deleted", created_at=t.created_at),
        title=t.title, body=t.body, type=t.type, priority=t.priority, status=t.status,
        assignee=UserOut.model_validate(assignee, from_attributes=True) if assignee else None,
        milestone=t.milestone, due_date=t.due_date,
        labels=[l.name for l in labels], comment_count=comment_count,
        linked_pr_id=t.linked_pr_id, created_at=t.created_at, updated_at=t.updated_at,
    )


@router.get("", response_model=list[MusicTaskOut])
def list_tasks(
    project_id: int,
    status_filter: str | None = Query(None, alias="status"),
    type_filter: str | None = Query(None, alias="type"),
    priority: str | None = Query(None),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    q = select(MusicTask).where(MusicTask.project_id == project_id)
    if status_filter: q = q.where(MusicTask.status == status_filter)
    if type_filter: q = q.where(MusicTask.type == type_filter)
    if priority: q = q.where(MusicTask.priority == priority)
    tasks = db.scalars(q.order_by(MusicTask.created_at.desc())).all()
    return [_task_out(db, t) for t in tasks]


@router.post("", response_model=MusicTaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: int, payload: MusicTaskCreate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    task = MusicTask(
        project_id=project_id, author_id=user.id,
        title=payload.title, body=payload.body, type=payload.type,
        priority=payload.priority, assignee_id=payload.assignee_id,
        milestone=payload.milestone, due_date=payload.due_date,
    )
    db.add(task)
    db.flush()
    for name in payload.labels[:10]:
        db.add(TaskLabel(task_id=task.id, name=name))
    db.commit()
    db.refresh(task)
    return _task_out(db, task)


@router.get("/{task_id}", response_model=MusicTaskOut)
def get_task(project_id: int, task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    task = db.get(MusicTask, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return _task_out(db, task)


@router.patch("/{task_id}", response_model=MusicTaskOut)
def update_task(
    project_id: int, task_id: int, payload: MusicTaskUpdate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    task = db.get(MusicTask, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    for field in ("title", "body", "type", "priority", "status", "assignee_id", "milestone", "due_date"):
        val = getattr(payload, field)
        if val is not None:
            setattr(task, field, val)
    if payload.status in ("done", "closed"):
        task.closed_at = utcnow()
    task.updated_at = utcnow()
    db.commit()
    return _task_out(db, task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(project_id: int, task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    task = db.get(MusicTask, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    db.delete(task)
    db.commit()


@router.post("/{task_id}/comments", response_model=TaskCommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    project_id: int, task_id: int, payload: TaskCommentCreate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    task = db.get(MusicTask, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    comment = TaskComment(task_id=task_id, author_id=user.id, author_name=user.username, body=payload.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return TaskCommentOut(id=comment.id, author=UserOut.model_validate(user, from_attributes=True), author_name=user.username, body=comment.body, created_at=comment.created_at)


@router.get("/{task_id}/comments", response_model=list[TaskCommentOut])
def list_comments(project_id: int, task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    comments = db.scalars(select(TaskComment).where(TaskComment.task_id == task_id)).all()
    return [TaskCommentOut(id=c.id, author=UserOut.model_validate(db.get(User, c.author_id), from_attributes=True) if c.author_id else None, author_name=c.author_name, body=c.body, created_at=c.created_at) for c in comments]
