"""ORM models for SoundHub."""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    bio: Mapped[str] = mapped_column(Text, default="")
    specialty: Mapped[str] = mapped_column(String(64), default="")
    location: Mapped[str] = mapped_column(String(128), default="")

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    slug: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    default_branch: Mapped[str] = mapped_column(String(64), default="main")
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
    release_packages: Mapped[list["ReleasePackage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    references: Mapped[list["ReferenceTrack"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    members: Mapped[list["SessionMember"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    change_orders: Mapped[list["ChangeOrder"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    # Team roles & approval chain
    approval_preset: Mapped[str] = mapped_column(String(32), default="solo_client")

    # Share-link settings
    share_password: Mapped[str | None] = mapped_column(String(256), nullable=True)
    share_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    share_permission: Mapped[str] = mapped_column(String(32), default="comment")
    share_allowlist: Mapped[str] = mapped_column(Text, default="")

    # Mix review rounds
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    feedback_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback_owner: Mapped[str] = mapped_column(String(128), default="")
    included_rounds: Mapped[int] = mapped_column(Integer, default=1)
    rounds_open: Mapped[bool] = mapped_column(default=True)

    # Booking deposit
    deposit_due_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_status: Mapped[str] = mapped_column(String(32), default="none")

    # Paid extra revision rounds
    extra_round_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rounds_paid: Mapped[int] = mapped_column(Integer, default=0)

    # Public portfolio + preview protection
    portfolio_public: Mapped[bool] = mapped_column(default=False)
    watermark_enabled: Mapped[bool] = mapped_column(default=True)

    # Client brief
    service_type: Mapped[str] = mapped_column(String(32), default="mix")
    genre: Mapped[str] = mapped_column(String(128), default="")
    goal: Mapped[str] = mapped_column(String(64), default="")
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference_links: Mapped[str] = mapped_column(Text, default="")
    do_not_change: Mapped[str] = mapped_column(Text, default="")
    required_deliverables: Mapped[str] = mapped_column(Text, default="")

    # Late-change protection
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recall_fee_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revision_fee_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change_rounds_granted: Mapped[int] = mapped_column(Integer, default=0)

    # Reminder automation
    reminders_enabled: Mapped[bool] = mapped_column(default=True)
    reminder_categories: Mapped[str] = mapped_column(Text, default="")
    reminders_client_opt_out: Mapped[bool] = mapped_column(default=False)
    client_email: Mapped[str] = mapped_column(String(256), default="")


class ReviewVersion(Base):
    __tablename__ = "review_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    number: Mapped[int] = mapped_column(Integer, default=1)
    label: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="in_review")
    filename: Mapped[str] = mapped_column(String(256))
    blob_sha: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[float] = mapped_column(default=0.0)
    audio_format: Mapped[str] = mapped_column(String(16), default="wav")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    watermark_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commit_id: Mapped[int | None] = mapped_column(ForeignKey("commits.id"), nullable=True, index=True)

    __table_args__ = (UniqueConstraint("session_id", "number", name="uq_review_version_number"),)

    session: Mapped["ReviewSession"] = relationship(back_populates="versions")
    comments: Mapped[list["ReviewComment"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        foreign_keys="ReviewComment.version_id",
    )
    stems: Mapped[list["StemAsset"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class SessionMember(Base):
    __tablename__ = "session_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    email: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32))
    invited_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("session_id", "email", name="uq_session_member_email"),)

    session: Mapped["ReviewSession"] = relationship(back_populates="members")


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    time_s: Mapped[float] = mapped_column(default=0.0)
    body: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(default=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("review_comments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    voice_blob_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    voice_format: Mapped[str] = mapped_column(String(16), default="")
    voice_duration_s: Mapped[float] = mapped_column(default=0.0)
    transcript: Mapped[str] = mapped_column(Text, default="")

    version: Mapped["ReviewVersion"] = relationship(
        back_populates="comments", foreign_keys=[version_id]
    )
    author: Mapped["User"] = relationship()

    status: Mapped[str] = mapped_column(String(32), default="open")
    fixed_in: Mapped[int | None] = mapped_column(ForeignKey("review_versions.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewRound(Base):
    __tablename__ = "review_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="open")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    request_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("session_id", "number", name="uq_review_round_number"),)

    session: Mapped["ReviewSession"] = relationship(back_populates="rounds")


class ChangeOrder(Base):
    __tablename__ = "change_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    created_by: Mapped[str] = mapped_column(String(128), default="")
    reason: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="requested")
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="usd")
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_round: Mapped[int] = mapped_column(Integer, default=1)
    round_granted: Mapped[bool] = mapped_column(default=False)
    quoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quote_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quote_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ReviewSession"] = relationship(back_populates="change_orders")


class ReferenceTrack(Base):
    __tablename__ = "reference_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    artist: Mapped[str] = mapped_column(String(128), default="")
    source_type: Mapped[str] = mapped_column(String(16))
    external_url: Mapped[str] = mapped_column(String(2000), default="")
    blob_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filename: Mapped[str] = mapped_column(String(256), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    audio_format: Mapped[str] = mapped_column(String(16), default="")
    duration_s: Mapped[float] = mapped_column(default=0.0)
    purpose: Mapped[str] = mapped_column(String(32), default="overall")
    visibility: Mapped[str] = mapped_column(String(32), default="reviewers")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    integrated_lufs: Mapped[float | None] = mapped_column(nullable=True)
    true_peak_dbtp: Mapped[float | None] = mapped_column(nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(16), default="pending")

    session: Mapped["ReviewSession"] = relationship(back_populates="references")


class ReferenceComparison(Base):
    __tablename__ = "reference_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"))
    reference_id: Mapped[int] = mapped_column(ForeignKey("reference_tracks.id"))
    start_ms: Mapped[int] = mapped_column(Integer, default=0)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mix_gain_db: Mapped[float] = mapped_column(default=0.0)
    ref_gain_db: Mapped[float] = mapped_column(default=0.0)
    level_match: Mapped[str] = mapped_column(String(32), default="none")
    short_term_lufs: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ReviewSession"] = relationship()
    version: Mapped["ReviewVersion"] = relationship()
    reference: Mapped["ReferenceTrack"] = relationship()


class ReviewApproval(Base):
    __tablename__ = "review_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"), index=True)
    scope: Mapped[str] = mapped_column(String(32), default="mix")
    approved: Mapped[bool] = mapped_column(default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    approver_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ReviewSession"] = relationship(back_populates="approvals")
    version: Mapped["ReviewVersion"] = relationship()


class ShareAccessEvent(Base):
    __tablename__ = "share_access_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    actor: Mapped[str] = mapped_column(String(128), default="")
    action: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ReviewSession"] = relationship(back_populates="access_events")


class StemAsset(Base):
    __tablename__ = "stem_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"), index=True)
    logical_name: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(128))
    blob_sha: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    audio_format: Mapped[str] = mapped_column(String(16), default="wav")
    start_offset_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    version: Mapped["ReviewVersion"] = relationship(back_populates="stems")


