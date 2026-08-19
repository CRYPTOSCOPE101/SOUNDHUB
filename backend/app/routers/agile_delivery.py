"""Sprints + Story Points + Retrospectives + Release Approvals."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    GitTag, Milestone, Project, ReleaseApproval, RetroItem, Retrospective,
    Sprint, StoryPoint, User, utcnow,
)
from ..security import get_current_user

router = APIRouter(tags=["sprints, retros, release approvals"])


def _get_project(db, pid, user):
    p = db.get(Project, pid)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "Not found")
    return p


# ── Sprints ─────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/sprints")
def list_sprints(pid: int, state: str | None = None,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    q = select(Sprint).where(Sprint.project_id == pid)
    if state:
        q = q.where(Sprint.state == state)
    sprints = db.scalars(q.order_by(Sprint.created_at.desc())).all()
    return [{"id": s.id, "name": s.name, "goal": s.goal, "state": s.state,
             "velocity": s.velocity, "start_date": s.start_date.isoformat() if s.start_date else None,
             "end_date": s.end_date.isoformat() if s.end_date else None} for s in sprints]


class SprintCreate(BaseModel):
    name: str
    goal: str = ""
    start_date: str | None = None
    end_date: str | None = None


@router.post("/api/projects/{pid}/sprints", status_code=201)
def create_sprint(pid: int, payload: SprintCreate,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    sprint = Sprint(project_id=pid, name=payload.name, goal=payload.goal)
    if payload.start_date:
        from datetime import datetime as dt
        sprint.start_date = dt.fromisoformat(payload.start_date)
    if payload.end_date:
        from datetime import datetime as dt
        sprint.end_date = dt.fromisoformat(payload.end_date)
    db.add(sprint)
    db.commit()
    return {"id": sprint.id, "name": sprint.name}


@router.patch("/api/projects/{pid}/sprints/{sid}")
def update_sprint(pid: int, sid: int, state: str | None = Query(None),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    sprint = db.get(Sprint, sid)
    if sprint is None or sprint.project_id != pid:
        raise HTTPException(404, "Not found")
    if state:
        sprint.state = state
        if state == "completed":
            sprint.completed_at = utcnow()
    db.commit()
    return {"ok": True, "state": sprint.state}


# ── Story Points ────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/sprints/{sid}/backlog")
def sprint_backlog(pid: int, sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    points = db.scalars(select(StoryPoint).where(StoryPoint.sprint_id == sid)).all()
    total = sum(sp.points for sp in points)
    return {"total_points": total, "items": [{"task_id": sp.task_id, "points": sp.points} for sp in points]}


class SPAssign(BaseModel):
    task_id: int
    points: int = 1


@router.post("/api/projects/{pid}/sprints/{sid}/assign", status_code=201)
def assign_story_points(pid: int, sid: int, payload: SPAssign,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    existing = db.scalar(select(StoryPoint).where(
        StoryPoint.task_id == payload.task_id, StoryPoint.sprint_id == sid))
    if existing:
        existing.points = payload.points
        existing.original_points = payload.points
    else:
        sp = StoryPoint(task_id=payload.task_id, sprint_id=sid, points=payload.points,
                        original_points=payload.points)
        db.add(sp)
    db.commit()
    return {"ok": True}


# ── Retrospectives ─────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/retros")
def list_retros(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    retros = db.scalars(select(Retrospective).where(
        Retrospective.project_id == pid).order_by(Retrospective.created_at.desc())).all()
    result = []
    for r in retros:
        item_count = db.scalar(select(func.count(RetroItem.id)).where(RetroItem.retrospective_id == r.id)) or 0
        result.append({"id": r.id, "name": r.name, "state": r.state, "item_count": item_count,
                       "sprint_id": r.sprint_id})
    return result


class RetroCreate(BaseModel):
    name: str
    sprint_id: int | None = None


@router.post("/api/projects/{pid}/retros", status_code=201)
def create_retro(pid: int, payload: RetroCreate,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    retro = Retrospective(project_id=pid, name=payload.name, sprint_id=payload.sprint_id,
                          created_by=user.id)
    db.add(retro)
    db.commit()
    return {"id": retro.id, "name": retro.name}


@router.patch("/api/projects/{pid}/retros/{rid}")
def update_retro(pid: int, rid: int, state: str | None = Query(None),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    retro = db.get(Retrospective, rid)
    if retro is None or retro.project_id != pid:
        raise HTTPException(404, "Not found")
    if state:
        retro.state = state
        if state == "closed":
            retro.closed_at = utcnow()
    db.commit()
    return {"ok": True, "state": retro.state}


# ── Retro Items ─────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/retros/{rid}/items")
def list_retro_items(pid: int, rid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    items = db.scalars(select(RetroItem).where(RetroItem.retrospective_id == rid).order_by(RetroItem.votes.desc())).all()
    return [{"id": i.id, "category": i.category, "content": i.content,
             "votes": i.votes, "author_id": i.author_id} for i in items]


class RetroItemCreate(BaseModel):
    category: str  # went_well | to_improve | action_item
    content: str


@router.post("/api/projects/{pid}/retros/{rid}/items", status_code=201)
def add_retro_item(pid: int, rid: int, payload: RetroItemCreate,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    item = RetroItem(retrospective_id=rid, author_id=user.id, category=payload.category,
                     content=payload.content)
    db.add(item)
    db.commit()
    return {"id": item.id, "content": item.content}


@router.post("/api/projects/{pid}/retro-items/{iid}/vote")
def vote_retro_item(pid: int, iid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    item = db.get(RetroItem, iid)
    if item is None:
        raise HTTPException(404, "Not found")
    item.votes += 1
    db.commit()
    return {"ok": True, "votes": item.votes}


# ── Release Approvals ──────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/release-approvals")
def list_release_approvals(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    approvals = db.scalars(select(ReleaseApproval).where(
        ReleaseApproval.project_id == pid).order_by(ReleaseApproval.created_at.desc())).all()
    return [{"id": a.id, "tag_id": a.tag_id, "environment_id": a.environment_id,
             "approver_id": a.approver_id, "status": a.status} for a in approvals]


class RACreate(BaseModel):
    tag_id: int | None = None
    environment_id: int | None = None


@router.post("/api/projects/{pid}/release-approvals", status_code=201)
def create_release_approval(pid: int, payload: RACreate,
                            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    ra = ReleaseApproval(project_id=pid, tag_id=payload.tag_id,
                         environment_id=payload.environment_id, approver_id=user.id)
    db.add(ra)
    db.commit()
    return {"id": ra.id, "status": ra.status}


@router.post("/api/projects/{pid}/release-approvals/{raid}/approve")
def approve_release(pid: int, raid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    ra = db.get(ReleaseApproval, raid)
    if ra is None or ra.project_id != pid:
        raise HTTPException(404, "Not found")
    ra.status = "approved"
    ra.decided_at = utcnow()
    db.commit()
    return {"ok": True, "status": ra.status}


@router.post("/api/projects/{pid}/release-approvals/{raid}/reject")
def reject_release(pid: int, raid: int, comment: str = "",
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    ra = db.get(ReleaseApproval, raid)
    if ra is None or ra.project_id != pid:
        raise HTTPException(404, "Not found")
    ra.status = "rejected"
    ra.comment = comment
    ra.decided_at = utcnow()
    db.commit()
    return {"ok": True, "status": ra.status}
