"""Versioning: full-snapshot commits.

An MVP commit stores a complete snapshot of the project tree.
Each file is stored content-addressed (deduplicated), so snapshots
cost almost nothing when nothing changed.
"""
from sqlalchemy.orm import Session

from ..models import Commit, FileSnapshot, Project, User
from . import storage


def create_commit(
    db: Session,
    project: Project,
    author: User,
    message: str,
    files: dict[str, bytes],
) -> Commit:
    """Create a commit from a full tree mapping {path: bytes}."""
    parent = (
        db.query(Commit)
        .filter(Commit.project_id == project.id)
        .order_by(Commit.id.desc())
        .first()
    )
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

    db.add(project)
    db.commit()
    db.refresh(commit)
    return commit


def get_commit(db: Session, project: Project, commit_id: int | None) -> Commit:
    if commit_id is not None:
        commit = db.get(Commit, commit_id)
        if commit is None or commit.project_id != project.id:
            raise LookupError("Commit not found")
        return commit
    commit = (
        db.query(Commit)
        .filter(Commit.project_id == project.id)
        .order_by(Commit.id.desc())
        .first()
    )
    if commit is None:
        raise LookupError("Project has no commits yet")
    return commit


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