class AudioAnalysis(Base):
    __tablename__ = "audio_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"), unique=True, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    integrated_lufs: Mapped[float | None] = mapped_column(nullable=True)
    true_peak_dbtp: Mapped[float | None] = mapped_column(nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(16), default="pending")
    analysed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped["ReviewVersion"] = relationship()


class VersionComparison(Base):
    __tablename__ = "version_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    base_version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"))
    compare_version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"))
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_ms: Mapped[int] = mapped_column(Integer, default=0)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_gain_db: Mapped[float] = mapped_column(default=0.0)
    compare_gain_db: Mapped[float] = mapped_column(default=0.0)
    level_match: Mapped[str] = mapped_column(String(32), default="none")
    short_term_lufs: Mapped[dict] = mapped_column(JSON, default=dict)
    mode: Mapped[str] = mapped_column(String(32), default="full_mix")
    stem_logical_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ReviewSession"] = relationship()
    base_version: Mapped["ReviewVersion"] = relationship(foreign_keys=[base_version_id])
    compare_version: Mapped["ReviewVersion"] = relationship(foreign_keys=[compare_version_id])


class LedgerEvent(Base):
    __tablename__ = "ledger_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event: Mapped[str] = mapped_column(String(48), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("review_sessions.id"), index=True, nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("release_packages.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(128), default="")
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    prev_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64), index=True)

    session: Mapped["ReviewSession"] = relationship()


