"""Notifications + Watch/Star/Fork — social features and alerts."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import UserNotification, Project, ProjectFork, ProjectStar, ProjectWatch, User, utcnow
from ..security import get_current_user

router = APIRouter(tags=["notifications & social"])


# ── Notifications ───────────────────────────────────────────────────────────

@router.get("/api/notifications")
def list_notifications(user: User = Depends(get_current_user), unread_only: bool = False, db: Session = Depends(get_db)):
    q = select(UserNotification).where(UserNotification.user_id == user.id)
    if unread_only:
        q = q.where(UserNotification.read == False)
    items = db.scalars(q.order_by(UserNotification.created_at.desc()).limit(50)).all()
    return [{"id": n.id, "type": n.type, "title": n.title, "body": n.body, "url": n.url, "read": n.read, "created_at": n.created_at.isoformat()} for n in items]


@router.get("/api/notifications/count")
def notification_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(UserNotification.id)).where(UserNotification.user_id == user.id)) or 0
    unread = db.scalar(select(func.count(UserNotification.id)).where(UserNotification.user_id == user.id, UserNotification.read == False)) or 0
    return {"total": total, "unread": unread}


@router.patch("/api/notifications/{nid}/read")
def mark_read(nid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "Not found")
    n.read = True
    db.commit()
    return {"ok": True}


@router.post("/api/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(UserNotification).where(UserNotification.user_id == user.id, UserNotification.read == False)).all()
    for n in items:
        n.read = True
    db.commit()
    return {"ok": True, "count": len(items)}


def create_notification(db: Session, user_id: int, type_: str, title: str, body: str = "", url: str = ""):
    """Helper to create notifications (called from other routers)."""
    n = UserNotification(user_id=user_id, type=type_, title=title, body=body, url=url)
    db.add(n)
    return n


# ── Star ────────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/star")
def get_star(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    starred = db.scalar(select(ProjectStar).where(ProjectStar.project_id == pid, ProjectStar.user_id == user.id)) is not None
    count = db.scalar(select(func.count(ProjectStar.id)).where(ProjectStar.project_id == pid)) or 0
    return {"starred": starred, "count": count}


@router.post("/api/projects/{pid}/star")
def toggle_star(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(ProjectStar).where(ProjectStar.project_id == pid, ProjectStar.user_id == user.id))
    if existing:
        db.delete(existing)
        db.commit()
        return {"starred": False}
    else:
        db.add(ProjectStar(project_id=pid, user_id=user.id))
        db.commit()
        return {"starred": True}


# ── Watch ───────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/watch")
def get_watch(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    w = db.scalar(select(ProjectWatch).where(ProjectWatch.project_id == pid, ProjectWatch.user_id == user.id))
    return {"watching": w is not None, "level": w.level if w else "none"}


class WatchUpdate(BaseModel):
    level: str = "all"  # all | participating | ignore

@router.put("/api/projects/{pid}/watch")
def set_watch(pid: int, payload: WatchUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(ProjectWatch).where(ProjectWatch.project_id == pid, ProjectWatch.user_id == user.id))
    if existing:
        existing.level = payload.level
    else:
        db.add(ProjectWatch(project_id=pid, user_id=user.id, level=payload.level))
    db.commit()
    return {"watching": True, "level": payload.level}


@router.delete("/api/projects/{pid}/watch")
def stop_watch(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(ProjectWatch).where(ProjectWatch.project_id == pid, ProjectWatch.user_id == user.id))
    if existing:
        db.delete(existing)
        db.commit()
    return {"watching": False}


# ── Fork ────────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/forks")
def list_forks(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    forks = db.scalars(select(ProjectFork).where(ProjectFork.source_id == pid)).all()
    return [{"id": f.id, "forked_id": f.forked_id, "user_id": f.user_id, "created_at": f.created_at.isoformat()} for f in forks]


@router.post("/api/projects/{pid}/fork", status_code=201)
def fork_project(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    source = db.get(Project, pid)
    if source is None:
        raise HTTPException(404, "Project not found")
    # Create fork
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", source.name.lower()).strip("-") + "-fork"
    forked = Project(owner_id=user.id, name=f"{source.name} (fork)", slug=slug, description=f"Fork of {source.name}")
    db.add(forked)
    db.flush()
    from ..models import Branch
    db.add(Branch(project_id=forked.id, name="main"))
    db.add(ProjectFork(source_id=pid, forked_id=forked.id, user_id=user.id))
    db.commit()
    return {"id": forked.id, "name": forked.name}
