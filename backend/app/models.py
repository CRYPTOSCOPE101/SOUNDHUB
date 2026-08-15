"""ORM models for SoundHub."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    wallet_address: Mapped[str | None] = mapped_column(String(42), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    slug: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    default_branch: Mapped[str] = mapped_column(String(64), default="main")
    # on-chain release NFT binding (SoundHubRelease token)
    release_token_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    release_contract: Mapped[str | None] = mapped_column(String(42), nullable=True)
    release_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    __table_args__ = (UniqueConstraint("owner_id", "slug", name="uq_project_owner_slug"),)

    owner: Mapped["User"] = relationship(back_populates="projects")
    commits: Mapped[list["Commit"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    branches: Mapped[list["Branch"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Branch(Base):
    """A named pointer to a commit (git-like). History of a branch is the
    parent chain walked from `head_commit_id`."""

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    head_commit_id: Mapped[int | None] = mapped_column(ForeignKey("commits.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_project_branch_name"),)

    project: Mapped["Project"] = relationship(back_populates="branches")

    @property
    def is_default(self) -> bool:
        return self.name == self.project.default_branch


class Commit(Base):
    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("commits.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped["Project"] = relationship(back_populates="commits")
    author: Mapped["User"] = relationship()
    files: Mapped[list["FileSnapshot"]] = relationship(
        back_populates="commit", cascade="all, delete-orphan"
    )


class FileSnapshot(Base):
    __tablename__ = "file_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commit_id: Mapped[int] = mapped_column(ForeignKey("commits.id"), index=True)
    path: Mapped[str] = mapped_column(String(1024))
    blob_sha: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(Integer, default=0)

    commit: Mapped["Commit"] = relationship(back_populates="files")

    __table_args__ = (UniqueConstraint("commit_id", "path", name="uq_commit_path"),)


class ReviewSession(Base):
    """A review workspace for a track: versions to share, comments, approvals."""

    __tablename__ = "review_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="in_review")
    share_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped["User"] = relationship()
    versions: Mapped[list["ReviewVersion"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["ReviewApproval"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    access_events: Mapped[list["ShareAccessEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    rounds: Mapped[list["ReviewRound"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    # Share-link settings (professional review links)
    share_password: Mapped[str | None] = mapped_column(String(256), nullable=True)
    share_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    share_permission: Mapped[str] = mapped_column(String(32), default="comment")  # comment | view | download
    share_allowlist: Mapped[str] = mapped_column(Text, default="")  # comma-separated emails

    # Mix review rounds (controlled revisions)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    feedback_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback_owner: Mapped[str] = mapped_column(String(128), default="")  # who consolidates draft notes
    included_rounds: Mapped[int] = mapped_column(Integer, default=1)  # paid/included rounds
    rounds_open: Mapped[bool] = mapped_column(default=True)  # can clients still add notes?


class ReviewVersion(Base):
    __tablename__ = "review_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    number: Mapped[int] = mapped_column(Integer, default=1)  # 1-based, human label v{n}
    label: Mapped[str] = mapped_column(String(64))  # e.g. "v13"
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="in_review")
    filename: Mapped[str] = mapped_column(String(256))
    blob_sha: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[float] = mapped_column(default=0.0)
    audio_format: Mapped[str] = mapped_column(String(16), default="wav")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    round_number: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (UniqueConstraint("session_id", "number", name="uq_review_version_number"),)

    session: Mapped["ReviewSession"] = relationship(back_populates="versions")
    comments: Mapped[list["ReviewComment"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        foreign_keys="ReviewComment.version_id",
    )


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(128), nullable=True)  # guest reviewers
    time_s: Mapped[float] = mapped_column(default=0.0)  # seconds into the track
    body: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(default=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("review_comments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    version: Mapped["ReviewVersion"] = relationship(
        back_populates="comments", foreign_keys=[version_id]
    )
    author: Mapped["User"] = relationship()

    # request lifecycle: draft → open → acknowledged → in_progress → fixed → verified → approved
    status: Mapped[str] = mapped_column(String(32), default="open")
    fixed_in: Mapped[int | None] = mapped_column(ForeignKey("review_versions.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewRound(Base):
    """A closed revision round: one consolidated list of change requests.

    Round 1 = initial mix review. Submitting feedback consolidates draft notes
    into open requests and increments the round; the next version belongs to
    the new round.
    """

    __tablename__ = "review_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | submitted | closed
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    request_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("session_id", "number", name="uq_review_round_number"),)

    session: Mapped["ReviewSession"] = relationship(back_populates="rounds")


class ReviewApproval(Base):
    """An approval decision on a version: a verifiable artifact, not just a badge.

    scope: mix | master | arrangement | release. A "needs_changes" decision is
    also stored here (approved=False) so the history is complete.
    """

    __tablename__ = "review_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"), index=True)
    scope: Mapped[str] = mapped_column(String(32), default="mix")
    approved: Mapped[bool] = mapped_column(default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    approver_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ReviewSession"] = relationship(back_populates="approvals")
    version: Mapped["ReviewVersion"] = relationship()


class ShareAccessEvent(Base):
    """Audit trail for a share link: who opened, downloaded, commented, approved."""

    __tablename__ = "share_access_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    actor: Mapped[str] = mapped_column(String(128), default="")  # email or username
    action: Mapped[str] = mapped_column(String(32))  # opened | commented | downloaded | approved
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ReviewSession"] = relationship(back_populates="access_events")