class ReleasePackage(Base):
    __tablename__ = "release_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    approved_version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"))
    name: Mapped[str] = mapped_column(String(160), default="Final delivery")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    invoice_status: Mapped[str] = mapped_column(String(32), default="none")
    amount_due_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="usd")
    stripe_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    immutable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked_by: Mapped[str] = mapped_column(String(128), default="")
    template: Mapped[str] = mapped_column(String(32), default="custom")
    plugin_manifest: Mapped[str] = mapped_column(Text, default="")
    session_manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    consolidate_audio: Mapped[bool] = mapped_column(default=False)
    archive_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_status: Mapped[str] = mapped_column(String(32), default="available_now")
    last_verified_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invoice_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    force_locked_reason: Mapped[str] = mapped_column(Text, default="")
    force_locked_by: Mapped[str] = mapped_column(String(128), default="")

    session: Mapped["ReviewSession"] = relationship()
    approved_version: Mapped["ReviewVersion"] = relationship()
    deliverables: Mapped[list["Deliverable"]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )
    events: Mapped[list["DeliveryEvent"]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(48))
    channel: Mapped[str] = mapped_column(String(16), default="email")
    recipient: Mapped[str] = mapped_column(String(256), default="")
    subject: Mapped[str] = mapped_column(String(256), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    cta_url: Mapped[str] = mapped_column(String(500), default="")
    cta_label: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    dedup_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ReviewSession"] = relationship(back_populates="notifications")


class Deliverable(Base):
    __tablename__ = "release_deliverables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("release_packages.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(256))
    blob_sha: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    format: Mapped[str] = mapped_column(String(16), default="wav")
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bit_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    integrated_lufs: Mapped[float | None] = mapped_column(nullable=True)
    true_peak: Mapped[float | None] = mapped_column(nullable=True)
    is_required: Mapped[bool] = mapped_column(default=True)
    source_version_id: Mapped[int | None] = mapped_column(ForeignKey("review_versions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    package: Mapped["ReleasePackage"] = relationship(back_populates="deliverables")


class DeliveryEvent(Base):
    __tablename__ = "delivery_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("release_packages.id"), index=True)
    event: Mapped[str] = mapped_column(String(48))
    actor: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    package: Mapped["ReleasePackage"] = relationship(back_populates="events")


# ═══════════════════════════════════════════════════════════════════════════
# Professional features — templates, tags, activity feed, groups, pins, webhooks
# ═══════════════════════════════════════════════════════════════════════════


class SessionTemplate(Base):
    __tablename__ = "session_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    service_type: Mapped[str] = mapped_column(String(32), default="mix_master")
    genre: Mapped[str] = mapped_column(String(64), default="")
    included_rounds: Mapped[int] = mapped_column(Integer, default=2)
    extra_round_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    deposit_due_cents: Mapped[int] = mapped_column(Integer, default=0)
    required_deliverables: Mapped[str] = mapped_column(Text, default="master,instrumental")
    brief_template: Mapped[str] = mapped_column(Text, default="")
    is_public: Mapped[bool] = mapped_column(default=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped["User"] = relationship()


class SessionTag(Base):
    __tablename__ = "session_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str] = mapped_column(String(7), default="#6366f1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_tag_owner_name"),)

    owner: Mapped["User"] = relationship()


class SessionTagLink(Base):
    __tablename__ = "session_tag_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("session_tags.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("session_id", "tag_id", name="uq_session_tag"),)

    session: Mapped["ReviewSession"] = relationship()
    tag: Mapped["SessionTag"] = relationship()


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("review_sessions.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(48))
    actor_name: Mapped[str] = mapped_column(String(128), default="")
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User | None"] = relationship()


class SessionGroup(Base):
    __tablename__ = "session_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("session_groups.id"), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped["User"] = relationship()
    children: Mapped[list["SessionGroup"]] = relationship(back_populates="parent")
    parent: Mapped["SessionGroup | None"] = relationship(back_populates="children", remote_side=[id])


class VersionPin(Base):
    __tablename__ = "version_pins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("review_versions.id"), index=True)
    pinned_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    label: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("session_id", "version_id", name="uq_session_version_pin"),)

    session: Mapped["ReviewSession"] = relationship()
    version: Mapped["ReviewVersion"] = relationship()
    user: Mapped["User"] = relationship()


class SessionGroupLink(Base):
    __tablename__ = "session_group_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("session_groups.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("session_id", "group_id", name="uq_session_group"),)

    session: Mapped["ReviewSession"] = relationship()
    group: Mapped["SessionGroup"] = relationship()


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    url: Mapped[str] = mapped_column(String(512))
    secret: Mapped[str | None] = mapped_column(String(128), nullable=True)
    events: Mapped[str] = mapped_column(Text, default="*")
    is_active: Mapped[bool] = mapped_column(default=True)
    last_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped["User"] = relationship()


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(48))
    payload: Mapped[str] = mapped_column(JSON)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str] = mapped_column(Text, default="")
    success: Mapped[bool] = mapped_column(default=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    webhook: Mapped["Webhook"] = relationship()


# ═══════════════════════════════════════════════════════════════════════════
# Pull Requests — GitHub-style merge requests for music projects
# ═══════════════════════════════════════════════════════════════════════════


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_branch: Mapped[str] = mapped_column(String(64))
    target_branch: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | draft | merged | closed
    merge_commit_id: Mapped[int | None] = mapped_column(ForeignKey("commits.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped["User"] = relationship()
    reviews: Mapped[list["PullRequestReview"]] = relationship(back_populates="pull_request", cascade="all, delete-orphan")
    comments: Mapped[list["PullRequestComment"]] = relationship(back_populates="pull_request", cascade="all, delete-orphan")
    labels: Mapped[list["PullRequestLabel"]] = relationship(back_populates="pull_request", cascade="all, delete-orphan")


class PullRequestReview(Base):
    __tablename__ = "pull_request_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewer_name: Mapped[str] = mapped_column(String(128), default="")
    decision: Mapped[str] = mapped_column(String(32), default="comment")  # comment | approve | request_changes
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    pull_request: Mapped["PullRequest"] = relationship(back_populates="reviews")
    reviewer: Mapped["User | None"] = relationship()


class PullRequestComment(Base):
    __tablename__ = "pull_request_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(128), default="")
    body: Mapped[str] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(String(512), nullable=True)  # file path (optional)
    time_s: Mapped[float | None] = mapped_column(nullable=True)  # timestamp in audio (optional)
    resolved: Mapped[bool] = mapped_column(default=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("pull_request_comments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    pull_request: Mapped["PullRequest"] = relationship(back_populates="comments")
    author: Mapped["User | None"] = relationship()


class PullRequestLabel(Base):
    __tablename__ = "pull_request_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("pull_request_id", "name", name="uq_pr_label"),)
    pull_request: Mapped["PullRequest"] = relationship(back_populates="labels")


# ═══════════════════════════════════════════════════════════════════════════
# Music Tasks — GitHub Issues for music production
# ═══════════════════════════════════════════════════════════════════════════


class MusicTask(Base):
    __tablename__ = "music_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(32), default="task")  # task | bug | feature | question
    priority: Mapped[str] = mapped_column(String(16), default="medium")  # low | medium | high | critical
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | in_progress | done | closed
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    milestone: Mapped[str] = mapped_column(String(128), default="")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    linked_pr_id: Mapped[int | None] = mapped_column(ForeignKey("pull_requests.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped["User"] = relationship(foreign_keys=[author_id])
    assignee: Mapped["User | None"] = relationship(foreign_keys=[assignee_id])
    comments: Mapped[list["TaskComment"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    labels: Mapped[list["TaskLabel"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("music_tasks.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(128), default="")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped["MusicTask"] = relationship(back_populates="comments")
    author: Mapped["User | None"] = relationship()


class TaskLabel(Base):
    __tablename__ = "task_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("music_tasks.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("task_id", "name", name="uq_task_label"),)
    task: Mapped["MusicTask"] = relationship(back_populates="labels")


# ═══════════════════════════════════════════════════════════════════════════
# Tags & Releases — Git-style versioning
# ═══════════════════════════════════════════════════════════════════════════


class GitTag(Base):
    __tablename__ = "git_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    commit_id: Mapped[int] = mapped_column(ForeignKey("commits.id"))
    name: Mapped[str] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_release: Mapped[bool] = mapped_column(default=False)  # true = release tag
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_project_tag"),)
    commit: Mapped["Commit"] = relationship()
    creator: Mapped["User"] = relationship()


class ReleaseNote(Base):
    __tablename__ = "release_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("git_tags.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    highlights: Mapped[str] = mapped_column(Text, default="")  # newline-separated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tag: Mapped["GitTag"] = relationship()


# ═══════════════════════════════════════════════════════════════════════════
# Audio CI Checks — automated quality checks
# ═══════════════════════════════════════════════════════════════════════════


class AudioCheck(Base):
    __tablename__ = "audio_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    commit_id: Mapped[int] = mapped_column(ForeignKey("commits.id"), index=True)
    check_type: Mapped[str] = mapped_column(String(48))  # lufs | true_peak | format | sample_rate | channels
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | pass | fail | warn
    value: Mapped[str] = mapped_column(String(128), default="")  # actual value
    expected: Mapped[str] = mapped_column(String(128), default="")  # expected range
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    commit: Mapped["Commit"] = relationship()


# ═══════════════════════════════════════════════════════════════════════════
# Discussions — forum for projects
# ═══════════════════════════════════════════════════════════════════════════


class Discussion(Base):
    __tablename__ = "discussions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), default="general")
    pinned: Mapped[bool] = mapped_column(default=False)
    locked: Mapped[bool] = mapped_column(default=False)
    answer_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    author: Mapped["User"] = relationship()
    comments: Mapped[list["DiscussionComment"]] = relationship(back_populates="discussion", cascade="all, delete-orphan")


class DiscussionComment(Base):
    __tablename__ = "discussion_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discussion_id: Mapped[int] = mapped_column(ForeignKey("discussions.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(128), default="")
    body: Mapped[str] = mapped_column(Text)
    is_answer: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    discussion: Mapped["Discussion"] = relationship(back_populates="comments")
    author: Mapped["User | None"] = relationship()


# ═══════════════════════════════════════════════════════════════════════════
# Kanban Boards — project management
# ═══════════════════════════════════════════════════════════════════════════


class KanbanBoard(Base):
    __tablename__ = "kanban_boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), default="Release Board")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    columns: Mapped[list["KanbanColumn"]] = relationship(back_populates="board", cascade="all, delete-orphan")


class KanbanColumn(Base):
    __tablename__ = "kanban_columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("kanban_boards.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")

    board: Mapped["KanbanBoard"] = relationship(back_populates="columns")
    cards: Mapped[list["KanbanCard"]] = relationship(back_populates="column", cascade="all, delete-orphan")


class KanbanCard(Base):
    __tablename__ = "kanban_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    column_id: Mapped[int] = mapped_column(ForeignKey("kanban_columns.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    version_id: Mapped[int | None] = mapped_column(ForeignKey("review_versions.id"), nullable=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("music_tasks.id"), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    column: Mapped["KanbanColumn"] = relationship(back_populates="cards")
    assignee: Mapped["User | None"] = relationship()


# ═══════════════════════════════════════════════════════════════════════════
# CODEOWNERS — automatic reviewers for branches/paths
# ═══════════════════════════════════════════════════════════════════════════


class CodeOwner(Base):
    __tablename__ = "code_owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    pattern: Mapped[str] = mapped_column(String(256))  # file path pattern like "*.als" or "stems/"
    owner_username: Mapped[str] = mapped_column(String(64))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "pattern", name="uq_codeowner_pattern"),)


# ═══════════════════════════════════════════════════════════════════════════
# Milestones — release planning
# ═══════════════════════════════════════════════════════════════════════════


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
# Notifications — in-app notifications
# ═══════════════════════════════════════════════════════════════════════════


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(48))  # pr.review | task.assigned | comment | etc
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Watch/Star/Fork — social features
# ═══════════════════════════════════════════════════════════════════════════


class ProjectStar(Base):
    __tablename__ = "project_stars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_star"),)


class ProjectWatch(Base):
    __tablename__ = "project_watches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    level: Mapped[str] = mapped_column(String(32), default="all")  # all | participating | ignore
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_watch"),)


class ProjectFork(Base):
    __tablename__ = "project_forks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    forked_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Secrets — secure key storage for CI/CD
# ═══════════════════════════════════════════════════════════════════════════


class ProjectSecret(Base):
    __tablename__ = "project_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    encrypted_value: Mapped[str] = mapped_column(Text)  # encrypted!
    environment: Mapped[str] = mapped_column(String(64), default="all")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "name", "environment", name="uq_project_secret"),)


# ═══════════════════════════════════════════════════════════════════════════
# Environments — staging/production
# ═══════════════════════════════════════════════════════════════════════════


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))  # production | staging | dev
    branch_pattern: Mapped[str] = mapped_column(String(128), default="main")
    protection_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_project_environment"),)


# ═══════════════════════════════════════════════════════════════════════════
# Git LFS — large file storage
# ═══════════════════════════════════════════════════════════════════════════


class LFSPointer(Base):
    __tablename__ = "lfs_pointers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    oid: Mapped[str] = mapped_column(String(64))  # SHA-256 of file
    size: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(1024))
    blob_sha: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Custom Roles — granular permissions
# ═══════════════════════════════════════════════════════════════════════════


class CustomRole(Base):
    __tablename__ = "custom_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)  # {"push": true, "admin": false, ...}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_custom_role"),)


