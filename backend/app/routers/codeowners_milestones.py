"""CODEOWNERS + Milestones — ownership rules and release planning."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CodeOwner, Milestone, Project, TaskLabel, MusicTask, User, utcnow
from ..security import get_current_user

router = APIRouter(tags=["codeowners & milestones"])


# ── CODEOWNERS ──────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/codeowners")
def list_codeowners(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, pid)
    if project is None or project.owner_id != user.id:
        raise HTTPException(404, "Not found")
    owners = db.scalars(select(CodeOwner).where(CodeOwner.project_id == pid)).all()
    return [{"id": o.id, "pattern": o.pattern, "owner": o.owner_username, "created_at": o.created_at.isoformat()} for o in owners]


class CodeOwnerCreate(BaseModel):
    pattern: str
    owner_username: str

@router.post("/api/projects/{pid}/codeowners", status_code=201)
def create_codeowner(pid: int, payload: CodeOwnerCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, pid)
    if project is None or project.owner_id != user.id:
        raise HTTPException(404, "Not found")
    existing = db.scalar(select(CodeOwner).where(CodeOwner.project_id == pid, CodeOwner.pattern == payload.pattern))
    if existing:
        raise HTTPException(409, "Pattern already exists")
    co = CodeOwner(project_id=pid, pattern=payload.pattern, owner_username=payload.owner_username, owner_id=user.id)
    db.add(co)
    db.commit()
    return {"id": co.id, "pattern": co.pattern, "owner": co.owner_username}


@router.delete("/api/projects/{pid}/codeowners/{owner_id}", status_code=204)
def delete_codeowner(pid: int, owner_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    co = db.get(CodeOwner, owner_id)
    if co is None or co.project_id != pid:
        raise HTTPException(404, "Not found")
    db.delete(co)
    db.commit()


# ── MILESTONES ──────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/milestones")
def list_milestones(pid: int, status_filter: str | None = Query(None, alias="status"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, pid)
    if project is None or project.owner_id != user.id:
        raise HTTPException(404, "Not found")
    q = select(Milestone).where(Milestone.project_id == pid)
    if status_filter:
        q = q.where(Milestone.status == status_filter)
    milestones = db.scalars(q.order_by(Milestone.created_at.desc())).all()
    return [
        {
            "id": m.id, "title": m.title, "description": m.description,
            "due_date": m.due_date.isoformat() if m.due_date else None,
            "status": m.status, "created_at": m.created_at.isoformat(),
            "task_count": db.scalar(select(MusicTask).where(MusicTask.project_id == pid, MusicTask.milestone == m.title).limit(1000)),
        }
        for m in milestones
    ]


class MilestoneCreate(BaseModel):
    title: str
    description: str = ""
    due_date: str | None = None

@router.post("/api/projects/{pid}/milestones", status_code=201)
def create_milestone(pid: int, payload: MilestoneCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, pid)
    if project is None or project.owner_id != user.id:
        raise HTTPException(404, "Not found")
    m = Milestone(project_id=pid, title=payload.title, description=payload.description)
    if payload.due_date:
        from datetime import datetime as dt
        m.due_date = dt.fromisoformat(payload.due_date)
    db.add(m)
    db.commit()
    return {"id": m.id, "title": m.title, "status": m.status}


@router.patch("/api/projects/{pid}/milestones/{mid}")
def update_milestone(pid: int, mid: int, status_val: str | None = Query(None, alias="status"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Milestone, mid)
    if m is None or m.project_id != pid:
        raise HTTPException(404, "Not found")
    if status_val:
        m.status = status_val
        if status_val == "closed":
            m.closed_at = utcnow()
    db.commit()
    return {"id": m.id, "title": m.title, "status": m.status}
