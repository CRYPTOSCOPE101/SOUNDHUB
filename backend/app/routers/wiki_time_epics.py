"""Wiki + Time Tracking + Epics + Roadmaps + Calendar."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from datetime import datetime as dt

from ..database import get_db
from ..models import (
    CalendarEvent, Epic, EpicTaskLink, Milestone, MusicTask, Project,
    RoadmapItem, TimeEntry, User, WikiPage, WikiRevision, utcnow,
)
from ..security import get_current_user

router = APIRouter(tags=["wiki, time, epics, roadmap, calendar"])


def _get_project(db, pid, user):
    p = db.get(Project, pid)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "Not found")
    return p


# ── Wiki ────────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/wiki")
def list_wiki(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    pages = db.scalars(select(WikiPage).where(WikiPage.project_id == pid).order_by(WikiPage.title)).all()
    return [{"id": p.id, "slug": p.slug, "title": p.title, "version": p.version, "updated_at": p.updated_at.isoformat()} for p in pages]


class WikiCreate(BaseModel):
    slug: str
    title: str
    content: str = ""

@router.post("/api/projects/{pid}/wiki", status_code=201)
def create_wiki_page(pid: int, payload: WikiCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    existing = db.scalar(select(WikiPage).where(WikiPage.project_id == pid, WikiPage.slug == payload.slug))
    if existing:
        raise HTTPException(409, "Page exists")
    page = WikiPage(project_id=pid, slug=payload.slug, title=payload.title, content=payload.content, author_id=user.id)
    db.add(page)
    db.flush()
    db.add(WikiRevision(page_id=page.id, author_id=user.id, content=payload.content, version=1))
    db.commit()
    return {"id": page.id, "slug": page.slug}


@router.get("/api/projects/{pid}/wiki/{slug}")
def get_wiki(pid: int, slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    page = db.scalar(select(WikiPage).where(WikiPage.project_id == pid, WikiPage.slug == slug))
    if page is None:
        raise HTTPException(404, "Page not found")
    return {"id": page.id, "slug": page.slug, "title": page.title, "content": page.content, "version": page.version}


class WikiUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    message: str = ""

@router.put("/api/projects/{pid}/wiki/{slug}")
def update_wiki(pid: int, slug: str, payload: WikiUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    page = db.scalar(select(WikiPage).where(WikiPage.project_id == pid, WikiPage.slug == slug))
    if page is None:
        raise HTTPException(404, "Page not found")
    if payload.title is not None:
        page.title = payload.title
    if payload.content is not None:
        page.content = payload.content
        page.version += 1
        db.add(WikiRevision(page_id=page.id, author_id=user.id, content=payload.content, message=payload.message, version=page.version))
    db.commit()
    return {"ok": True, "version": page.version}


@router.delete("/api/projects/{pid}/wiki/{slug}", status_code=204)
def delete_wiki(pid: int, slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    page = db.scalar(select(WikiPage).where(WikiPage.project_id == pid, WikiPage.slug == slug))
    if page is None:
        raise HTTPException(404, "Page not found")
    db.delete(page)
    db.commit()


@router.get("/api/projects/{pid}/wiki/{slug}/revisions")
def wiki_revisions(pid: int, slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    page = db.scalar(select(WikiPage).where(WikiPage.project_id == pid, WikiPage.slug == slug))
    if page is None:
        raise HTTPException(404, "Page not found")
    revs = db.scalars(select(WikiRevision).where(WikiRevision.page_id == page.id).order_by(WikiRevision.version.desc())).all()
    return [{"id": r.id, "version": r.version, "message": r.message, "created_at": r.created_at.isoformat()} for r in revs]


# ── Time Tracking ───────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/time")
def list_time(pid: int, user_id: int | None = None, task_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    q = select(TimeEntry).where(TimeEntry.project_id == pid)
    if user_id: q = q.where(TimeEntry.user_id == user_id)
    if task_id: q = q.where(TimeEntry.task_id == task_id)
    entries = db.scalars(q.order_by(TimeEntry.date.desc())).all()
    total = sum(e.hours for e in entries)
    return {"entries": [{"id": e.id, "hours": e.hours, "description": e.description, "date": e.date.isoformat()} for e in entries], "total_minutes": total}


class TimeCreate(BaseModel):
    hours: int  # minutes
    description: str = ""
    task_id: int | None = None
    date: str | None = None

@router.post("/api/projects/{pid}/time", status_code=201)
def log_time(pid: int, payload: TimeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    entry = TimeEntry(user_id=user.id, project_id=pid, hours=payload.hours, description=payload.description, task_id=payload.task_id)
    if payload.date:
        entry.date = dt.fromisoformat(payload.date)
    db.add(entry)
    db.commit()
    return {"id": entry.id, "hours": entry.hours}


# ── Epics ───────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/epics")
def list_epics(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    epics = db.scalars(select(Epic).where(Epic.project_id == pid).order_by(Epic.created_at.desc())).all()
    result = []
    for e in epics:
        task_count = db.scalar(select(func.count(EpicTaskLink.id)).where(EpicTaskLink.epic_id == e.id)) or 0
        result.append({"id": e.id, "title": e.title, "color": e.color, "status": e.status, "task_count": task_count, "start_date": e.start_date.isoformat() if e.start_date else None, "due_date": e.due_date.isoformat() if e.due_date else None})
    return result


class EpicCreate(BaseModel):
    title: str
    description: str = ""
    color: str = "#6366f1"
    start_date: str | None = None
    due_date: str | None = None

@router.post("/api/projects/{pid}/epics", status_code=201)
def create_epic(pid: int, payload: EpicCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    epic = Epic(project_id=pid, author_id=user.id, title=payload.title, description=payload.description, color=payload.color)
    if payload.start_date: epic.start_date = dt.fromisoformat(payload.start_date)
    if payload.due_date: epic.due_date = dt.fromisoformat(payload.due_date)
    db.add(epic)
    db.commit()
    return {"id": epic.id, "title": epic.title}


@router.post("/api/projects/{pid}/epics/{eid}/tasks/{tid}", status_code=201)
def link_task_to_epic(pid: int, eid: int, tid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    existing = db.scalar(select(EpicTaskLink).where(EpicTaskLink.epic_id == eid, EpicTaskLink.task_id == tid))
    if existing:
        raise HTTPException(409, "Already linked")
    db.add(EpicTaskLink(epic_id=eid, task_id=tid))
    db.commit()
    return {"ok": True}


# ── Roadmaps ────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/roadmap")
def list_roadmap(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    items = db.scalars(select(RoadmapItem).where(RoadmapItem.project_id == pid).order_by(RoadmapItem.start_date)).all()
    return [{"id": i.id, "title": i.title, "category": i.category, "start_date": i.start_date.isoformat(), "end_date": i.end_date.isoformat(), "progress": i.progress, "color": i.color} for i in items]


class RoadmapCreate(BaseModel):
    title: str
    category: str = "feature"
    start_date: str
    end_date: str
    progress: int = 0
    color: str = "#3b82f6"

@router.post("/api/projects/{pid}/roadmap", status_code=201)
def create_roadmap_item(pid: int, payload: RoadmapCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    item = RoadmapItem(project_id=pid, title=payload.title, category=payload.category, start_date=dt.fromisoformat(payload.start_date), end_date=dt.fromisoformat(payload.end_date), progress=payload.progress, color=payload.color)
    db.add(item)
    db.commit()
    return {"id": item.id, "title": item.title}


# ── Calendar ────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/calendar")
def list_calendar(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    events = db.scalars(select(CalendarEvent).where(CalendarEvent.project_id == pid).order_by(CalendarEvent.start_at)).all()
    return [{"id": e.id, "title": e.title, "start_at": e.start_at.isoformat(), "end_at": e.end_at.isoformat(), "all_day": e.all_day, "recurrence": e.recurrence} for e in events]


class CalendarCreate(BaseModel):
    title: str
    description: str = ""
    start_at: str
    end_at: str
    all_day: bool = False
    recurrence: str = ""

@router.post("/api/projects/{pid}/calendar", status_code=201)
def create_event(pid: int, payload: CalendarCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    event = CalendarEvent(project_id=pid, user_id=user.id, title=payload.title, description=payload.description, start_at=dt.fromisoformat(payload.start_at), end_at=dt.fromisoformat(payload.end_at), all_day=payload.all_day, recurrence=payload.recurrence)
    db.add(event)
    db.commit()
    return {"id": event.id, "title": event.title}
