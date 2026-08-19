"""Code Search + Code Insights + Smart Mirroring + Extensions Marketplace."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    CodeInsightReport, CodeSearchIndex, Commit, Extension, ExtensionInstall,
    MirrorConfig, Project, User, utcnow,
)
from ..security import get_current_user

router = APIRouter(tags=["code search, insights, mirroring, extensions"])


def _get_project(db, pid, user):
    p = db.get(Project, pid)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "Not found")
    return p


# ── Code Search ─────────────────────────────────────────────────────────────

class SearchIndexCreate(BaseModel):
    file_path: str
    content: str
    language: str = ""


@router.post("/api/projects/{pid}/code-search/index", status_code=201)
def index_file(pid: int, commit_id: int = Query(...), payload: SearchIndexCreate = None,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    if payload is None:
        raise HTTPException(422, "Body required")
    commit = db.get(Commit, commit_id)
    if commit is None or commit.project_id != pid:
        raise HTTPException(404, "Commit not found")
    idx = db.scalar(select(CodeSearchIndex).where(
        CodeSearchIndex.project_id == pid, CodeSearchIndex.file_path == payload.file_path,
        CodeSearchIndex.commit_id == commit_id))
    if idx:
        idx.content = payload.content
        idx.language = payload.language
        idx.indexed_at = utcnow()
    else:
        idx = CodeSearchIndex(project_id=pid, commit_id=commit_id, file_path=payload.file_path,
                              content=payload.content, language=payload.language)
        db.add(idx)
    db.commit()
    return {"ok": True, "file_path": idx.file_path}


@router.get("/api/projects/{pid}/code-search")
def search_code(pid: int, q: str = Query(..., min_length=1), language: str | None = None,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    q_like = f"%{q}%"
    query = select(CodeSearchIndex).where(
        CodeSearchIndex.project_id == pid,
        or_(CodeSearchIndex.content.ilike(q_like), CodeSearchIndex.file_path.ilike(q_like)))
    if language:
        query = query.where(CodeSearchIndex.language == language)
    results = db.scalars(query.order_by(CodeSearchIndex.indexed_at.desc()).limit(50)).all()
    return [{"file": r.file_path, "language": r.language, "snippet": r.content[:200],
             "commit_id": r.commit_id, "indexed_at": r.indexed_at.isoformat()} for r in results]


# ── Code Insights ───────────────────────────────────────────────────────────

class InsightReport(BaseModel):
    report_type: str  # coverage | lint | complexity | security | custom
    reporter: str
    result_data: dict = {}
    summary: str = ""
    passed: bool = True


@router.get("/api/projects/{pid}/code-insights")
def list_insights(pid: int, commit_id: int | None = None,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    q = select(CodeInsightReport).where(CodeInsightReport.project_id == pid)
    if commit_id:
        q = q.where(CodeInsightReport.commit_id == commit_id)
    reports = db.scalars(q.order_by(CodeInsightReport.created_at.desc()).limit(50)).all()
    return [{"id": r.id, "commit_id": r.commit_id, "type": r.report_type, "reporter": r.reporter,
             "passed": r.passed, "summary": r.summary, "created_at": r.created_at.isoformat()} for r in reports]


@router.post("/api/projects/{pid}/code-insights", status_code=201)
def create_insight(pid: int, commit_id: int = Query(...), payload: InsightReport = None,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    if payload is None:
        raise HTTPException(422, "Body required")
    report = CodeInsightReport(project_id=pid, commit_id=commit_id, report_type=payload.report_type,
                               reporter=payload.reporter, result_data=payload.result_data,
                               summary=payload.summary, passed=payload.passed)
    db.add(report)
    db.commit()
    return {"id": report.id, "passed": report.passed}


# ── Smart Mirroring ─────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/mirrors")
def list_mirrors(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    mirrors = db.scalars(select(MirrorConfig).where(MirrorConfig.project_id == pid)).all()
    return [{"id": m.id, "url": m.mirror_url, "interval": m.sync_interval_min,
             "status": m.status, "last_synced": m.last_synced_at.isoformat() if m.last_synced_at else None} for m in mirrors]


class MirrorCreate(BaseModel):
    mirror_url: str
    sync_interval_min: int = 30


@router.post("/api/projects/{pid}/mirrors", status_code=201)
def create_mirror(pid: int, payload: MirrorCreate,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    m = MirrorConfig(project_id=pid, mirror_url=payload.mirror_url, sync_interval_min=payload.sync_interval_min)
    db.add(m)
    db.commit()
    return {"id": m.id, "url": m.mirror_url, "status": m.status}


@router.post("/api/projects/{pid}/mirrors/{mid}/sync")
def sync_mirror(pid: int, mid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    m = db.get(MirrorConfig, mid)
    if m is None or m.project_id != pid:
        raise HTTPException(404, "Not found")
    m.last_synced_at = utcnow()
    db.commit()
    return {"ok": True, "synced_at": m.last_synced_at.isoformat()}


@router.patch("/api/projects/{pid}/mirrors/{mid}")
def update_mirror(pid: int, mid: int, status_val: str | None = Query(None, alias="status"),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    m = db.get(MirrorConfig, mid)
    if m is None or m.project_id != pid:
        raise HTTPException(404, "Not found")
    if status_val:
        m.status = status_val
    db.commit()
    return {"ok": True, "status": m.status}


# ── Extensions Marketplace ──────────────────────────────────────────────────

@router.get("/api/extensions")
def list_extensions(category: str | None = None, db: Session = Depends(get_db)):
    q = select(Extension)
    if category:
        q = q.where(Extension.category == category)
    exts = db.scalars(q.order_by(Extension.install_count.desc())).all()
    return [{"id": e.id, "name": e.name, "description": e.description, "version": e.version,
             "author": e.author, "category": e.category, "installs": e.install_count,
             "rating": e.rating, "official": e.is_official} for e in exts]


class ExtensionCreate(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    category: str = "utility"
    manifest_url: str = ""


@router.post("/api/extensions", status_code=201)
def publish_extension(payload: ExtensionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ext = Extension(name=payload.name, description=payload.description, version=payload.version,
                    author=payload.author, category=payload.category, manifest_url=payload.manifest_url)
    db.add(ext)
    db.commit()
    return {"id": ext.id, "name": ext.name}


@router.post("/api/projects/{pid}/extensions/{eid}/install", status_code=201)
def install_extension(pid: int, eid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    existing = db.scalar(select(ExtensionInstall).where(
        ExtensionInstall.project_id == pid, ExtensionInstall.extension_id == eid))
    if existing:
        raise HTTPException(409, "Already installed")
    db.add(ExtensionInstall(project_id=pid, extension_id=eid, installed_by=user.id))
    ext = db.get(Extension, eid)
    if ext:
        ext.install_count += 1
    db.commit()
    return {"ok": True}


@router.get("/api/projects/{pid}/extensions")
def list_project_extensions(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    installs = db.scalars(select(ExtensionInstall).where(ExtensionInstall.project_id == pid)).all()
    result = []
    for inst in installs:
        ext = db.get(Extension, inst.extension_id)
        if ext:
            result.append({"id": ext.id, "name": ext.name, "version": ext.version, "installed_at": inst.created_at.isoformat()})
    return result
