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
