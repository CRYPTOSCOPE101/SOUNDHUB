"""Secrets + Environments + Git LFS + Custom Roles + Push Rules."""
import hashlib
import base64
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    CustomRole, Environment, IPAllowList, LFSPointer, Project, ProjectMemberRole,
    ProjectSecret, PushRule, User, utcnow,
)
from ..security import get_current_user

router = APIRouter(tags=["secrets, envs, lfs, roles, rules"])


def _get_project(db, pid, user):
    p = db.get(Project, pid)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "Not found")
    return p


def _encrypt(val: str) -> str:
    return hashlib.sha256(val.encode()).hexdigest()

def _mask(val: str) -> str:
    return val[:4] + "****" + val[-4:] if len(val) > 8 else "****"


# ── Secrets ─────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/secrets")
def list_secrets(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    secrets = db.scalars(select(ProjectSecret).where(ProjectSecret.project_id == pid)).all()
    return [{"id": s.id, "name": s.name, "environment": s.environment, "created_at": s.created_at.isoformat()} for s in secrets]


class SecretCreate(BaseModel):
    name: str
    value: str
    environment: str = "all"

@router.post("/api/projects/{pid}/secrets", status_code=201)
def create_secret(pid: int, payload: SecretCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    existing = db.scalar(select(ProjectSecret).where(ProjectSecret.project_id == pid, ProjectSecret.name == payload.name, ProjectSecret.environment == payload.environment))
    if existing:
        existing.encrypted_value = _encrypt(payload.value)
        existing.updated_at = utcnow()
    else:
        s = ProjectSecret(project_id=pid, name=payload.name, encrypted_value=_encrypt(payload.value), environment=payload.environment, created_by=user.id)
        db.add(s)
    db.commit()
    return {"ok": True, "name": payload.name}


@router.delete("/api/projects/{pid}/secrets/{sid}", status_code=204)
def delete_secret(pid: int, sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(ProjectSecret, sid)
    if s is None or s.project_id != pid:
        raise HTTPException(404, "Not found")
    db.delete(s)
    db.commit()


# ── Environments ────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/environments")
def list_environments(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    envs = db.scalars(select(Environment).where(Environment.project_id == pid)).all()
    return [{"id": e.id, "name": e.name, "branch_pattern": e.branch_pattern, "protection_rules": e.protection_rules} for e in envs]


class EnvCreate(BaseModel):
    name: str
    branch_pattern: str = "main"
    protection_rules: dict = {}

@router.post("/api/projects/{pid}/environments", status_code=201)
def create_environment(pid: int, payload: EnvCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    e = Environment(project_id=pid, name=payload.name, branch_pattern=payload.branch_pattern, protection_rules=payload.protection_rules)
    db.add(e)
    db.commit()
    return {"id": e.id, "name": e.name}


# ── Git LFS ─────────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/lfs")
def list_lfs_pointers(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    pointers = db.scalars(select(LFSPointer).where(LFSPointer.project_id == pid)).all()
    return [{"id": p.id, "oid": p.oid, "size": p.size, "path": p.path} for p in pointers]


class LFSCreate(BaseModel):
    oid: str
    size: int
    path: str
    blob_sha: str

@router.post("/api/projects/{pid}/lfs", status_code=201)
def create_lfs_pointer(pid: int, payload: LFSCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    lfs = LFSPointer(project_id=pid, oid=payload.oid, size=payload.size, path=payload.path, blob_sha=payload.blob_sha)
    db.add(lfs)
    db.commit()
    return {"id": lfs.id, "oid": lfs.oid}


# ── Custom Roles ────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/roles")
def list_roles(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    roles = db.scalars(select(CustomRole).where(CustomRole.project_id == pid)).all()
    return [{"id": r.id, "name": r.name, "permissions": r.permissions} for r in roles]


class RoleCreate(BaseModel):
    name: str
    permissions: dict = {}

@router.post("/api/projects/{pid}/roles", status_code=201)
def create_role(pid: int, payload: RoleCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    r = CustomRole(project_id=pid, name=payload.name, permissions=payload.permissions)
    db.add(r)
    db.commit()
    return {"id": r.id, "name": r.name, "permissions": r.permissions}


class RoleAssign(BaseModel):
    user_id: int
    role_id: int

@router.post("/api/projects/{pid}/roles/assign", status_code=201)
def assign_role(pid: int, payload: RoleAssign, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    existing = db.scalar(select(ProjectMemberRole).where(ProjectMemberRole.project_id == pid, ProjectMemberRole.user_id == payload.user_id))
    if existing:
        existing.role_id = payload.role_id
    else:
        db.add(ProjectMemberRole(project_id=pid, user_id=payload.user_id, role_id=payload.role_id, granted_by=user.id))
    db.commit()
    return {"ok": True}


# ── Push Rules ──────────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/push-rules")
def get_push_rules(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    rule = db.scalar(select(PushRule).where(PushRule.project_id == pid))
    if rule is None:
        return {"configured": False}
    return {"configured": True, "id": rule.id, "require_signed_commits": rule.require_signed_commits, "deny_force_push": rule.deny_force_push, "deny_delete_branch": rule.deny_delete_branch, "commit_message_pattern": rule.commit_message_pattern, "branch_name_pattern": rule.branch_name_pattern, "max_file_size_mb": rule.max_file_size_mb}


class PushRuleCreate(BaseModel):
    require_signed_commits: bool = False
    deny_force_push: bool = True
    deny_delete_branch: bool = True
    commit_message_pattern: str = ""
    branch_name_pattern: str = ""
    max_file_size_mb: int = 100

@router.put("/api/projects/{pid}/push-rules")
def set_push_rules(pid: int, payload: PushRuleCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    existing = db.scalar(select(PushRule).where(PushRule.project_id == pid))
    if existing:
        for k, v in payload.model_dump().items():
            setattr(existing, k, v)
    else:
        rule = PushRule(project_id=pid, **payload.model_dump())
        db.add(rule)
    db.commit()
    return {"ok": True}


# ── IP Allow List ───────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/ip-allowlist")
def list_ip_allowlist(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    items = db.scalars(select(IPAllowList).where(IPAllowList.project_id == pid)).all()
    return [{"id": i.id, "ip_range": i.ip_range, "description": i.description, "enabled": i.enabled} for i in items]


class IPAllowCreate(BaseModel):
    ip_range: str
    description: str = ""

@router.post("/api/projects/{pid}/ip-allowlist", status_code=201)
def add_ip_allowlist(pid: int, payload: IPAllowCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    item = IPAllowList(project_id=pid, ip_range=payload.ip_range, description=payload.description)
    db.add(item)
    db.commit()
    return {"id": item.id, "ip_range": item.ip_range}