class ProjectMemberRole(Base):
    __tablename__ = "project_member_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role_id: Mapped[int] = mapped_column(ForeignKey("custom_roles.id"))
    granted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member_role"),)


# ═══════════════════════════════════════════════════════════════════════════
# Push Rules — commit validation
# ═══════════════════════════════════════════════════════════════════════════


class PushRule(Base):
    __tablename__ = "push_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    require_signed_commits: Mapped[bool] = mapped_column(default=False)
    deny_force_push: Mapped[bool] = mapped_column(default=True)
    deny_delete_branch: Mapped[bool] = mapped_column(default=True)
    commit_message_pattern: Mapped[str] = mapped_column(String(256), default="")
    branch_name_pattern: Mapped[str] = mapped_column(String(256), default="")
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Packages — sample/plugin registry
# ═══════════════════════════════════════════════════════════════════════════


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    package_type: Mapped[str] = mapped_column(String(32))  # sample_pack | preset | plugin | stem
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    license: Mapped[str] = mapped_column(String(64), default="royalty-free")
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    blob_sha: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer, default=0)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Gist — code/patch snippets
# ═══════════════════════════════════════════════════════════════════════════


class Gist(Base):
    __tablename__ = "gists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    public: Mapped[bool] = mapped_column(default=True)
    fork_of_id: Mapped[int | None] = mapped_column(nullable=True)
    star_count: Mapped[int] = mapped_column(Integer, default=0)
    fork_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    files: Mapped[list["GistFile"]] = relationship(back_populates="gist", cascade="all, delete-orphan")


