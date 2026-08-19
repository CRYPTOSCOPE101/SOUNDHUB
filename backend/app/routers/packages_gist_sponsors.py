"""Packages + Gist + Sponsors + Teams."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Gist, GistFile, Package, Sponsorship, Team, TeamMember, TeamProjectAccess, User, utcnow,
)
from ..security import get_current_user

router = APIRouter(tags=["packages, gist, sponsors, teams"])


# ── Packages ────────────────────────────────────────────────────────────────

@router.get("/api/packages")
def list_packages(user: User = Depends(get_current_user), package_type: str | None = None, db: Session = Depends(get_db)):
    q = select(Package).where(Package.owner_id == user.id)
    if package_type:
        q = q.where(Package.package_type == package_type)
    pkgs = db.scalars(q.order_by(Package.created_at.desc())).all()
    return [{"id": p.id, "name": p.name, "type": p.package_type, "version": p.version, "downloads": p.download_count, "created_at": p.created_at.isoformat()} for p in pkgs]


class PackageCreate(BaseModel):
    name: str
    description: str = ""
    package_type: str = "sample_pack"
    version: str = "1.0.0"
    license: str = "royalty-free"
    price_cents: int = 0
    tags: str = ""
    blob_sha: str = ""
    size: int = 0
    file_count: int = 0

@router.post("/api/packages", status_code=201)
def create_package(payload: PackageCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = Package(owner_id=user.id, **payload.model_dump())
    db.add(p)
    db.commit()
    return {"id": p.id, "name": p.name, "version": p.version}


@router.get("/api/packages/{pkg_id}")
def get_package(pkg_id: int, db: Session = Depends(get_db)):
    p = db.get(Package, pkg_id)
    if p is None:
        raise HTTPException(404, "Not found")
    return {"id": p.id, "name": p.name, "description": p.description, "type": p.package_type, "version": p.version, "license": p.license, "price_cents": p.price_cents, "downloads": p.download_count, "tags": p.tags, "created_at": p.created_at.isoformat()}


@router.post("/api/packages/{pkg_id}/download")
def download_package(pkg_id: int, db: Session = Depends(get_db)):
    p = db.get(Package, pkg_id)
    if p is None:
        raise HTTPException(404, "Not found")
    p.download_count += 1
    db.commit()
    return {"blob_sha": p.blob_sha, "size": p.size, "name": p.name}


# ── Gist ────────────────────────────────────────────────────────────────────

@router.get("/api/gists")
def list_gists(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    gists = db.scalars(select(Gist).where(Gist.user_id == user.id).order_by(Gist.updated_at.desc())).all()
    return [{"id": g.id, "title": g.title, "public": g.public, "files": len(g.files), "stars": g.star_count, "created_at": g.created_at.isoformat()} for g in gists]


class GistCreate(BaseModel):
    title: str = ""
    description: str = ""
    public: bool = True
    files: list[dict] = []  # [{"filename": "x.py", "content": "...", "language": "python"}]

@router.post("/api/gists", status_code=201)
def create_gist(payload: GistCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = Gist(user_id=user.id, title=payload.title, description=payload.description, public=payload.public)
    db.add(g)
    db.flush()
    for f in payload.files:
        db.add(GistFile(gist_id=g.id, filename=f.get("filename", "file"), content=f.get("content", ""), language=f.get("language", ""), size=len(f.get("content", ""))))
    db.commit()
    return {"id": g.id, "title": g.title}


@router.get("/api/gists/{gid}")
def get_gist(gid: int, db: Session = Depends(get_db)):
    g = db.get(Gist, gid)
    if g is None:
        raise HTTPException(404, "Not found")
    files = [{"filename": f.filename, "content": f.content, "language": f.language, "size": f.size} for f in g.files]
    return {"id": g.id, "title": g.title, "description": g.description, "public": g.public, "files": files, "stars": g.star_count, "created_at": g.created_at.isoformat()}


@router.delete("/api/gists/{gid}", status_code=204)
def delete_gist(gid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.get(Gist, gid)
    if g is None or g.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(g)
    db.commit()


# ── Sponsors ────────────────────────────────────────────────────────────────

@router.get("/api/users/{username}/sponsors")
def list_sponsors(username: str, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(404, "User not found")
    sponsorships = db.scalars(select(Sponsorship).where(Sponsorship.creator_id == user.id, Sponsorship.active == True)).all()
    total = sum(s.amount_cents for s in sponsorships)
    return {"total_cents": total, "sponsor_count": len(sponsorships)}


class SponsorCreate(BaseModel):
    creator_id: int
    tier: str = "buy_me_a_coffee"
    amount_cents: int = 500
    message: str = ""

@router.post("/api/sponsors", status_code=201)
def create_sponsorship(payload: SponsorCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = Sponsorship(sponsor_id=user.id, creator_id=payload.creator_id, tier=payload.tier, amount_cents=payload.amount_cents, message=payload.message)
    db.add(s)
    db.commit()
    return {"id": s.id, "tier": s.tier, "amount_cents": s.amount_cents}


# ── Teams ───────────────────────────────────────────────────────────────────

@router.get("/api/teams")
def list_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member_of = db.scalars(select(TeamMember).where(TeamMember.user_id == user.id)).all()
    team_ids = [m.team_id for m in member_of]
    teams = db.scalars(select(Team).where(Team.id.in_(team_ids))).all()
    return [{"id": t.id, "name": t.name, "description": t.description, "privacy": t.privacy} for t in teams]


class TeamCreate(BaseModel):
    name: str
    description: str = ""
    privacy: str = "visible"

@router.post("/api/teams", status_code=201)
def create_team(payload: TeamCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = Team(name=payload.name, description=payload.description, privacy=payload.privacy)
    db.add(t)
    db.flush()
    db.add(TeamMember(team_id=t.id, user_id=user.id, role="admin"))
    db.commit()
    return {"id": t.id, "name": t.name}


class MemberAdd(BaseModel):
    user_id: int
    role: str = "member"

@router.post("/api/teams/{tid}/members", status_code=201)
def add_member(tid: int, payload: MemberAdd, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(Team, tid)
    if t is None:
        raise HTTPException(404, "Team not found")
    existing = db.scalar(select(TeamMember).where(TeamMember.team_id == tid, TeamMember.user_id == payload.user_id))
    if existing:
        existing.role = payload.role
    else:
        db.add(TeamMember(team_id=tid, user_id=payload.user_id, role=payload.role))
    db.commit()
    return {"ok": True}


class ProjectAccessGrant(BaseModel):
    project_id: int
    permission: str = "read"

@router.post("/api/teams/{tid}/projects", status_code=201)
def grant_project_access(tid: int, payload: ProjectAccessGrant, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(TeamProjectAccess).where(TeamProjectAccess.team_id == tid, TeamProjectAccess.project_id == payload.project_id))
    if existing:
        existing.permission = payload.permission
    else:
        db.add(TeamProjectAccess(team_id=tid, project_id=payload.project_id, permission=payload.permission))
    db.commit()
    return {"ok": True}
