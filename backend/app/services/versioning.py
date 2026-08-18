"""File snapshot and tree navigation for project versioning."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Commit, FileSnapshot


def tree_files(db: Session, commit: Commit) -> list[FileSnapshot]:
    """Get all file snapshots for a commit."""
    return list(
        db.scalars(
            select(FileSnapshot).where(FileSnapshot.commit_id == commit.id)
        ).all()
    )


def file_in_commit(db: Session, commit: Commit | None, path: str) -> FileSnapshot | None:
    """Find a file snapshot by path in a specific commit."""
    if commit is None:
        return None
    return db.scalar(
        select(FileSnapshot).where(
            FileSnapshot.commit_id == commit.id,
            FileSnapshot.path == path,
        )
    )


def file_history(db: Session, project_id: int, path: str) -> list[dict]:
    """Get the history of a file across commits."""
    results = (
        db.query(FileSnapshot, Commit)
        .join(Commit, FileSnapshot.commit_id == Commit.id)
        .filter(Commit.project_id == project_id, FileSnapshot.path == path)
        .order_by(Commit.created_at.desc())
        .all()
    )
    return [
        {
            "commit_id": commit.id,
            "path": snap.path,
            "blob_sha": snap.blob_sha,
            "size": snap.size,
            "message": commit.message,
            "created_at": commit.created_at.isoformat(),
        }
        for snap, commit in results
    ]
