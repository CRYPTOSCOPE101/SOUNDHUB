"""Pydantic schemas for the SoundHub API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.\-]+$")
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(ORMModel):
    id: int
    username: str
    wallet_address: str | None = None
    created_at: datetime
    bio: str = ""
    specialty: str = ""
    location: str = ""


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileUpdate(BaseModel):
    bio: str | None = None
    specialty: str | None = None
    location: str | None = None


class WalletNonceOut(BaseModel):
    nonce: str
    message: str


class WalletLogin(BaseModel):
    address: str
    message: str
    signature: str


# ---------- Projects ----------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4000)


class ProjectOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str
    default_branch: str = "main"
    release_token_id: int | None = None
    release_contract: str | None = None
    release_name: str | None = None
    created_at: datetime
    updated_at: datetime
    owner: UserOut


# ---------- Branches ----------
class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-/\.]+$")
    from_branch: str | None = Field(default=None, max_length=64)


class BranchOut(BaseModel):
    name: str
    is_default: bool
    head_commit_id: int | None = None
    head_message: str = ""
    head_sha: str | None = None
    head_author: str = ""
    head_date: datetime | None = None
    commit_count: int = 0
    created_at: datetime


# ---------- Commits ----------
class CommitCreate(BaseModel):
    message: str = Field(default="", max_length=2000)
    branch: str = Field(default="main", max_length=64)


class FileSnapshotOut(BaseModel):
    path: str
    blob_sha: str
    size: int


class CommitOut(ORMModel):
    id: int
    message: str
    created_at: datetime
    author: UserOut
    files: list[FileSnapshotOut] = []
    parent_id: int | None = None


# ---------- Review Sessions ----------
class ReviewSessionCreate(BaseModel):
    project_id: int | None = None
    name: str = Field(min_length=1, max_length=160)


class ReviewSessionOut(ORMModel):
    id: int
    project_id: int | None = None
    name: str
    status: str
    share_token: str
    created_at: datetime
    updated_at: datetime
    owner_username: str = ""
    version_count: int = 0
    latest_status: str = ""


class ReviewSessionDetailOut(ReviewSessionOut):
    versions: list["ReviewVersionOut"] = []
    approvals: list["ReviewApprovalOut"] = []
    access_events: list["ShareAccessEventOut"] = []
    rounds: list["ReviewRoundOut"] = []
    share_expires_at: datetime | None = None
    share_permission: str = "comment"
    share_has_password: bool = False
    share_allowlist: str = ""
    round_number: int = 1
    feedback_due_at: datetime | None = None
    feedback_owner: str = ""
    included_rounds: int = 1
    rounds_open: bool = True
    deposit_due_cents: int | None = None
    deposit_status: str = "none"
    extra_round_price_cents: int | None = None
    rounds_paid: int = 0
    portfolio_public: bool = False
    watermark_enabled: bool = True
    retention_until: datetime | None = None
    recall_fee_cents: int | None = None
    revision_fee_cents: int | None = None
    change_rounds_granted: int = 0
    approval_preset: str = "solo_client"
    members: list[dict] = []
    service_type: str = "mix"
    genre: str = ""
    goal: str = ""
    deadline_at: datetime | None = None
    review_start_at: datetime | None = None
    reference_links: str = ""
    do_not_change: str = ""
    required_deliverables: str = ""


# ---------- Versions ----------
class ReviewVersionOut(ORMModel):
    id: int
    session_id: int
    number: int
    label: str
    message: str
    status: str
    filename: str
    size: int
    duration_s: float
    audio_format: str
    created_at: datetime
    round_number: int = 1
    waveform: list[float] = []
    waveform_synthetic: bool = False
    comments: list["ReviewCommentOut"] = []
    watermarked: bool = False
    commit_id: int | None = None


# ---------- Comments ----------
class ReviewCommentCreate(BaseModel):
    time_s: float = 0.0
    body: str = Field(max_length=5000)
    parent_id: int | None = None
    status: str = "open"


class GuestReviewCommentCreate(BaseModel):
    author_name: str = Field(max_length=128)
    time_s: float = 0.0
    body: str = Field(max_length=5000)
    parent_id: int | None = None


class ReviewCommentOut(ORMModel):
    id: int
    version_id: int
    time_s: float
    body: str
    resolved: bool
    author_name: str = ""
    parent_id: int | None = None
    created_at: datetime
    status: str = "open"
    fixed_in: int | None = None
    verified_at: datetime | None = None
    voice_format: str = ""
    voice_duration_s: float = 0.0
    transcript: str = ""


# ---------- Approvals ----------
class ReviewApprovalCreate(BaseModel):
    scope: str = "mix"
    approved: bool = True
    note: str = Field(default="", max_length=2000)
    approver_name: str = Field(default="", max_length=128)


class ReviewApprovalOut(ORMModel):
    id: int
    session_id: int
    version_id: int
    scope: str
    approved: bool
    note: str
    approver_name: str
    role: str = ""
    created_at: datetime


# ---------- Rounds ----------
class ReviewRoundSubmit(BaseModel):
    note: str = Field(default="", max_length=2000)


class ReviewRoundOut(ORMModel):
    id: int
    session_id: int
    number: int
    status: str
    submitted_at: datetime | None = None
    due_at: datetime | None = None
    note: str
    request_count: int


# ---------- Share Settings ----------
class ShareSettingsUpdate(BaseModel):
    share_password: str | None = None
    share_expires_at: datetime | None = None
    share_permission: str | None = None
    share_allowlist: str | None = None
    feedback_owner: str | None = None
    included_rounds: int | None = None
    rounds_open: bool | None = None
    feedback_due_at: datetime | None = None
    deposit_due_cents: int | None = None
    deposit_status: str | None = None
    extra_round_price_cents: int | None = None
    rounds_paid: int | None = None
    portfolio_public: bool | None = None
    watermark_enabled: bool | None = None
    retention_until: datetime | None = None
    recall_fee_cents: int | None = None
    revision_fee_cents: int | None = None


# ---------- Brief ----------
class ReviewBriefUpdate(BaseModel):
    service_type: str = "mix"
    genre: str = Field(default="", max_length=128)
    goal: str = Field(default="", max_length=64)
    deadline_at: datetime | None = None
    review_start_at: datetime | None = None
    reference_links: str = Field(default="", max_length=4000)
    do_not_change: str = Field(default="", max_length=2000)
    required_deliverables: str = Field(default="", max_length=500)


# ---------- Status Updates ----------
class ReviewStatusUpdate(BaseModel):
    status: str


class ReviewRequestStatusUpdate(BaseModel):
    status: str


# ---------- Access Events ----------
class ShareAccessEventOut(ORMModel):
    id: int
    session_id: int
    actor: str
    action: str
    detail: str
    created_at: datetime


# ---------- Version Diff ----------
class VersionDiffOut(BaseModel):
    version_label: str
    from_label: str | None = None
    path: str | None = None
    format: str | None = None
    has_daw: bool = False
    summary: dict = {}
    raw: str = ""
    truncated: bool = False


# ---------- Release Packages ----------
class ReleasePackageOut(ORMModel):
    id: int
    session_id: int
    approved_version_id: int
    name: str
    status: str
    invoice_status: str
    amount_due_cents: int | None = None
    currency: str
    immutable_at: datetime | None = None
    manifest_hash: str | None = None
    delivery_token: str | None = None
    created_at: datetime
    locked_by: str
    template: str
    plugin_manifest: str
    session_manifest: dict
    consolidate_audio: bool
    archive_status: str


class ReleasePackageCreate(BaseModel):
    approved_version_id: int
    name: str = Field(default="Final delivery", max_length=160)
    template: str = Field(default="custom", max_length=32)


class DeliverableOut(ORMModel):
    id: int
    package_id: int
    type: str
    filename: str
    blob_sha: str
    size: int
    sha256: str | None = None
    format: str
    sample_rate: int | None = None
    bit_depth: int | None = None
    channels: int | None = None
    integrated_lufs: float | None = None
    true_peak: float | None = None
    is_required: bool
    created_at: datetime


# ---------- Checkout ----------
class CheckoutOut(BaseModel):
    checkout_url: str
    session_id: str
    amount_due_cents: int
    currency: str


# ---------- Activity ----------
class ActivityEventOut(ORMModel):
    id: int
    user_id: int | None = None
    session_id: int | None = None
    project_id: int | None = None
    event_type: str
    actor_name: str
    entity_type: str
    entity_id: int | None = None
    detail: str
    metadata_json: dict | None = None
    created_at: datetime


# ---------- Analytics ----------
class AnalyticsOut(BaseModel):
    total_sessions: int = 0
    total_versions: int = 0
    total_comments: int = 0
    total_approvals: int = 0
    sessions_by_status: dict = {}
    avg_versions_per_session: float = 0.0


# ---------- Templates ----------
class SessionTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    service_type: str = Field(default="mix_master", max_length=32)
    genre: str = Field(default="", max_length=64)
    included_rounds: int = Field(default=2, ge=0)
    extra_round_price_cents: int = Field(default=0, ge=0)
    deposit_due_cents: int = Field(default=0, ge=0)
    required_deliverables: str = Field(default="master,instrumental", max_length=500)
    brief_template: str = Field(default="", max_length=4000)
    is_public: bool = False


class SessionTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    service_type: str | None = Field(default=None, max_length=32)
    genre: str | None = Field(default=None, max_length=64)
    included_rounds: int | None = None
    extra_round_price_cents: int | None = None
    deposit_due_cents: int | None = None
    required_deliverables: str | None = Field(default=None, max_length=500)
    brief_template: str | None = Field(default=None, max_length=4000)
    is_public: bool | None = None


class SessionTemplateOut(ORMModel):
    id: int
    owner_id: int
    name: str
    description: str
    service_type: str
    genre: str
    included_rounds: int
    extra_round_price_cents: int
    deposit_due_cents: int
    required_deliverables: str
    brief_template: str
    is_public: bool
    use_count: int
    created_at: datetime
    updated_at: datetime


# ---------- Tags ----------
class SessionTagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str = Field(default="#6366f1", max_length=7)


class SessionTagUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=7)


class SessionTagOut(ORMModel):
    id: int
    owner_id: int
    name: str
    color: str
    created_at: datetime


class SessionTagLinkCreate(BaseModel):
    tag_id: int


class SessionTagLinkOut(ORMModel):
    id: int
    session_id: int
    tag_id: int
    created_at: datetime


# ---------- Groups ----------
class SessionGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    color: str = Field(default="#3b82f6", max_length=7)
    parent_id: int | None = None
    sort_order: int = 0


class SessionGroupUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, max_length=7)
    parent_id: int | None = None
    sort_order: int | None = None


class SessionGroupOut(ORMModel):
    id: int
    owner_id: int
    name: str
    description: str
    color: str
    parent_id: int | None = None
    sort_order: int
    created_at: datetime
    updated_at: datetime


class SessionGroupLinkCreate(BaseModel):
    group_id: int


class SessionGroupLinkOut(ORMModel):
    id: int
    session_id: int
    group_id: int
    created_at: datetime


# ---------- Pins ----------
class VersionPinCreate(BaseModel):
    version_id: int
    label: str = Field(default="", max_length=64)


class VersionPinOut(ORMModel):
    id: int
    session_id: int
    version_id: int
    pinned_by: int
    label: str
    created_at: datetime


# ---------- Webhooks ----------
class WebhookCreate(BaseModel):
    url: str = Field(max_length=512)
    secret: str | None = Field(default=None, max_length=128)
    events: str = Field(default="*", max_length=1000)
    is_active: bool = True


class WebhookUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=512)
    secret: str | None = None
    events: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class WebhookOut(ORMModel):
    id: int
    owner_id: int
    url: str
    events: str
    is_active: bool
    last_status: int | None = None
    last_error: str
    last_triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryOut(ORMModel):
    id: int
    webhook_id: int
    event_type: str
    payload: dict
    status_code: int | None = None
    response_body: str
    success: bool
    duration_ms: int | None = None
    created_at: datetime


# ---------- Reminders ----------
class ReminderEvaluateOut(BaseModel):
    evaluated: int
    created: int


class ReminderSendOut(BaseModel):
    sent: int
    failed: int


# ---------- Search ----------
class SearchResultOut(BaseModel):
    query: str
    engineers: list[dict] = []
    sessions: list[dict] = []


# ---------- Reference Tracks ----------
class ReferenceTrackCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(default="", max_length=128)
    source_type: str = Field(max_length=16)
    external_url: str = Field(default="", max_length=2000)
    purpose: str = Field(default="overall", max_length=32)
    visibility: str = Field(default="reviewers", max_length=32)
    note: str = Field(default="", max_length=2000)


class ReferenceTrackOut(ORMModel):
    id: int
    session_id: int
    title: str
    artist: str
    source_type: str
    external_url: str
    blob_sha: str | None = None
    filename: str
    size: int
    audio_format: str
    duration_s: float
    purpose: str
    visibility: str
    note: str
    created_by: str
    created_at: datetime
    integrated_lufs: float | None = None
    true_peak_dbtp: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    analysis_status: str


# ---------- Roles ----------
class RoleUpdate(BaseModel):
    email: str = Field(max_length=256)
    role: str = Field(max_length=32)


class RoleOut(BaseModel):
    id: int
    session_id: int
    email: str
    role: str
    invited_by: str
    created_at: datetime


# ---------- Change Orders ----------
class ChangeOrderCreate(BaseModel):
    reason: str = Field(max_length=32)
    description: str = Field(default="", max_length=2000)


class ChangeOrderQuote(BaseModel):
    decision: str = Field(max_length=32)
    price_cents: int | None = None
    deadline_at: datetime | None = None


class ChangeOrderOut(ORMModel):
    id: int
    session_id: int
    created_by: str
    reason: str
    description: str
    status: str
    decision: str | None = None
    price_cents: int | None = None
    currency: str
    deadline_at: datetime | None = None
    target_round: int
    round_granted: bool
    quoted_at: datetime | None = None
    accepted_at: datetime | None = None
    paid_at: datetime | None = None
    declined_at: datetime | None = None
    quote_expires_at: datetime | None = None
    quote_version: int
    created_at: datetime


# ---------- Comparisons ----------
class VersionComparisonCreate(BaseModel):
    base_version_id: int
    compare_version_id: int
    start_ms: int = 0
    end_ms: int | None = None
    level_match: str = "integrated_lufs"


class VersionComparisonOut(ORMModel):
    id: int
    session_id: int
    base_version_id: int
    compare_version_id: int
    start_ms: int
    end_ms: int | None = None
    base_gain_db: float
    compare_gain_db: float
    level_match: str
    mode: str
    stem_logical_name: str | None = None
    created_at: datetime


class ReferenceComparisonCreate(BaseModel):
    version_id: int
    reference_id: int
    start_ms: int = 0
    end_ms: int | None = None
    level_match: str = "integrated_lufs"


class ReferenceComparisonOut(ORMModel):
    id: int
    session_id: int
    version_id: int
    reference_id: int
    start_ms: int
    end_ms: int | None = None
    mix_gain_db: float
    ref_gain_db: float
    level_match: str
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Pull Requests
# ═══════════════════════════════════════════════════════════════════════════

class PullRequestCreate(BaseModel):
    source_branch: str = Field(min_length=1, max_length=64)
    target_branch: str = Field(default="main", max_length=64)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    labels: list[str] = []

class PullRequestUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None

class PullRequestOut(BaseModel):
    id: int
    project_id: int
    author: UserOut
    source_branch: str
    target_branch: str
    title: str
    description: str
    status: str
    review_count: int = 0
    approval_count: int = 0
    comment_count: int = 0
    labels: list[str] = []
    merge_commit_id: int | None = None
    created_at: datetime
    updated_at: datetime

class PullRequestReviewCreate(BaseModel):
    decision: str = Field(pattern=r"^(comment|approve|request_changes)$")
    body: str = Field(default="", max_length=5000)

class PullRequestReviewOut(BaseModel):
    id: int
    reviewer: UserOut | None = None
    reviewer_name: str
    decision: str
    body: str
    created_at: datetime

class PullRequestCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    path: str | None = None
    time_s: float | None = None
    parent_id: int | None = None

class PullRequestCommentOut(BaseModel):
    id: int
    author: UserOut | None = None
    author_name: str
    body: str
    path: str | None = None
    time_s: float | None = None
    resolved: bool
    parent_id: int | None = None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Music Tasks
# ═══════════════════════════════════════════════════════════════════════════

class MusicTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=10000)
    type: str = Field(default="task", pattern=r"^(task|bug|feature|question)$")
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|critical)$")
    assignee_id: int | None = None
    milestone: str = Field(default="", max_length=128)
    due_date: datetime | None = None
    labels: list[str] = []

class MusicTaskUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    type: str | None = None
    priority: str | None = None
    status: str | None = None
    assignee_id: int | None = None
    milestone: str | None = None
    due_date: datetime | None = None

class MusicTaskOut(BaseModel):
    id: int
    project_id: int
    author: UserOut
    title: str
    body: str
    type: str
    priority: str
    status: str
    assignee: UserOut | None = None
    milestone: str
    due_date: datetime | None = None
    labels: list[str] = []
    comment_count: int = 0
    linked_pr_id: int | None = None
    created_at: datetime
    updated_at: datetime

class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

class TaskCommentOut(BaseModel):
    id: int
    author: UserOut | None = None
    author_name: str
    body: str
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Tags & Releases
# ═══════════════════════════════════════════════════════════════════════════

class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    commit_id: int
    message: str = Field(default="", max_length=2000)
    is_release: bool = False

class TagOut(BaseModel):
    id: int
    project_id: int
    name: str
    message: str
    commit_id: int
    is_release: bool
    created_by: UserOut
    created_at: datetime

class ReleaseNoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=10000)
    highlights: str = Field(default="", max_length=2000)

class ReleaseNoteOut(BaseModel):
    id: int
    tag: TagOut
    title: str
    body: str
    highlights: str
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Audio CI Checks
# ═══════════════════════════════════════════════════════════════════════════

class AudioCheckCreate(BaseModel):
    check_type: str = Field(pattern=r"^(lufs|true_peak|format|sample_rate|channels)$")
    value: str = Field(max_length=128)
    expected: str = Field(default="", max_length=128)

class AudioCheckOut(BaseModel):
    id: int
    commit_id: int
    check_type: str
    status: str
    value: str
    expected: str
    message: str
    created_at: datetime

class AudioCheckResultOut(BaseModel):
    commit_id: int
    checks: list[AudioCheckOut]
    passed: int
    failed: int
    warned: int
    total: int


# ═══════════════════════════════════════════════════════════════════════════
# Discussions
# ═══════════════════════════════════════════════════════════════════════════

class DiscussionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)
    category: str = Field(default="general", max_length=64)

class DiscussionUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    category: str | None = None
    pinned: bool | None = None
    locked: bool | None = None

class DiscussionOut(BaseModel):
    id: int
    project_id: int
    author: UserOut
    title: str
    body: str
    category: str
    pinned: bool
    locked: bool
    comment_count: int = 0
    created_at: datetime
    updated_at: datetime

class DiscussionCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

class DiscussionCommentOut(BaseModel):
    id: int
    author: UserOut | None = None
    author_name: str
    body: str
    is_answer: bool
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Kanban Boards
# ═══════════════════════════════════════════════════════════════════════════

class KanbanBoardCreate(BaseModel):
    name: str = Field(default="Release Board", max_length=128)
    columns: list[str] = ["Backlog", "In Progress", "Review", "Approved", "Mastered", "Released"]

class KanbanBoardOut(BaseModel):
    id: int
    project_id: int
    name: str
    columns: list["KanbanColumnOut"] = []
    created_at: datetime

class KanbanColumnOut(BaseModel):
    id: int
    name: str
    position: int
    color: str
    cards: list["KanbanCardOut"] = []

class KanbanCardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    version_id: int | None = None
    task_id: int | None = None
    assignee_id: int | None = None

class KanbanCardUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    column_id: int | None = None
    position: int | None = None
    assignee_id: int | None = None

class KanbanCardOut(BaseModel):
    id: int
    title: str
    description: str
    version_id: int | None = None
    task_id: int | None = None
    position: int
    assignee: UserOut | None = None
    created_at: datetime

KanbanBoardOut.model_rebuild()
KanbanColumnOut.model_rebuild()