class GistFile(Base):
    __tablename__ = "gist_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gist_id: Mapped[int] = mapped_column(ForeignKey("gists.id"), index=True)
    filename: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(32), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    gist: Mapped["Gist"] = relationship(back_populates="files")


# ═══════════════════════════════════════════════════════════════════════════
# Sponsors — funding
# ═══════════════════════════════════════════════════════════════════════════


class Sponsorship(Base):
    __tablename__ = "sponsorships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    tier: Mapped[str] = mapped_column(String(32), default="buy_me_a_coffee")
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Teams — organization teams
# ═══════════════════════════════════════════════════════════════════════════


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    privacy: Mapped[str] = mapped_column(String(32), default="visible")  # visible | secret
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    members: Mapped[list["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(32), default="member")  # member | maintainer | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member"),)
    team: Mapped["Team"] = relationship(back_populates="members")


class TeamProjectAccess(Base):
    __tablename__ = "team_project_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    permission: Mapped[str] = mapped_column(String(32), default="read")  # read | write | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("team_id", "project_id", name="uq_team_project"),)


# ═══════════════════════════════════════════════════════════════════════════
# Actions/Workflows — CI/CD pipelines
# ═══════════════════════════════════════════════════════════════════════════


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    filename: Mapped[str] = mapped_column(String(128))
    yaml_content: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | running | success | failure | cancelled
    trigger: Mapped[str] = mapped_column(String(32), default="push")
    commit_id: Mapped[int | None] = mapped_column(ForeignKey("commits.id"), nullable=True)
    logs: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="runs")


