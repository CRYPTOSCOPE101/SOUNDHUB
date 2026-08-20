"""Branch protection rules — GitHub-style protection for branches."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BranchProtection, Project, User, utcnow
from ..schemas import BranchProtectionCreate, BranchProtectionOut, BranchProtectionUpdate
from ..security import get_current_user

router = APIRouter(prefix="/api/projects/{project_id}/protection", tags=["branch protection"])


def _get_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _get_protection(db: Session, project_id: int, branch_name: str) -> BranchProtection:
    p = db.scalar(
        select(BranchProtection).where(
            BranchProtection.project_id == project_id,
            BranchProtection.branch_name == branch_name,
        )
    )
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No protection rules for this branch")
    return p


@router.get("", response_model=list[BranchProtectionOut])
def list_protections(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all branch protection rules for a project."""
    _get_project(db, project_id, user)
    rules = db.scalars(
        select(BranchProtection).where(BranchProtection.project_id == project_id)
    ).all()
    return [BranchProtectionOut.model_validate(r, from_attributes=True) for r in rules]


@router.post("", response_model=BranchProtectionOut, status_code=status.HTTP_201_CREATED)
def create_protection(
    project_id: int,
    payload: BranchProtectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or replace protection rules for a branch."""
    _get_project(db, project_id, user)

    existing = db.scalar(
        select(BranchProtection).where(
            BranchProtection.project_id == project_id,
            BranchProtection.branch_name == payload.branch_name,
        )
    )
    if existing:
        # Update existing
        existing.require_pull_request = payload.require_pull_request
        existing.required_reviewers = payload.required_reviewers
        existing.require_status_checks = payload.require_status_checks
        existing.restrict_pushes = payload.restrict_pushes
        existing.allow_force_push = payload.allow_force_push
        existing.allow_deletions = payload.allow_deletions
        existing.updated_at = utcnow()
        db.commit()
        db.refresh(existing)
        return BranchProtectionOut.model_validate(existing, from_attributes=True)

    rule = BranchProtection(
        project_id=project_id,
        branch_name=payload.branch_name,
        require_pull_request=payload.require_pull_request,
        required_reviewers=payload.required_reviewers,
        require_status_checks=payload.require_status_checks,
        restrict_pushes=payload.restrict_pushes,
        allow_force_push=payload.allow_force_push,
        allow_deletions=payload.allow_deletions,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return BranchProtectionOut.model_validate(rule, from_attributes=True)


@router.patch("/{branch_name}", response_model=BranchProtectionOut)
def update_protection(
    project_id: int,
    branch_name: str,
    payload: BranchProtectionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partially update protection rules for a branch."""
    _get_project(db, project_id, user)
    rule = _get_protection(db, project_id, branch_name)

    if payload.require_pull_request is not None:
        rule.require_pull_request = payload.require_pull_request
    if payload.required_reviewers is not None:
        rule.required_reviewers = payload.required_reviewers
    if payload.require_status_checks is not None:
        rule.require_status_checks = payload.require_status_checks
    if payload.restrict_pushes is not None:
        rule.restrict_pushes = payload.restrict_pushes
    if payload.allow_force_push is not None:
        rule.allow_force_push = payload.allow_force_push
    if payload.allow_deletions is not None:
        rule.allow_deletions = payload.allow_deletions

    rule.updated_at = utcnow()
    db.commit()
    db.refresh(rule)
    return BranchProtectionOut.model_validate(rule, from_attributes=True)


@router.delete("/{branch_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_protection(
    project_id: int,
    branch_name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove protection rules from a branch."""
    _get_project(db, project_id, user)
    rule = _get_protection(db, project_id, branch_name)
    db.delete(rule)
    db.commit()
