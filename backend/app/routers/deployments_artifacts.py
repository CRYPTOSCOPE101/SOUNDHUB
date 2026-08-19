"""Artifact Feeds + Deployment Tracking + Environment Approvals + Branch Permissions."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    ApprovalGate, ArtifactFeed, ArtifactPackage, BranchPermission, Commit,
    Deployment, Environment, EnvironmentApproval, Project, User,
    WorkflowRun, utcnow,
)
from ..security import get_current_user

router = APIRouter(tags=["artifacts, deployments, branch permissions, env approvals"])


def _get_project(db, pid, user):
    p = db.get(Project, pid)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "Not found")
    return p


# ── Artifact Feeds ──────────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/artifact-feeds")
def list_feeds(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    feeds = db.scalars(select(ArtifactFeed).where(ArtifactFeed.project_id == pid)).all()
    return [{"id": f.id, "name": f.name, "type": f.feed_type, "visibility": f.visibility} for f in feeds]


class FeedCreate(BaseModel):
    name: str
    feed_type: str  # npm | pip | nuget | maven | universal | sample_pack
    description: str = ""
    visibility: str = "private"


@router.post("/api/projects/{pid}/artifact-feeds", status_code=201)
def create_feed(pid: int, payload: FeedCreate,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    feed = ArtifactFeed(project_id=pid, name=payload.name, feed_type=payload.feed_type,
                        description=payload.description, visibility=payload.visibility)
    db.add(feed)
    db.commit()
    return {"id": feed.id, "name": feed.name}


@router.get("/api/projects/{pid}/artifact-feeds/{fid}/packages")
def list_feed_packages(pid: int, fid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    pkgs = db.scalars(select(ArtifactPackage).where(ArtifactPackage.feed_id == fid).order_by(ArtifactPackage.created_at.desc())).all()
    return [{"id": p.id, "name": p.name, "version": p.version, "size": p.size,
             "downloads": p.download_count} for p in pkgs]


class PkgPublish(BaseModel):
    name: str
    version: str
    description: str = ""
    blob_sha: str
    size: int = 0


@router.post("/api/projects/{pid}/artifact-feeds/{fid}/packages", status_code=201)
def publish_package(pid: int, fid: int, payload: PkgPublish,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    pkg = ArtifactPackage(feed_id=fid, name=payload.name, version=payload.version,
                          description=payload.description, blob_sha=payload.blob_sha,
                          size=payload.size, published_by=user.id)
    db.add(pkg)
    db.commit()
    return {"id": pkg.id, "name": pkg.name, "version": pkg.version}


# ── Deployment Tracking ─────────────────────────────────────────────────────

@router.get("/api/projects/{pid}/deployments")
def list_deployments(pid: int, environment_id: int | None = None,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    q = select(Deployment).where(Deployment.project_id == pid)
    if environment_id:
        q = q.where(Deployment.environment_id == environment_id)
    deploys = db.scalars(q.order_by(Deployment.created_at.desc()).limit(20)).all()
    return [{"id": d.id, "environment_id": d.environment_id, "status": d.status,
             "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None} for d in deploys]


class DeployCreate(BaseModel):
    environment_id: int
    commit_id: int | None = None
    workflow_run_id: int | None = None


@router.post("/api/projects/{pid}/deployments", status_code=201)
def create_deployment(pid: int, payload: DeployCreate,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    d = Deployment(project_id=pid, environment_id=payload.environment_id,
                   commit_id=payload.commit_id, workflow_run_id=payload.workflow_run_id,
                   deployed_by=user.id)
    db.add(d)
    db.commit()
    return {"id": d.id, "status": d.status}


@router.patch("/api/projects/{pid}/deployments/{did}")
def update_deployment(pid: int, did: int, status_val: str | None = Query(None, alias="status"),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    d = db.get(Deployment, did)
    if d is None or d.project_id != pid:
        raise HTTPException(404, "Not found")
    if status_val:
        d.status = status_val
        if status_val == "success":
            d.deployed_at = utcnow()
    db.commit()
    return {"ok": True, "status": d.status}


# ── Environment Approvals ──────────────────────────────────────────────────

@router.get("/api/projects/{pid}/environments/{eid}/approvals")
def list_env_approvals(pid: int, eid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    approvals = db.scalars(select(EnvironmentApproval).where(
        EnvironmentApproval.environment_id == eid).order_by(EnvironmentApproval.created_at.desc())).all()
    return [{"id": a.id, "deployment_id": a.deployment_id, "approver_id": a.approver_id,
             "status": a.status, "comment": a.comment} for a in approvals]


@router.post("/api/projects/{pid}/environments/{eid}/approvals/{aid}/approve")
def approve_deployment(pid: int, eid: int, aid: int,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    a = db.get(EnvironmentApproval, aid)
    if a is None or a.environment_id != eid:
        raise HTTPException(404, "Not found")
    a.status = "approved"
    a.decided_at = utcnow()
    db.commit()
    return {"ok": True, "status": a.status}


@router.post("/api/projects/{pid}/environments/{eid}/approvals/{aid}/reject")
def reject_deployment(pid: int, eid: int, aid: int, comment: str = "",
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    a = db.get(EnvironmentApproval, aid)
    if a is None or a.environment_id != eid:
        raise HTTPException(404, "Not found")
    a.status = "rejected"
    a.comment = comment
    a.decided_at = utcnow()
    db.commit()
    return {"ok": True, "status": a.status}


# ── Branch Permissions (advanced) ──────────────────────────────────────────

@router.get("/api/projects/{pid}/branch-permissions")
def list_branch_permissions(pid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    perms = db.scalars(select(BranchPermission).where(BranchPermission.project_id == pid)).all()
    return [{"id": p.id, "branch_pattern": p.branch_pattern, "permission_type": p.permission_type,
             "grant_type": p.grant_type} for p in perms]


class BPCreate(BaseModel):
    branch_pattern: str
    permission_type: str  # push | merge | force_push | delete
    grant_type: str  # allow | deny
    user_id: int | None = None
    team_id: int | None = None


@router.post("/api/projects/{pid}/branch-permissions", status_code=201)
def create_branch_permission(pid: int, payload: BPCreate,
                             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    bp = BranchPermission(project_id=pid, branch_pattern=payload.branch_pattern,
                          permission_type=payload.permission_type, grant_type=payload.grant_type,
                          user_id=payload.user_id, team_id=payload.team_id)
    db.add(bp)
    db.commit()
    return {"id": bp.id, "pattern": bp.branch_pattern}


@router.delete("/api/projects/{pid}/branch-permissions/{bid}", status_code=204)
def delete_branch_permission(pid: int, bid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, pid, user)
    bp = db.get(BranchPermission, bid)
    if bp is None or bp.project_id != pid:
        raise HTTPException(404, "Not found")
    db.delete(bp)
    db.commit()
