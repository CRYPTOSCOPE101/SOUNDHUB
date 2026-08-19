"""Producer Dashboard — analytics and insights for music projects."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    ActivityEvent,
    Branch,
    Commit,
    Project,
    PullRequest,
    ReviewApproval,
    ReviewComment,
    ReviewSession,
    ReviewVersion,
    User,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get producer dashboard with analytics across all projects."""
    projects = db.scalars(select(Project).where(Project.owner_id == user.id)).all()
    project_ids = [p.id for p in projects]

    # Project stats
    total_projects = len(projects)
    total_commits = db.scalar(select(func.count(Commit.id)).where(Commit.project_id.in_(project_ids))) or 0
    total_branches = db.scalar(select(func.count(Branch.id)).where(Branch.project_id.in_(project_ids))) or 0

    # Review stats
    sessions = db.scalars(select(ReviewSession).where(ReviewSession.owner_id == user.id)).all()
    total_sessions = len(sessions)
    session_ids = [s.id for s in sessions]
    total_versions = db.scalar(select(func.count(ReviewVersion.id)).where(ReviewVersion.session_id.in_(session_ids))) or 0
    total_comments = db.scalar(select(func.count(ReviewComment.id)).where(ReviewComment.version_id.in_(
        select(ReviewVersion.id).where(ReviewVersion.session_id.in_(session_ids))
    ))) or 0

    # PR stats
    total_prs = db.scalar(select(func.count(PullRequest.id)).where(PullRequest.project_id.in_(project_ids))) or 0
    open_prs = db.scalar(select(func.count(PullRequest.id)).where(
        PullRequest.project_id.in_(project_ids), PullRequest.status == "open"
    )) or 0
    merged_prs = db.scalar(select(func.count(PullRequest.id)).where(
        PullRequest.project_id.in_(project_ids), PullRequest.status == "merged"
    )) or 0

    # Approval stats
    total_approvals = db.scalar(select(func.count(ReviewApproval.id)).where(
        ReviewApproval.session_id.in_(session_ids)
    )) or 0

    # Sessions by status
    status_counts = {}
    for s in sessions:
        status_counts[s.status] = status_counts.get(s.status, 0) + 1

    return {
        "user": user.username,
        "projects": {
            "total": total_projects,
            "total_commits": total_commits,
            "total_branches": total_branches,
        },
        "reviews": {
            "total_sessions": total_sessions,
            "total_versions": total_versions,
            "total_comments": total_comments,
            "total_approvals": total_approvals,
            "sessions_by_status": status_counts,
        },
        "pull_requests": {
            "total": total_prs,
            "open": open_prs,
            "merged": merged_prs,
        },
        "recent_activity": [
            {
                "type": a.event_type,
                "detail": a.detail,
                "created_at": a.created_at.isoformat(),
            }
            for a in db.scalars(
                select(ActivityEvent)
                .where(ActivityEvent.user_id == user.id)
                .order_by(ActivityEvent.created_at.desc())
                .limit(10)
            ).all()
        ],
    }


@router.get("/projects/{project_id}")
def get_project_dashboard(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get detailed analytics for a specific project."""
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        from fastapi import HTTPException
        raise HTTPException(404, "Project not found")

    commits = db.scalars(select(Commit).where(Commit.project_id == project_id)).all()
    branches = db.scalars(select(Branch).where(Branch.project_id == project_id)).all()
    prs = db.scalars(select(PullRequest).where(PullRequest.project_id == project_id)).all()

    # Commits per branch
    branch_activity = {}
    for b in branches:
        count = sum(1 for c in commits if c.project_id == project_id)
        branch_activity[b.name] = count

    return {
        "project": project.name,
        "commits": {
            "total": len(commits),
            "by_branch": branch_activity,
        },
        "branches": {
            "total": len(branches),
            "list": [{"name": b.name, "is_default": b.is_default} for b in branches],
        },
        "pull_requests": {
            "total": len(prs),
            "open": sum(1 for p in prs if p.status == "open"),
            "merged": sum(1 for p in prs if p.status == "merged"),
            "closed": sum(1 for p in prs if p.status == "closed"),
        },
    }
