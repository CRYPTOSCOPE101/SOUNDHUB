"""Versioning: full-snapshot commits + git-like branches.

An MVP commit stores a complete snapshot of the project tree. Each file is
stored content-addressed (deduplicated), so snapshots cost almost nothing
when little changed. Commits form a single-parent chain (a DAG with merges
is roadmap work); a **branch** is a named pointer to a commit, and the
history of a branch is the parent chain walked from its head.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Branch, Commit, FileSnapshot, Project, User
from . import storage


def create_commit(
    db: Session,
    project: Project,
    author: User,
    message: str,
    files: dict[str, bytes],
    branch: str = "main",
    commit_transaction: bool = True,
) -> Commit:
    """Create a commit from a full tree mapping {path: bytes} on `branch`.

    With `commit_transaction=False` the commit rows are flushed but not
    committed, so the caller can create the review version + stems in the
    SAME transaction and commit once — a failed push never leaves a
    half-pushed version visible to anyone.
    """
    parent = head_commit(db, project, branch)
    commit = Commit(
        project_id=project.id,
        author_id=author.id,
        parent_id=parent.id if parent else None,
        message=message,
    )
    db.add(commit)
    db.flush()

    for path in sorted(files):
        data = files[path]
        sha = storage.put_blob(data)
        db.add(
            FileSnapshot(
                commit_id=commit.id,
                path=path,
                blob_sha=sha,
                size=len(data),
            )
        )

    # point the branch at the new head (create the branch if it's new)
    branch_row = db.scalar(
        select(Branch).where(Branch.project_id == project.id, Branch.name == branch)
    )
    if branch_row is None:
        branch_row = Branch(project_id=project.id, name=branch)
        db.add(branch_row)
    branch_row.head_commit_id = commit.id

    if commit_transaction:
        db.commit()
        db.refresh(commit)
    return commit


def ensure_branch(db: Session, project: Project, branch: str) -> Branch:
    """Return the branch row, synthesizing it if missing.

    The default branch may exist in commits but not yet as a pointer (legacy
    data); any other branch name is created empty so a first push to a fresh
    branch (e.g. `snd push … --branch review/v12`) resolves cleanly.
    """
    row = db.scalar(
        select(Branch).where(Branch.project_id == project.id, Branch.name == branch)
    )
    if row is not None:
        return row
    head = (
        db.query(Commit)
        .filter(Commit.project_id == project.id)
        .order_by(Commit.id.desc())
        .first()
    )
    row = Branch(
        project_id=project.id,
        name=branch,
        head_commit_id=head.id if head else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def head_commit(db: Session, project: Project, branch: str) -> Commit | None:
    row = ensure_branch(db, project, branch)
    if row.head_commit_id is None:
        return None
    commit = db.get(Commit, row.head_commit_id)
    if commit is None or commit.project_id != project.id:
        return None
    return commit


def get_commit(db: Session, project: Project, commit_id: int | None, branch: str | None = None) -> Commit:
    if commit_id is not None:
        commit = db.get(Commit, commit_id)
        if commit is None or commit.project_id != project.id:
            raise LookupError("Commit not found")
        return commit
    branch = branch or project.default_branch
    commit = head_commit(db, project, branch)
    if commit is None:
        raise LookupError(f"Project has no commits on branch '{branch}'")
    return commit


def iter_commits(db: Session, project: Project, branch: str | None = None, limit: int | None = None) -> list[Commit]:
    """Walk the parent chain from the branch head (newest first)."""
    branch = branch or project.default_branch
    out: list[Commit] = []
    commit = head_commit(db, project, branch)
    seen: set[int] = set()
    while commit is not None and commit.id not in seen:
        seen.add(commit.id)
        out.append(commit)
        if limit is not None and len(out) >= limit:
            break
        commit = db.get(Commit, commit.parent_id) if commit.parent_id else None
    return out


def list_branches(db: Session, project: Project) -> list[dict]:
    """All branches with head info and commit counts (newest head first)."""
    rows = db.scalars(
        select(Branch).where(Branch.project_id == project.id).order_by(Branch.name)
    ).all()
    out: list[dict] = []
    for row in rows:
        head = db.get(Commit, row.head_commit_id) if row.head_commit_id else None
        out.append(
            {
                "name": row.name,
                "is_default": row.name == project.default_branch,
                "head_commit_id": head.id if head else None,
                "head_message": head.message if head else "",
                "head_sha": _short_sha(head) if head else None,
                "head_author": head.author.username if head and head.author else "",
                "head_date": head.created_at if head else None,
                "commit_count": len(iter_commits(db, project, row.name)),
                "created_at": row.created_at,
            }
        )
    return sorted(out, key=lambda b: (not b["is_default"], b["name"]))


def create_branch(db: Session, project: Project, name: str, from_branch: str | None = None) -> Branch:
    """Create a branch pointing at the head of `from_branch` (default branch)."""
    src = from_branch or project.default_branch
    head = head_commit(db, project, src)
    if head is None:
        raise LookupError(f"Branch '{src}' has no commits to branch from")
    row = Branch(
        project_id=project.id,
        name=name,
        head_commit_id=head.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_branch(db: Session, project: Project, name: str) -> bool:
    if name == project.default_branch:
        raise ValueError("Cannot delete the default branch")
    row = db.scalar(
        select(Branch).where(Branch.project_id == project.id, Branch.name == name)
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def _short_sha(commit: Commit) -> str:
    return f"{commit.id:08x}"[:7]


def get_tree(db: Session, commit: Commit) -> dict[str, FileSnapshot]:
    return {f.path: f for f in db.query(FileSnapshot).filter(FileSnapshot.commit_id == commit.id)}


def tree_files(db: Session, commit: Commit) -> list[FileSnapshot]:
    return db.query(FileSnapshot).filter(FileSnapshot.commit_id == commit.id).all()


def file_in_commit(db: Session, commit: Commit, path: str) -> FileSnapshot | None:
    return (
        db.query(FileSnapshot)
        .filter(FileSnapshot.commit_id == commit.id, FileSnapshot.path == path)
        .first()
    )
