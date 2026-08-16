"""Pydantic schemas for the SoundHub API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(ORMModel):
    id: int
    username: str
    wallet_address: str | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


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
    name: str = Field(
        min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_\-\/\.]+$"
    )
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


# ---------- Web3 ----------
class WalletNonceOut(BaseModel):
    nonce: str
    message: str


class WalletLogin(BaseModel):
    address: str
    message: str
    signature: str


class ReleaseIn(BaseModel):
    token_id: int = Field(gt=0)
    contract_address: str = Field(min_length=40, max_length=42)
    name: str = Field(min_length=1, max_length=256)


# ---------- Files / commits ----------
class FileOut(BaseModel):
    path: str
    size: int
    blob_sha: str
    kind: str  # "dir" | "file"
    daw_format: str | None = None
    daw_info: dict | None = None


class TreeOut(BaseModel):
    commit_id: int
    commit_message: str
    files: list[FileOut]


class CommitCreate(BaseModel):
    message: str = Field(default="", max_length=2000)


class CommitOut(ORMModel):
    id: int
    message: str
    created_at: datetime
    parent_id: int | None
    author: UserOut
    file_count: int = 0
    total_size: int = 0


class CommitDetailOut(CommitOut):
    files: list[FileOut]


# ---------- Review sessions ----------
class ReviewSessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    project_id: int | None = None


class ReviewCommentOut(BaseModel):
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
    # voice notes
    voice_format: str = ""
    voice_duration_s: float = 0.0
    transcript: str = ""


class ReviewCommentCreate(BaseModel):
    time_s: float = Field(default=0, ge=0)
    body: str = Field(min_length=1, max_length=4000)
    parent_id: int | None = None
    status: str = Field(default="open", pattern=r"^(draft|open)$")


class GuestReviewCommentCreate(ReviewCommentCreate):
    author_name: str = Field(default="", max_length=128)


class ReviewVersionOut(BaseModel):
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
    comments: list[ReviewCommentOut] = []
    watermarked: bool = False  # guests hear an audible watermark on this preview
    commit_id: int | None = None  # project commit this bounce was pushed from → smart diff


class ReviewVersionCreate(BaseModel):
    message: str = Field(default="", max_length=2000)


class ReviewSessionOut(BaseModel):
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
    versions: list[ReviewVersionOut] = []


class ReviewStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(in_review|needs_changes|approved)$")


class ReviewBriefUpdate(BaseModel):
    """The client brief: what the client expects, agreed before the first bounce."""

    service_type: str = Field(default="mix", pattern=r"^(mix|master|mix_master|production|stems)$")
    genre: str = Field(default="", max_length=128)
    goal: str = Field(default="", max_length=64)
    deadline_at: datetime | None = None
    review_start_at: datetime | None = None
    reference_links: str = Field(default="", max_length=4000)
    do_not_change: str = Field(default="", max_length=2000)
    required_deliverables: str = Field(default="", max_length=500)


class ShareSettingsUpdate(BaseModel):
    share_password: str | None = Field(default=None, max_length=128)
    share_expires_at: datetime | None = None
    share_permission: str | None = Field(default=None, pattern=r"^(comment|view|download)$")
    share_allowlist: str | None = Field(default=None, max_length=2000)
    feedback_owner: str | None = Field(default=None, max_length=128)
    included_rounds: int | None = Field(default=None, ge=0, le=50)
    rounds_open: bool | None = None
    feedback_due_at: datetime | None = None
    # booking deposit + paid extra rounds
    deposit_due_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    deposit_status: str | None = Field(default=None, pattern=r"^(none|deposit_due|paid|waived)$")
    extra_round_price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    rounds_paid: int | None = Field(default=None, ge=0, le=1000)
    # portfolio + preview protection
    portfolio_public: bool | None = None
    watermark_enabled: bool | None = None
    # retention + late-change fees (change orders)
    retention_until: datetime | None = None
    recall_fee_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    revision_fee_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    # reminder automation
    reminders_enabled: bool | None = None
    reminder_categories: str | None = Field(default=None, max_length=500)
    client_email: str | None = Field(default=None, max_length=256)


class ReminderSettingsUpdate(BaseModel):
    """Engineer picks what to automate and where client mail goes."""

    reminders_enabled: bool | None = None
    reminder_categories: str | None = Field(default=None, max_length=500)  # comma list; empty = all
    client_email: str | None = Field(default=None, max_length=256)


class NotificationOut(BaseModel):
    id: int
    session_id: int
    kind: str
    channel: str = "email"
    recipient: str = ""
    subject: str = ""
    body: str = ""
    cta_url: str = ""
    cta_label: str = ""
    status: str = "queued"
    error: str = ""
    sent_at: datetime | None = None
    created_at: datetime


class RemindersEvalOut(BaseModel):
    evaluated: int = 0
    created: int = 0
    sent: int = 0
    failed: int = 0
    dismissed: int = 0


class ReviewApprovalCreate(BaseModel):
    scope: str = Field(default="mix", pattern=r"^(mix|master|arrangement|release)$")
    approved: bool = True
    note: str = Field(default="", max_length=2000)
    approver_name: str = Field(default="", max_length=128)


class ReviewApprovalOut(BaseModel):
    id: int
    session_id: int
    version_id: int
    scope: str
    approved: bool
    note: str
    approver_name: str
    role: str = ""  # team role that signed off (empty in permissive presets)
    created_at: datetime


# ---------- Team roles & approval chains ----------
APPROVAL_PRESETS = ["solo_client", "artist_team", "label_workflow", "post_production"]
TEAM_ROLES = [
    "engineer",
    "artist",
    "feedback_owner",
    "a_r",
    "label_admin",
    "producer",
    "director",
    "viewer",
]


class SessionMemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=256)
    role: str = Field(pattern=r"^(engineer|artist|feedback_owner|a_r|label_admin|producer|director|viewer)$")


class SessionMemberOut(BaseModel):
    id: int
    session_id: int
    email: str
    role: str
    invited_by: str = ""
    created_at: datetime


class ApprovalPresetUpdate(BaseModel):
    preset: str = Field(pattern=r"^(solo_client|artist_team|label_workflow|post_production)$")


class ApprovalPolicyOut(BaseModel):
    preset: str = "solo_client"
    preset_label: str = "Solo client"
    enforced: bool = False
    policy: dict = {}  # scope -> required roles
    roles: list[str] = []


class ApprovalStatusOut(BaseModel):
    scope: str
    ok: bool
    missing: list[str] = []
    required: list[str] = []
    enforced: bool = False


class ShareAccessEventOut(BaseModel):
    id: int
    actor: str
    action: str
    detail: str
    created_at: datetime


class ReviewRoundOut(BaseModel):
    id: int
    number: int
    status: str
    submitted_at: datetime | None = None
    due_at: datetime | None = None
    note: str = ""
    request_count: int = 0


class ReviewRequestStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(open|acknowledged|in_progress|fixed|verified|approved)$")
    fixed_in_version_id: int | None = None


class ReviewRoundSubmit(BaseModel):
    note: str = Field(default="", max_length=2000)
    due_at: datetime | None = None


class ReviewSessionDetailOut(ReviewSessionOut):
    versions: list[ReviewVersionOut] = []
    approvals: list[ReviewApprovalOut] = []
    access_events: list[ShareAccessEventOut] = []
    rounds: list[ReviewRoundOut] = []
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
    # retention + late-change fees (change orders)
    retention_until: datetime | None = None
    recall_fee_cents: int | None = None
    revision_fee_cents: int | None = None
    change_rounds_granted: int = 0
    # reminder automation
    reminders_enabled: bool = True
    reminder_categories: str = ""
    reminders_client_opt_out: bool = False
    client_email: str = ""
    # team roles & approval chain
    approval_preset: str = "solo_client"
    members: list[SessionMemberOut] = []
    # client brief — expectations fixed before the first bounce
    service_type: str = "mix"
    genre: str = ""
    goal: str = ""
    deadline_at: datetime | None = None
    review_start_at: datetime | None = None
    reference_links: str = ""
    do_not_change: str = ""
    required_deliverables: str = ""


# ---------- Audio analysis & A/B comparison ----------
class AudioAnalysisOut(BaseModel):
    version_id: int | None = None
    duration_ms: int = 0
    sample_rate: int | None = None
    channels: int | None = None
    integrated_lufs: float | None = None
    true_peak_dbtp: float | None = None
    analysis_status: str = "pending"  # pending | done | unavailable
    analysed_at: datetime | None = None


STEM_LOGICAL_NAMES = ["drums", "bass", "vocal", "synths", "other"]


class StemCreate(BaseModel):
    logical_name: str = Field(pattern=r"^(drums|bass|vocal|synths|other)$")
    display_name: str = Field(default="", max_length=128)
    start_offset_ms: int = Field(default=0, ge=0)


class StemOut(BaseModel):
    id: int
    version_id: int
    logical_name: str
    display_name: str = ""
    size: int = 0
    audio_format: str = "wav"
    start_offset_ms: int = 0
    created_at: datetime


class StemAudioUrlOut(BaseModel):
    url: str = ""


class ComparisonCreate(BaseModel):
    base_version_id: int
    compare_version_id: int
    request_id: int | None = None
    start_ms: int = Field(default=0, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    mode: str = Field(default="full_mix", pattern=r"^(full_mix|stem)$")
    stem_logical_name: str | None = Field(default=None, pattern=r"^(drums|bass|vocal|synths|other)$")
    level_match: str = Field(default="short_term_lufs", pattern=r"^(none|integrated_lufs|short_term_lufs)$")


class ComparisonOut(BaseModel):
    id: int
    session_id: int
    base_version_id: int
    compare_version_id: int
    base_label: str = ""
    compare_label: str = ""
    request_id: int | None = None
    start_ms: int = 0
    end_ms: int | None = None
    base_gain_db: float = 0.0
    compare_gain_db: float = 0.0
    short_term_lufs: dict = {}
    level_match: str = "none"
    label: str = ""
    mode: str = "full_mix"
    stem_logical_name: str | None = None
    created_at: datetime


# ---------- Reference tracks (mix/reference A/B) ----------
REFERENCE_PURPOSES = ["balance", "low_end", "vocal", "width", "arrangement", "overall"]
REFERENCE_VISIBILITY = ["engineer_only", "reviewers"]


class ReferenceTrackCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(default="", max_length=128)
    source_type: str = Field(pattern=r"^(external_url|private_upload)$")
    external_url: str = Field(default="", max_length=2000)
    purpose: str = Field(default="overall", pattern=r"^(balance|low_end|vocal|width|arrangement|overall)$")
    visibility: str = Field(default="reviewers", pattern=r"^(engineer_only|reviewers)$")
    note: str = Field(default="", max_length=1000)


class ReferenceTrackUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    artist: str | None = Field(default=None, max_length=128)
    external_url: str | None = Field(default=None, max_length=2000)
    purpose: str | None = Field(default=None, pattern=r"^(balance|low_end|vocal|width|arrangement|overall)$")
    visibility: str | None = Field(default=None, pattern=r"^(engineer_only|reviewers)$")
    note: str | None = Field(default=None, max_length=1000)


class ReferenceTrackOut(BaseModel):
    id: int
    session_id: int
    title: str
    artist: str = ""
    source_type: str
    external_url: str = ""
    purpose: str = "overall"
    visibility: str = "reviewers"
    note: str = ""
    created_by: str = ""
    created_at: datetime
    filename: str = ""
    size: int = 0
    audio_format: str = ""
    duration_s: float = 0.0
    integrated_lufs: float | None = None
    true_peak_dbtp: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    analysis_status: str = "pending"
    waveform: list[float] = []
    waveform_synthetic: bool = False


class ReferenceComparisonCreate(BaseModel):
    version_id: int
    reference_id: int
    start_ms: int = Field(default=0, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    level_match: str = Field(default="short_term_lufs", pattern=r"^(none|integrated_lufs|short_term_lufs)$")


# ---------- Change orders (late changes after approval/delivery) ----------
CHANGE_ORDER_REASONS = ["mix_revision", "new_stem_request", "format_change", "mastering_recall"]
CHANGE_ORDER_DECISIONS = ["courtesy", "paid_round", "new_mastering_pass"]


class ChangeOrderCreate(BaseModel):
    reason: str = Field(pattern=r"^(mix_revision|new_stem_request|format_change|mastering_recall)$")
    description: str = Field(default="", max_length=2000)


class ChangeOrderQuote(BaseModel):
    decision: str = Field(pattern=r"^(courtesy|paid_round|new_mastering_pass)$")
    price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    deadline_at: datetime | None = None


class ChangeOrderOut(BaseModel):
    id: int
    session_id: int
    created_by: str = ""
    reason: str
    description: str = ""
    status: str = "requested"  # requested | quoted | accepted | declined | paid | expired
    decision: str | None = None
    price_cents: int | None = None
    currency: str = "usd"
    deadline_at: datetime | None = None
    target_round: int = 1
    round_granted: bool = False
    quote_version: int = 0
    quote_expires_at: datetime | None = None
    quoted_at: datetime | None = None
    accepted_at: datetime | None = None
    paid_at: datetime | None = None
    declined_at: datetime | None = None
    created_at: datetime


class ReferenceComparisonOut(BaseModel):
    id: int
    session_id: int
    version_id: int
    reference_id: int
    version_label: str = ""
    reference_label: str = ""
    start_ms: int = 0
    end_ms: int | None = None
    mix_gain_db: float = 0.0
    ref_gain_db: float = 0.0
    short_term_lufs: dict = {}
    level_match: str = "none"
    label: str = ""
    mix_audio_url: str = ""
    ref_audio_url: str = ""
    created_at: datetime


# ---------- Release packages (final delivery) ----------
class ReleasePackageCreate(BaseModel):
    session_id: int
    approved_version_id: int
    name: str = Field(default="", max_length=160)  # empty → template preset name
    template: str = Field(default="custom", max_length=32)


class DeliverableType(str):
    pass


DELIVERABLE_TYPES = ["master", "instrumental", "acapella", "clean_edit", "stems", "artwork", "other"]


class DeliverableCreate(BaseModel):
    type: str = Field(pattern=r"^(master|instrumental|acapella|clean_edit|stems|artwork|other)$")
    is_required: bool = True
    from_version_id: int | None = None  # reuse an existing version's audio


class DeliverableOut(BaseModel):
    id: int
    package_id: int
    type: str
    filename: str
    size: int
    sha256: str | None = None
    format: str
    sample_rate: int | None = None
    bit_depth: int | None = None
    channels: int | None = None
    integrated_lufs: float | None = None
    true_peak: float | None = None
    is_required: bool
    source_version_id: int | None = None
    created_at: datetime


class ReleasePackageOut(BaseModel):
    id: int
    session_id: int
    approved_version_id: int
    name: str
    status: str
    invoice_status: str = "none"
    amount_due_cents: int | None = None
    currency: str = "usd"
    immutable_at: datetime | None = None
    manifest_hash: str | None = None
    delivery_token: str | None = None
    created_at: datetime
    locked_by: str = ""
    template: str = "custom"
    plugin_manifest: str = ""
    session_manifest: dict = {}
    consolidate_audio: bool = False
    archive_expires_at: datetime | None = None
    archive_status: str = "available_now"
    last_verified_opened_at: datetime | None = None
    invoice_due_at: datetime | None = None
    force_locked_reason: str = ""
    force_locked_by: str = ""
    deliverables: list[DeliverableOut] = []
    events: list[dict] = []


class PackageTemplateOut(BaseModel):
    id: str
    name: str
    description: str
    deliverable_types: list[str] = []
    note: str = ""


class ReleaseLockIn(BaseModel):
    approval_scope: str = Field(default="master", pattern=r"^(arrangement|mix|master|release)$")
    note: str = Field(default="", max_length=1000)
    force: bool = False  # skip blocking preflight issues ("lock anyway")
    force_reason: str = Field(default="", max_length=1000)  # required when force=True


class PreflightCheckOut(BaseModel):
    status: str  # ok | warn | block
    label: str
    detail: str = ""


class PreflightOut(BaseModel):
    passed: bool
    blocking: bool
    checks: list[PreflightCheckOut] = []


class HandoffUpdate(BaseModel):
    plugin_manifest: str | None = Field(default=None, max_length=8000)
    session_manifest: dict | None = None
    consolidate_audio: bool | None = None
    archive_expires_at: datetime | None = None
    last_verified_opened_at: datetime | None = None


class ArchiveUpdate(BaseModel):
    archive_status: str = Field(
        default="available_now",
        pattern=r"^(available_now|needs_preparation|archived|permanently_deleted)$",
    )
    archive_expires_at: datetime | None = None


class DeliveryManifestOut(BaseModel):
    package: ReleasePackageOut
    manifest_json: dict
    manifest_hash: str


class DeliveryPageOut(BaseModel):
    id: int
    name: str
    status: str
    invoice_status: str = "none"
    amount_due_cents: int | None = None
    currency: str = "usd"
    deposit_due_cents: int | None = None
    deposit_status: str = "none"
    locked_by: str = ""
    immutable_at: datetime | None = None
    manifest_hash: str | None = None
    approved_label: str = ""
    approved_filename: str = ""
    template: str = "custom"
    archive_status: str = "available_now"
    archive_expires_at: datetime | None = None
    last_verified_opened_at: datetime | None = None
    invoice_due_at: datetime | None = None
    retention_until: datetime | None = None
    share_token: str = ""
    deliverables: list[DeliverableOut] = []


class DeliveryInvoiceUpdate(BaseModel):
    invoice_status: str = Field(pattern=r"^(none|deposit_due|balance_due|paid|waived)$")
    amount_due_cents: int | None = Field(default=None, ge=0, le=100_000_000)  # 1M USD max
    currency: str = Field(default="usd", max_length=8)
    invoice_due_at: datetime | None = None


class CheckoutOut(BaseModel):
    """A Stripe Checkout session ready for redirect."""

    checkout_url: str
    session_id: str
    amount_due_cents: int
    currency: str


# ---------- Public engineer portfolio ----------
class PortfolioTrackOut(BaseModel):
    session_id: int
    name: str
    status: str
    version_count: int = 0
    has_approved: bool = False
    approved_label: str = ""
    approved_filename: str = ""
    approved_version_id: int | None = None
    approved_duration_s: float = 0.0
    approved_at: datetime | None = None
    delivery_token: str | None = None  # locked release package, when one exists


class PortfolioOut(BaseModel):
    username: str
    track_count: int = 0
    tracks: list[PortfolioTrackOut] = []


# ---------- Diff ----------
class DiffChange(BaseModel):
    kind: str  # "bpm" | "tempo" | "track_added" | "track_removed" | "device_added" | "device_removed" | "info"
    label: str
    old: str | None = None
    new: str | None = None


class DiffOut(BaseModel):
    path: str
    format: str | None = None
    summary: list[DiffChange] = []
    raw: str = ""
    binary: bool = False
    truncated: bool = False


class VersionDiffOut(BaseModel):
    """Smart diff for a review version vs the previous one in the session."""

    version_label: str
    from_label: str | None = None  # "v11" / "parent commit" / None (first version)
    path: str | None = None
    format: str | None = None
    has_daw: bool = False  # the pushed commit carried a parseable DAW file
    summary: list[DiffChange] = []
    raw: str = ""
    truncated: bool = False
