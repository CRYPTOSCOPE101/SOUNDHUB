"""Kanban Boards — project management for music releases."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import KanbanBoard, KanbanCard, KanbanColumn, Project, User, utcnow
from ..schemas import (
    KanbanBoardCreate,
    KanbanBoardOut,
    KanbanCardCreate,
    KanbanCardOut,
    KanbanCardUpdate,
    KanbanColumnOut,
    UserOut,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/projects/{project_id}/kanban", tags=["kanban"])


def _get_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _board_out(db: Session, board: KanbanBoard) -> KanbanBoardOut:
    columns = db.scalars(select(KanbanColumn).where(KanbanColumn.board_id == board.id).order_by(KanbanColumn.position)).all()
    col_outs = []
    for col in columns:
        cards = db.scalars(select(KanbanCard).where(KanbanCard.column_id == col.id).order_by(KanbanCard.position)).all()
        card_outs = []
        for card in cards:
            assignee = db.get(User, card.assignee_id) if card.assignee_id else None
            card_outs.append(KanbanCardOut(
                id=card.id, title=card.title, description=card.description,
                version_id=card.version_id, task_id=card.task_id, position=card.position,
                assignee=UserOut.model_validate(assignee, from_attributes=True) if assignee else None,
                created_at=card.created_at,
            ))
        col_outs.append(KanbanColumnOut(id=col.id, name=col.name, position=col.position, color=col.color, cards=card_outs))
    return KanbanBoardOut(id=board.id, project_id=board.project_id, name=board.name, columns=col_outs, created_at=board.created_at)


@router.get("", response_model=list[KanbanBoardOut])
def list_boards(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    boards = db.scalars(select(KanbanBoard).where(KanbanBoard.project_id == project_id)).all()
    return [_board_out(db, b) for b in boards]


@router.post("", response_model=KanbanBoardOut, status_code=status.HTTP_201_CREATED)
def create_board(project_id: int, payload: KanbanBoardCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    board = KanbanBoard(project_id=project_id, name=payload.name)
    db.add(board)
    db.flush()
    for i, col_name in enumerate(payload.columns):
        db.add(KanbanColumn(board_id=board.id, name=col_name, position=i))
    db.commit()
    db.refresh(board)
    return _board_out(db, board)


@router.get("/{board_id}", response_model=KanbanBoardOut)
def get_board(project_id: int, board_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    board = db.get(KanbanBoard, board_id)
    if board is None or board.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Board not found")
    return _board_out(db, board)


@router.post("/{board_id}/cards", response_model=KanbanCardOut, status_code=status.HTTP_201_CREATED)
def create_card(project_id: int, board_id: int, column_id: int, payload: KanbanCardCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    col = db.get(KanbanColumn, column_id)
    if col is None or col.board_id != board_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Column not found")
    pos = db.scalar(select(KanbanCard.id).where(KanbanCard.column_id == column_id).order_by(KanbanCard.position.desc()).limit(1)) or 0
    card = KanbanCard(column_id=column_id, title=payload.title, description=payload.description, version_id=payload.version_id, task_id=payload.task_id, position=pos, assignee_id=payload.assignee_id)
    db.add(card)
    db.commit()
    db.refresh(card)
    assignee = db.get(User, card.assignee_id) if card.assignee_id else None
    return KanbanCardOut(id=card.id, title=card.title, description=card.description, version_id=card.version_id, task_id=card.task_id, position=card.position, assignee=UserOut.model_validate(assignee, from_attributes=True) if assignee else None, created_at=card.created_at)


@router.patch("/{board_id}/cards/{card_id}", response_model=KanbanCardOut)
def update_card(project_id: int, board_id: int, card_id: int, payload: KanbanCardUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    card = db.get(KanbanCard, card_id)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card not found")
    if payload.title is not None: card.title = payload.title
    if payload.description is not None: card.description = payload.description
    if payload.column_id is not None: card.column_id = payload.column_id
    if payload.position is not None: card.position = payload.position
    if payload.assignee_id is not None: card.assignee_id = payload.assignee_id
    db.commit()
    db.refresh(card)
    assignee = db.get(User, card.assignee_id) if card.assignee_id else None
    return KanbanCardOut(id=card.id, title=card.title, description=card.description, version_id=card.version_id, task_id=card.task_id, position=card.position, assignee=UserOut.model_validate(assignee, from_attributes=True) if assignee else None, created_at=card.created_at)


@router.delete("/{board_id}/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(project_id: int, board_id: int, card_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    card = db.get(KanbanCard, card_id)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Card not found")
    db.delete(card)
    db.commit()
