"""Music Tasks — GitHub Issues for music production."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import KanbanBoard, KanbanColumn, KanbanCard, MusicTask, Project, TaskComment, TaskLabel, User, utcnow
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


def _get_project_and_verify_access(db: Session, project_id: int, user: User) -> Project:
    """Get project and verify user has access."""
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _get_or_create_default_board(db: Session, project_id: int) -> KanbanBoard:
    """Get the default kanban board for a project or create one if it doesn't exist."""
    board = db.scalar(select(KanbanBoard).where(KanbanBoard.project_id == project_id))
    if board is None:
        # Create default board with standard columns
        board = KanbanBoard(project_id=project_id, name="Release Board")
        db.add(board)
        db.flush()

        # Add default columns
        default_columns = ["Backlog", "In Progress", "Review", "Approved", "Mastered", "Released"]
        for i, col_name in enumerate(default_columns):
            db.add(KanbanColumn(board_id=board.id, name=col_name, position=i))

        db.commit()
        db.refresh(board)

    return board


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
    project_id: int,
    payload: MusicTaskCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    create_kanban_card: bool = Query(True, description="Whether to automatically create a kanban card for this task"),
    board_id: int | None = Query(None, description="Optional board ID to place the task on (uses default board if not specified)"),
    column_name: str | None = Query(None, description="Optional column name to place the task in (uses first column if not specified)")
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

    # Optionally create a kanban card for this task
    if create_kanban_card:
        # Determine which board to use
        if board_id is not None:
            board = db.get(KanbanBoard, board_id)
            if board is None or board.project_id != project_id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Board not found")
        else:
            board = _get_or_create_default_board(db, project_id)

        # Determine which column to use
        if column_name is not None:
            column = db.scalar(select(KanbanColumn).where(
                KanbanColumn.board_id == board.id,
                KanbanColumn.name == column_name
            ))
            if column is None:
                # If column doesn't exist, use the first column
                column = db.scalar(select(KanbanColumn).where(
                    KanbanColumn.board_id == board.id
                ).order_by(KanbanColumn.position).limit(1))
        else:
            # Use the first column (typically "Backlog")
            column = db.scalar(select(KanbanColumn).where(
                KanbanColumn.board_id == board.id
            ).order_by(KanbanColumn.position).limit(1))

        if column is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "No columns found on board")

        # Create kanban card for the task
        pos = db.scalar(select(KanbanCard.position).where(KanbanCard.column_id == column.id).order_by(KanbanCard.position.desc()).limit(1)) or 0
        card = KanbanCard(
            column_id=column.id,
            task_id=task.id,
            position=pos,
            title=task.title,
            description=task.body
        )
        db.add(card)

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


# Enhanced work management endpoints (Azure Boards analog)

@router.get("/board/{board_id}/tasks", response_model=list[MusicTaskOut])
def get_tasks_on_board(
    project_id: int,
    board_id: int,
    column_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all tasks on a specific kanban board, optionally filtered by column."""
    _get_project(db, project_id, user)

    # Verify board belongs to project
    board = db.get(KanbanBoard, board_id)
    if board is None or board.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Board not found")

    # Query tasks through kanban cards
    query = select(MusicTask).join(
        KanbanCard, MusicTask.id == KanbanCard.task_id
    ).where(
        KanbanCard.column_id.in_(
            select(KanbanColumn.id).where(KanbanColumn.board_id == board_id)
        )
    )

    if column_id is not None:
        # Verify column belongs to board
        column = db.get(KanbanColumn, column_id)
        if column is None or column.board_id != board_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Column not found")
        query = query.where(KanbanCard.column_id == column_id)

    tasks = db.scalars(query.options(joinedload(MusicTask.author))).all()
    return [_task_out(db, t) for t in tasks]


@router.post("/{task_id}/move/{column_id}", response_model=MusicTaskOut)
def move_task_to_column(
    project_id: int,
    task_id: int,
    column_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Move a task to a specific column on its kanban board."""
    _get_project(db, project_id, user)

    # Get task and verify it belongs to project
    task = db.get(MusicTask, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")

    # Get column and verify it belongs to project
    column = db.get(KanbanColumn, column_id)
    if column is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Column not found")

    # Verify column belongs to a board in this project
    board = db.get(KanbanBoard, column.board_id)
    if board is None or board.project_id != project_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Column does not belong to a board in this project")

    # Find or create kanban card for this task
    card = db.scalar(select(KanbanCard).where(KanbanCard.task_id == task_id))

    if card is None:
        # Create a new kanban card for this task in the target column
        # Get position at the end of the column
        pos = db.scalar(select(KanbanCard.position).where(KanbanCard.column_id == column_id).order_by(KanbanCard.position.desc()).limit(1)) or 0
        card = KanbanCard(
            column_id=column_id,
            task_id=task_id,
            position=pos,
            title=task.title,
            description=task.body
        )
        db.add(card)
    else:
        # Move existing card to new column
        # Get position at the end of the target column
        pos = db.scalar(select(KanbanCard.position).where(KanbanCard.column_id == column_id).order_by(KanbanCard.position.desc()).limit(1)) or 0
        card.column_id = column_id
        card.position = pos

    db.commit()
    db.refresh(task)
    return _task_out(db, task)
