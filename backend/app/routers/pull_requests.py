"""Pull Requests — GitHub-style merge requests for music projects."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Branch,
    Commit,
    Project,
    PullRequest,
    PullRequestComment,
    PullRequestLabel,
    PullRequestReview,
    User,
    utcnow,
)
from ..schemas import (
    PullRequestCommentCreate,
    PullRequestCommentOut,
    PullRequestCreate,
    PullRequestOut,
    PullRequestReviewCreate,
    PullRequestReviewOut,
    PullRequestUpdate,
    UserOut,
)
from ..security import get_current_user

router = APIRouter(prefix="/api/projects/{project_id}/pull-requests", tags=["pull requests"])


def _get_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _get_pr(db: Session, project_id: int, pr_id: int) -> PullRequest:
    pr = db.get(PullRequest, pr_id)
    if pr is None or pr.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pull request not found")
    return pr


def _pr_out(db: Session, pr: PullRequest) -> PullRequestOut:
    author = db.get(User, pr.author_id)
    reviews = db.scalars(select(PullRequestReview).where(PullRequestReview.pull_request_id == pr.id)).all()
    comments = db.scalars(select(PullRequestComment).where(PullRequestComment.pull_request_id == pr.id)).all()
    labels = db.scalars(select(PullRequestLabel).where(PullRequestLabel.pull_request_id == pr.id)).all()
    approvals = sum(1 for r in reviews if r.decision == "approve")
    return PullRequestOut(
        id=pr.id,
        project_id=pr.project_id,
        author=UserOut.model_validate(author, from_attributes=True) if author else UserOut(id=0, username="deleted", created_at=pr.created_at),
        source_branch=pr.source_branch,
        target_branch=pr.target_branch,
        title=pr.title,
        description=pr.description,
        status=pr.status,
        review_count=len(reviews),
        approval_count=approvals,
        comment_count=len(comments),
        labels=[l.name for l in labels],
        merge_commit_id=pr.merge_commit_id,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
    )


@router.get("", response_model=list[PullRequestOut])
def list_prs(
    project_id: int,
    status_filter: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    query = select(PullRequest).where(PullRequest.project_id == project_id)
    if status_filter:
        query = query.where(PullRequest.status == status_filter)
    prs = db.scalars(query.order_by(PullRequest.created_at.desc())).all()
    return [_pr_out(db, pr) for pr in prs]


@router.post("", response_model=PullRequestOut, status_code=status.HTTP_201_CREATED)
def create_pr(
    project_id: int,
    payload: PullRequestCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)

    # Validate branches exist
    source = db.scalar(select(Branch).where(Branch.project_id == project_id, Branch.name == payload.source_branch))
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Source branch '{payload.source_branch}' not found")
    target = db.scalar(select(Branch).where(Branch.project_id == project_id, Branch.name == payload.target_branch))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Target branch '{payload.target_branch}' not found")

    pr = PullRequest(
        project_id=project_id,
        author_id=user.id,
        source_branch=payload.source_branch,
        target_branch=payload.target_branch,
        title=payload.title,
        description=payload.description,
    )
    db.add(pr)
    db.flush()

    for label_name in payload.labels[:10]:
        db.add(PullRequestLabel(pull_request_id=pr.id, name=label_name))

    db.commit()
    db.refresh(pr)
    return _pr_out(db, pr)


@router.get("/{pr_id}", response_model=PullRequestOut)
def get_pr(project_id: int, pr_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_project(db, project_id, user)
    return _pr_out(db, _get_pr(db, project_id, pr_id))


@router.patch("/{pr_id}", response_model=PullRequestOut)
def update_pr(
    project_id: int, pr_id: int, payload: PullRequestUpdate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    pr = _get_pr(db, project_id, pr_id)
    if payload.title is not None:
        pr.title = payload.title
    if payload.description is not None:
        pr.description = payload.description
    if payload.status is not None:
        pr.status = payload.status
        if payload.status == "merged":
            pr.merged_at = utcnow()
        elif payload.status == "closed":
            pr.closed_at = utcnow()
    pr.updated_at = utcnow()
    db.commit()
    return _pr_out(db, pr)


@router.post("/{pr_id}/merge", response_model=PullRequestOut)
def merge_pr(
    project_id: int, pr_id: int,
    strategy: str = Query("merge", pattern=r"^(merge|squash|fast_forward)$"),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Merge a pull request into the target branch."""
    _get_project(db, project_id, user)
    pr = _get_pr(db, project_id, pr_id)

    if pr.status not in ("open", "draft"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PR is not open")

    # Check approvals
    reviews = db.scalars(select(PullRequestReview).where(PullRequestReview.pull_request_id == pr.id)).all()
    approvals = sum(1 for r in reviews if r.decision == "approve")
    if approvals == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PR needs at least 1 approval to merge")

    # Perform merge via the projects merge logic
    from .projects import _get_branch, _collect_tree, _merge_trees
    source = _get_branch(db, project_id, pr.source_branch)
    target = _get_branch(db, project_id, pr.target_branch)

    if source.head_commit_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Source branch has no commits")

    if strategy == "fast_forward":
        target.head_commit_id = source.head_commit_id
    else:
        source_tree = _collect_tree(db, source.head_commit_id)
        target_tree = _collect_tree(db, target.head_commit_id)
        merged, conflicts = _merge_trees(target_tree, source_tree)
        if conflicts:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Conflicts: {', '.join(conflicts[:5])}")

        commit = Commit(
            project_id=project_id, author_id=user.id,
            parent_id=target.head_commit_id,
            message=f"Merge PR #{pr.id}: {pr.title}",
        )
        db.add(commit)
        db.flush()
        from ..models import FileSnapshot
        for path, snap in merged.items():
            db.add(FileSnapshot(commit_id=commit.id, path=path, blob_sha=snap.blob_sha, size=snap.size))
        target.head_commit_id = commit.id
        pr.merge_commit_id = commit.id

    pr.status = "merged"
    pr.merged_at = utcnow()
    pr.updated_at = utcnow()
    db.commit()
    return _pr_out(db, pr)


@router.post("/{pr_id}/reviews", response_model=PullRequestReviewOut, status_code=status.HTTP_201_CREATED)
def add_review(
    project_id: int, pr_id: int, payload: PullRequestReviewCreate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    pr = _get_pr(db, project_id, pr_id)
    review = PullRequestReview(
        pull_request_id=pr.id, reviewer_id=user.id,
        reviewer_name=user.username, decision=payload.decision, body=payload.body,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return PullRequestReviewOut(
        id=review.id,
        reviewer=UserOut.model_validate(user, from_attributes=True),
        reviewer_name=user.username,
        decision=review.decision, body=review.body, created_at=review.created_at,
    )


@router.get("/{pr_id}/reviews", response_model=list[PullRequestReviewOut])
def list_reviews(
    project_id: int, pr_id: int,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    _get_pr(db, project_id, pr_id)
    reviews = db.scalars(select(PullRequestReview).where(PullRequestReview.pull_request_id == pr_id)).all()
    return [
        PullRequestReviewOut(
            id=r.id,
            reviewer=UserOut.model_validate(db.get(User, r.reviewer_id), from_attributes=True) if r.reviewer_id else None,
            reviewer_name=r.reviewer_name, decision=r.decision, body=r.body, created_at=r.created_at,
        ) for r in reviews
    ]


@router.post("/{pr_id}/comments", response_model=PullRequestCommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    project_id: int, pr_id: int, payload: PullRequestCommentCreate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    _get_pr(db, project_id, pr_id)
    comment = PullRequestComment(
        pull_request_id=pr_id, author_id=user.id,
        author_name=user.username, body=payload.body,
        path=payload.path, time_s=payload.time_s, parent_id=payload.parent_id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return PullRequestCommentOut(
        id=comment.id,
        author=UserOut.model_validate(user, from_attributes=True),
        author_name=user.username, body=comment.body,
        path=comment.path, time_s=comment.time_s,
        resolved=comment.resolved, parent_id=comment.parent_id,
        created_at=comment.created_at,
    )


@router.get("/{pr_id}/comments", response_model=list[PullRequestCommentOut])
def list_comments(
    project_id: int, pr_id: int,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    comments = db.scalars(select(PullRequestComment).where(PullRequestComment.pull_request_id == pr_id)).all()
    return [
        PullRequestCommentOut(
            id=c.id,
            author=UserOut.model_validate(db.get(User, c.author_id), from_attributes=True) if c.author_id else None,
            author_name=c.author_name, body=c.body,
            path=c.path, time_s=c.time_s, resolved=c.resolved,
            parent_id=c.parent_id, created_at=c.created_at,
        ) for c in comments
    ]
