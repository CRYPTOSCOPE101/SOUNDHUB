"""GitLab features: Merge Trains + Requirements + Design + Service Desk + SAST + Registry + Feature Flags + Errors + Incidents + On-call + Status Page + OKRs + Audit."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from datetime import datetime as dt

from ..database import get_db
from ..models import (
    CalendarEvent, ContainerImage, Design, DesignComment, Error, FeatureFlag,
    Incident, KeyResult, MergeTrain, Objective, OnCallRotation, OnCallSchedule,
    Project, PullRequest, Requirement, SecurityFinding, SecurityScan,
    ServiceDeskTicket, StatusPageComponent, StatusPageIncident,
    AuditEvent, User, utcnow,
)
from ..security import get_current_user

router = APIRouter(tags=["gitlab features"])


def _get_project(db, pid, user):
    p = db.get(Project, pid)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "Not found")
    return p


# ── Merge Trains ────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/merge-trains")
def list_merge_trains(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    trains = db.scalars(select(MergeTrain).where(MergeTrain.project_id == pid).order_by(MergeTrain.position)).all()
    return [{"id": t.id, "pr_id": t.pr_id, "position": t.position, "status": t.status, "created_at": t.created_at.isoformat()} for t in trains]


@router.post("/api/projects/{pid}/merge-trains/{pr_id}", status_code=201)
def enqueue_merge_train(pid: int, pr_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    pos = db.scalar(select(func.count(MergeTrain.id)).where(MergeTrain.project_id == pid, MergeTrain.status == "queued")) or 0
    train = MergeTrain(project_id=pid, pr_id=pr_id, position=pos)
    db.add(train)
    db.commit()
    return {"id": train.id, "position": pos}


# ── Requirements ────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/requirements")
def list_requirements(pid: int, status_filter: str | None = Query(None, alias="status"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    q = select(Requirement).where(Requirement.project_id == pid)
    if status_filter: q = q.where(Requirement.status == status_filter)
    reqs = db.scalars(q.order_by(Requirement.created_at.desc())).all()
    return [{"id": r.id, "title": r.title, "priority": r.priority, "status": r.status, "created_at": r.created_at.isoformat()} for r in reqs]


class RequirementCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"

@router.post("/api/projects/{pid}/requirements", status_code=201)
def create_requirement(pid: int, payload: RequirementCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    r = Requirement(project_id=pid, author_id=user.id, title=payload.title, description=payload.description, priority=payload.priority)
    db.add(r)
    db.commit()
    return {"id": r.id, "title": r.title}


# ── Design Management ───────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/designs")
def list_designs(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    designs = db.scalars(select(Design).where(Design.project_id == pid).order_by(Design.created_at.desc())).all()
    return [{"id": d.id, "filename": d.filename, "version": d.version, "note": d.note, "created_at": d.created_at.isoformat()} for d in designs]


@router.post("/api/projects/{pid}/designs", status_code=201)
def upload_design(pid: int, filename: str = Query(...), blob_sha: str = Query(...), size: int = Query(0), note: str = Query(""), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    d = Design(project_id=pid, author_id=user.id, filename=filename, blob_sha=blob_sha, size=size, note=note)
    db.add(d)
    db.commit()
    return {"id": d.id, "filename": d.filename}


@router.post("/api/projects/{pid}/designs/{did}/comments", status_code=201)
def comment_design(pid: int, did: int, body: str = Query(...), position_x: float = 0, position_y: float = 0, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    d = db.get(Design, did)
    if d is None or d.project_id != pid:
        raise HTTPException(404, "Not found")
    c = DesignComment(design_id=did, author_id=user.id, body=body, position_x=position_x, position_y=position_y)
    db.add(c)
    db.commit()
    return {"id": c.id, "body": c.body}


# ── Service Desk ────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/service-desk")
def list_service_desk(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    tickets = db.scalars(select(ServiceDeskTicket).where(ServiceDeskTicket.project_id == pid).order_by(ServiceDeskTicket.created_at.desc())).all()
    return [{"id": t.id, "identifier": t.identifier, "subject": t.subject, "status": t.status, "from_email": t.from_email, "created_at": t.created_at.isoformat()} for t in tickets]


class TicketCreate(BaseModel):
    subject: str
    body: str
    from_email: str = "anonymous@soundhub.dev"

@router.post("/api/projects/{pid}/service-desk", status_code=201)
def create_ticket(pid: int, payload: TicketCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    count = db.scalar(select(func.count(ServiceDeskTicket.id)).where(ServiceDeskTicket.project_id == pid)) or 0
    identifier = f"SD-{count + 1:03d}"
    t = ServiceDeskTicket(project_id=pid, identifier=identifier, subject=payload.subject, body=payload.body, from_email=payload.from_email)
    db.add(t)
    db.commit()
    return {"id": t.id, "identifier": t.identifier}


@router.patch("/api/projects/{pid}/service-desk/{tid}")
def update_ticket(pid: int, tid: int, status_val: str | None = Query(None, alias="status"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    t = db.get(ServiceDeskTicket, tid)
    if t is None or t.project_id != pid:
        raise HTTPException(404, "Not found")
    if status_val: t.status = status_val
    db.commit()
    return {"ok": True}


# ── SAST/DAST ───────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/security-scans")
def list_scans(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    scans = db.scalars(select(SecurityScan).where(SecurityScan.project_id == pid).order_by(SecurityScan.created_at.desc()).limit(20)).all()
    return [{"id": s.id, "type": s.scan_type, "status": s.status, "critical": s.critical_count, "high": s.high_count, "medium": s.medium_count, "low": s.low_count, "created_at": s.created_at.isoformat()} for s in scans]


@router.post("/api/projects/{pid}/security-scans", status_code=201)
def trigger_scan(pid: int, scan_type: str = Query(..., pattern=r"^(sast|dast|dependency|secret)$"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    scan = SecurityScan(project_id=pid, scan_type=scan_type, status="pending")
    db.add(scan)
    db.commit()
    return {"id": scan.id, "status": scan.status}


@router.get("/api/projects/{pid}/security-scans/{sid}/findings")
def list_findings(pid: int, sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    findings = db.scalars(select(SecurityFinding).where(SecurityFinding.scan_id == sid)).all()
    return [{"id": f.id, "severity": f.severity, "title": f.title, "file": f.file_path, "cwe": f.cwe, "status": f.status} for f in findings]


# ── Container Registry ──────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/registry")
def list_images(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    images = db.scalars(select(ContainerImage).where(ContainerImage.project_id == pid)).all()
    return [{"id": i.id, "name": i.name, "tag": i.tag, "size": i.size, "created_at": i.created_at.isoformat()} for i in images]


# ── Feature Flags ───────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/feature-flags")
def list_flags(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    flags = db.scalars(select(FeatureFlag).where(FeatureFlag.project_id == pid)).all()
    return [{"id": f.id, "name": f.name, "enabled": f.enabled, "description": f.description} for f in flags]


class FlagCreate(BaseModel):
    name: str
    description: str = ""
    enabled: bool = False

@router.post("/api/projects/{pid}/feature-flags", status_code=201)
def create_flag(pid: int, payload: FlagCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    f = FeatureFlag(project_id=pid, name=payload.name, description=payload.description, enabled=payload.enabled)
    db.add(f)
    db.commit()
    return {"id": f.id, "name": f.name, "enabled": f.enabled}


@router.patch("/api/projects/{pid}/feature-flags/{fid}")
def toggle_flag(pid: int, fid: int, enabled: bool = Query(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    f = db.get(FeatureFlag, fid)
    if f is None or f.project_id != pid:
        raise HTTPException(404, "Not found")
    f.enabled = enabled
    db.commit()
    return {"ok": True, "enabled": f.enabled}


# ── Error Tracking ──────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/errors")
def list_errors(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    errors = db.scalars(select(Error).where(Error.project_id == pid).order_by(Error.last_seen.desc())).all()
    return [{"id": e.id, "message": e.message, "severity": e.severity, "status": e.status, "count": e.occurrence_count, "last_seen": e.last_seen.isoformat()} for e in errors]


@router.patch("/api/projects/{pid}/errors/{eid}")
def resolve_error(pid: int, eid: int, status_val: str = Query(..., alias="status"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    e = db.get(Error, eid)
    if e is None or e.project_id != pid:
        raise HTTPException(404, "Not found")
    e.status = status_val
    if status_val == "resolved":
        e.resolved_at = utcnow()
    db.commit()
    return {"ok": True}


# ── Incidents ───────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/incidents")
def list_incidents(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    incidents = db.scalars(select(Incident).where(Incident.project_id == pid).order_by(Incident.created_at.desc())).all()
    return [{"id": i.id, "title": i.title, "severity": i.severity, "status": i.status, "created_at": i.created_at.isoformat()} for i in incidents]


class IncidentCreate(BaseModel):
    title: str
    description: str = ""
    severity: str = "minor"

@router.post("/api/projects/{pid}/incidents", status_code=201)
def create_incident(pid: int, payload: IncidentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    inc = Incident(project_id=pid, title=payload.title, description=payload.description, severity=payload.severity)
    db.add(inc)
    db.commit()
    return {"id": inc.id, "title": inc.title}


@router.patch("/api/projects/{pid}/incidents/{iid}")
def update_incident(pid: int, iid: int, status_val: str | None = Query(None, alias="status"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    inc = db.get(Incident, iid)
    if inc is None or inc.project_id != pid:
        raise HTTPException(404, "Not found")
    if status_val:
        inc.status = status_val
        if status_val == "resolved":
            inc.resolved_at = utcnow()
    db.commit()
    return {"ok": True}


# ── On-call ─────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/oncall")
def list_oncall(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    schedules = db.scalars(select(OnCallSchedule).where(OnCallSchedule.project_id == pid)).all()
    return [{"id": s.id, "name": s.name, "interval": s.rotation_interval} for s in schedules]


class OncallCreate(BaseModel):
    name: str
    rotation_interval: str = "weekly"

@router.post("/api/projects/{pid}/oncall", status_code=201)
def create_schedule(pid: int, payload: OncallCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    s = OnCallSchedule(project_id=pid, name=payload.name, rotation_interval=payload.rotation_interval)
    db.add(s)
    db.commit()
    return {"id": s.id, "name": s.name}


# ── Status Page ─────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/status-page")
def get_status_page(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    components = db.scalars(select(StatusPageComponent).where(StatusPageComponent.project_id == pid)).all()
    incidents = db.scalars(select(StatusPageIncident).where(StatusPageIncident.project_id == pid, StatusPageIncident.status != "resolved").order_by(StatusPageIncident.created_at.desc())).all()
    return {
        "components": [{"id": c.id, "name": c.name, "status": c.status} for c in components],
        "incidents": [{"id": i.id, "title": i.title, "status": i.status, "impact": i.impact, "created_at": i.created_at.isoformat()} for i in incidents],
    }


class ComponentCreate(BaseModel):
    name: str
    status: str = "operational"

@router.post("/api/projects/{pid}/status-page/components", status_code=201)
def add_component(pid: int, payload: ComponentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    c = StatusPageComponent(project_id=pid, name=payload.name, status=payload.status)
    db.add(c)
    db.commit()
    return {"id": c.id, "name": c.name, "status": c.status}


# ── OKRs ────────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/okrs")
def list_okrs(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    objectives = db.scalars(select(Objective).where(Objective.project_id == pid)).all()
    result = []
    for obj in objectives:
        krs = db.scalars(select(KeyResult).where(KeyResult.objective_id == obj.id)).all()
        result.append({"id": obj.id, "title": obj.title, "period": obj.period, "progress": obj.progress, "key_results": [{"id": kr.id, "title": kr.title, "target": kr.target_value, "current": kr.current_value, "unit": kr.unit} for kr in krs]})
    return result


class ObjectiveCreate(BaseModel):
    title: str
    description: str = ""
    period: str = "Q1 2026"

@router.post("/api/projects/{pid}/okrs", status_code=201)
def create_objective(pid: int, payload: ObjectiveCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    obj = Objective(project_id=pid, title=payload.title, description=payload.description, period=payload.period)
    db.add(obj)
    db.commit()
    return {"id": obj.id, "title": obj.title}


class KRCreate(BaseModel):
    title: str
    target_value: float = 100
    unit: str = ""

@router.post("/api/projects/{pid}/okrs/{oid}/key-results", status_code=201)
def create_kr(pid: int, oid: int, payload: KRCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    kr = KeyResult(objective_id=oid, title=payload.title, target_value=payload.target_value, unit=payload.unit)
    db.add(kr)
    db.commit()
    return {"id": kr.id, "title": kr.title}


# ── Audit Events ────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/audit")
def list_audit(pid: int, limit: int = Query(50, le=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    events = db.scalars(select(AuditEvent).where(AuditEvent.project_id == pid).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [{"id": e.id, "action": e.action, "target": f"{e.target_type}:{e.target_id}", "details": e.details, "ip": e.ip_address, "created_at": e.created_at.isoformat()} for e in events]