# ═══════════════════════════════════════════════════════════════════════════
# Dependabot — security alerts
# ═══════════════════════════════════════════════════════════════════════════


class SecurityAlert(Base):
    __tablename__ = "security_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    severity: Mapped[str] = mapped_column(String(16))  # low | medium | high | critical
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    package_name: Mapped[str] = mapped_column(String(128), default="")
    vulnerable_version: Mapped[str] = mapped_column(String(32), default="")
    patched_version: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | dismissed | fixed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
# IP Allow List
# ═══════════════════════════════════════════════════════════════════════════


class IPAllowList(Base):
    __tablename__ = "ip_allow_list"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    ip_range: Mapped[str] = mapped_column(String(64))  # CIDR notation
    description: Mapped[str] = mapped_column(String(200), default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Wiki — in-project documentation
# ═══════════════════════════════════════════════════════════════════════════


class WikiPage(Base):
    __tablename__ = "wiki_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    slug: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_wiki_slug"),)


class WikiRevision(Base):
    __tablename__ = "wiki_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("wiki_pages.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(String(200), default="")
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Time Tracking — log hours on tasks
# ═══════════════════════════════════════════════════════════════════════════


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("music_tasks.id"), nullable=True)
    hours: Mapped[float] = mapped_column(Integer, default=0)  # stored as minutes
    description: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Epics — group tasks into large features
