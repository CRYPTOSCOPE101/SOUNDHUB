"""Variable Groups + Secure Files + Task Groups + Pipeline Artifacts + Approval Gates."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import timedelta

from ..database import get_db
from ..models import (
    ApprovalGate, PipelineArtifact, Project, SecureFile, TaskGroup,
    User, VariableGroup, WorkflowRun, utcnow,
)
from ..security import get_current_user

router = APIRouter(tags=["pipelines, variables, artifacts, approvals"])


def _get_project(db, pid, user):
    p = db.get(Project, pid)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "Not found")
    return p


# ── Variable Groups ─────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/variable-groups")
def list_variable_groups(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    groups = db.scalars(select(VariableGroup).where(VariableGroup.project_id == pid)).all()
    return [{"id": g.id, "name": g.name, "description": g.description,
             "var_count": len(g.variables) if g.variables else 0} for g in groups]


class VGCreate(BaseModel):
    name: str
    description: str = ""
    variables: dict = {}


@router.post("/api/projects/{pid}/variable-groups", status_code=201)
def create_variable_group(pid: int, payload: VGCreate,
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    g = VariableGroup(project_id=pid, name=payload.name, description=payload.description,
                      variables=payload.variables, created_by=user.id)
    db.add(g)
    db.commit()
    return {"id": g.id, "name": g.name}


@router.patch("/api/projects/{pid}/variable-groups/{gid}")
def update_variable_group(pid: int, gid: int, payload: VGCreate,
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    g = db.get(VariableGroup, gid)
    if g is None or g.project_id != pid:
        raise HTTPException(404, "Not found")
    g.name = payload.name
    g.description = payload.description
    g.variables = payload.variables
    db.commit()
    return {"ok": True}


@router.delete("/api/projects/{pid}/variable-groups/{gid}", status_code=204)
def delete_variable_group(pid: int, gid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    g = db.get(VariableGroup, gid)
    if g is None or g.project_id != pid:
        raise HTTPException(404, "Not found")
    db.delete(g)
    db.commit()


# ── Secure Files ────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/secure-files")
def list_secure_files(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    files = db.scalars(select(SecureFile).where(SecureFile.project_id == pid)).all()
    return [{"id": f.id, "name": f.name, "description": f.description, "size": f.size,
             "content_type": f.content_type, "expires_at": f.expires_at.isoformat() if f.expires_at else None} for f in files]


class SFCreate(BaseModel):
    name: str
    description: str = ""
    blob_sha: str
    size: int = 0
    content_type: str = "application/octet-stream"
    expires_at: str | None = None


@router.post("/api/projects/{pid}/secure-files", status_code=201)
def upload_secure_file(pid: int, payload: SFCreate,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    f = SecureFile(project_id=pid, name=payload.name, description=payload.description,
                   blob_sha=payload.blob_sha, size=payload.size, content_type=payload.content_type,
                   uploaded_by=user.id)
    if payload.expires_at:
        from datetime import datetime as dt
        f.expires_at = dt.fromisoformat(payload.expires_at)
    db.add(f)
    db.commit()
    return {"id": f.id, "name": f.name}


@router.delete("/api/projects/{pid}/secure-files/{fid}", status_code=204)
def delete_secure_file(pid: int, fid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    f = db.get(SecureFile, fid)
    if f is None or f.project_id != pid:
        raise HTTPException(404, "Not found")
    db.delete(f)
    db.commit()


# ── Task Groups ─────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/task-groups")
def list_task_groups(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    groups = db.scalars(select(TaskGroup).where(TaskGroup.project_id == pid)).all()
    return [{"id": g.id, "name": g.name, "description": g.description, "version": g.version} for g in groups]


class TGCreate(BaseModel):
    name: str
    description: str = ""
    tasks_json: dict = {}


@router.post("/api/projects/{pid}/task-groups", status_code=201)
def create_task_group(pid: int, payload: TGCreate,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    g = TaskGroup(project_id=pid, name=payload.name, description=payload.description,
                  tasks_json=payload.tasks_json, created_by=user.id)
    db.add(g)
    db.commit()
    return {"id": g.id, "name": g.name}


@router.patch("/api/projects/{pid}/task-groups/{gid}")
def update_task_group(pid: int, gid: int, payload: TGCreate,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    g = db.get(TaskGroup, gid)
    if g is None or g.project_id != pid:
        raise HTTPException(404, "Not found")
    g.name = payload.name
    g.description = payload.description
    g.tasks_json = payload.tasks_json
    g.version += 1
    db.commit()
    return {"ok": True, "version": g.version}


# ── Pipeline Artifacts ──────────────────────────────────────────────────────

@router.get("/api/workflow-runs/{run_id}/artifacts")
def list_pipeline_artifacts(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    artifacts = db.scalars(select(PipelineArtifact).where(PipelineArtifact.workflow_run_id == run_id)).all()
    return [{"id": a.id, "name": a.name, "size": a.size, "retention_days": a.retention_days,
             "expires_at": a.expires_at.isoformat() if a.expires_at else None} for a in artifacts]


class PAArtifact(BaseModel):
    name: str
    blob_sha: str
    size: int = 0
    retention_days: int = 30


@router.post("/api/workflow-runs/{run_id}/artifacts", status_code=201)
def upload_pipeline_artifact(run_id: int, payload: PAArtifact,
                             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(404, "Workflow run not found")
    from datetime import datetime as dt, timedelta as td
    artifact = PipelineArtifact(workflow_run_id=run_id, name=payload.name, blob_sha=payload.blob_sha,
                                size=payload.size, retention_days=payload.retention_days,
                                expires_at=utcnow() + td(days=payload.retention_days))
    db.add(artifact)
    db.commit()
    return {"id": artifact.id, "name": artifact.name, "expires_at": artifact.expires_at.isoformat() if artifact.expires_at else None}


# ── Approval Gates ──────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/approval-gates")
def list_approval_gates(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    gates = db.scalars(select(ApprovalGate).where(ApprovalGate.project_id == pid)).all()
    return [{"id": g.id, "name": g.name, "type": g.gate_type, "required_approvers": g.required_approvers,
             "target": g.target_pattern} for g in gates]


class GateCreate(BaseModel):
    name: str
    description: str = ""
    gate_type: str  # branch | release | deploy
    required_approvers: int = 1
    target_pattern: str = "main"


@router.post("/api/projects/{pid}/approval-gates", status_code=201)
def create_approval_gate(pid: int, payload: GateCreate,
                         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    gate = ApprovalGate(project_id=pid, name=payload.name, description=payload.description,
                        gate_type=payload.gate_type, required_approvers=payload.required_approvers,
                        target_pattern=payload.target_pattern)
    db.add(gate)
    db.commit()
    return {"id": gate.id, "name": gate.name}


@router.delete("/api/projects/{pid}/approval-gates/{gid}", status_code=204)
def delete_approval_gate(pid: int, gid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    gate = db.get(ApprovalGate, gid)
    if gate is None or gate.project_id != pid:
        raise HTTPException(404, "Not found")
    db.delete(gate)
    db.commit()