# ═══════════════════════════════════════════════════════════════════════════


class Epic(Base):
    __tablename__ = "epics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(7), default="#6366f1")
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | in_progress | done | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EpicTaskLink(Base):
    __tablename__ = "epic_task_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    epic_id: Mapped[int] = mapped_column(ForeignKey("epics.id"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("music_tasks.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("epic_id", "task_id", name="uq_epic_task"),)


# ═══════════════════════════════════════════════════════════════════════════
# Roadmaps — visual timeline
# ═══════════════════════════════════════════════════════════════════════════


class RoadmapItem(Base):
    __tablename__ = "roadmap_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(64), default="feature")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")
    epic_id: Mapped[int | None] = mapped_column(ForeignKey("epics.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Calendar — deadline tracking
# ═══════════════════════════════════════════════════════════════════════════


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(default=False)
    recurrence: Mapped[str] = mapped_column(String(32), default="")  # none | daily | weekly | monthly
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Merge Trains — queue merges
# ═══════════════════════════════════════════════════════════════════════════


class MergeTrain(Base):
    __tablename__ = "merge_trains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    pr_id: Mapped[int] = mapped_column(ForeignKey("pull_requests.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued | merging | merged | failed
    merge_commit_id: Mapped[int | None] = mapped_column(ForeignKey("commits.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
# Requirements — project requirements management
# ═══════════════════════════════════════════════════════════════════════════


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(32), default="proposed")  # proposed | accepted | implemented | verified
    linked_task_id: Mapped[int | None] = mapped_column(ForeignKey("music_tasks.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Design Management — store and review designs
# ═══════════════════════════════════════════════════════════════════════════


class Design(Base):
    __tablename__ = "designs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(256))
    blob_sha: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DesignComment(Base):
    __tablename__ = "design_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    design_id: Mapped[int] = mapped_column(ForeignKey("designs.id"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    position_x: Mapped[float] = mapped_column(Integer, default=0)
    position_y: Mapped[float] = mapped_column(Integer, default=0)
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Service Desk — email support
# ═══════════════════════════════════════════════════════════════════════════


class ServiceDeskTicket(Base):
    __tablename__ = "service_desk_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    identifier: Mapped[str] = mapped_column(String(32), unique=True)  # SD-001
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    from_email: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="new")  # new | in_progress | closed
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# SAST/DAST — security scanning
# ═══════════════════════════════════════════════════════════════════════════


class SecurityScan(Base):
    __tablename__ = "security_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    commit_id: Mapped[int | None] = mapped_column(ForeignKey("commits.id"), nullable=True)
    scan_type: Mapped[str] = mapped_column(String(32))  # sast | dast | dependency | secret
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | running | success | failure
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    high_count: Mapped[int] = mapped_column(Integer, default=0)
    medium_count: Mapped[int] = mapped_column(Integer, default=0)
    low_count: Mapped[int] = mapped_column(Integer, default=0)
    report_url: Mapped[str] = mapped_column(String(500), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecurityFinding(Base):
    __tablename__ = "security_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("security_scans.id"), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(512), default="")
    line: Mapped[int | None] = mapped_column(nullable=True)
    cwe: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | dismissed | fixed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Container Registry — Docker images
# ═══════════════════════════════════════════════════════════════════════════


class ContainerImage(Base):
    __tablename__ = "container_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    tag: Mapped[str] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Feature Flags
# ═══════════════════════════════════════════════════════════════════════════


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(default=False)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_feature_flag"),)


# ═══════════════════════════════════════════════════════════════════════════
# Error Tracking
# ═══════════════════════════════════════════════════════════════════════════


class Error(Base):
    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(String(500))
    stacktrace: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="error")
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | resolved | ignored
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
# Incident Management
# ═══════════════════════════════════════════════════════════════════════════


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="minor")  # critical | major | minor
    status: Mapped[str] = mapped_column(String(32), default="open")  # open | acknowledged | investigating | resolved
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    error_id: Mapped[int | None] = mapped_column(ForeignKey("errors.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
# On-call Schedules
# ═══════════════════════════════════════════════════════════════════════════


class OnCallSchedule(Base):
    __tablename__ = "oncall_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    rotation_interval: Mapped[str] = mapped_column(String(32), default="weekly")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OnCallRotation(Base):
    __tablename__ = "oncall_rotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("oncall_schedules.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Status Page
# ═══════════════════════════════════════════════════════════════════════════


class StatusPageComponent(Base):
    __tablename__ = "status_page_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="operational")  # operational | degraded | outage | maintenance
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StatusPageIncident(Base):
    __tablename__ = "status_page_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(32), default="investigating")  # investigating | identified | monitoring | resolved
    impact: Mapped[str] = mapped_column(String(16), default="minor")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════
# OKRs — Objectives and Key Results
# ═══════════════════════════════════════════════════════════════════════════


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    period: Mapped[str] = mapped_column(String(32), default="Q1 2026")
    status: Mapped[str] = mapped_column(String(32), default="active")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KeyResult(Base):
    __tablename__ = "key_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    objective_id: Mapped[int] = mapped_column(ForeignKey("objectives.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    target_value: Mapped[float] = mapped_column(Integer, default=100)
    current_value: Mapped[float] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(32), default="")  # %, count, etc
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# Audit Events
# ═══════════════════════════════════════════════════════════════════════════


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(48))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[int | None] = mapped_column(nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
