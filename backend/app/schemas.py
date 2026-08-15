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


class ShareSettingsUpdate(BaseModel):
    share_password: str | None = Field(default=None, max_length=128)
    share_expires_at: datetime | None = None
    share_permission: str = Field(default="comment", pattern=r"^(comment|view|download)$")
    share_allowlist: str = Field(default="", max_length=2000)
    feedback_owner: str = Field(default="", max_length=128)
    included_rounds: int | None = Field(default=None, ge=0, le=50)
    rounds_open: bool | None = None
    feedback_due_at: datetime | None = None


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
    created_at: datetime


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


class ComparisonCreate(BaseModel):
    base_version_id: int
    compare_version_id: int
    request_id: int | None = None
    start_ms: int = Field(default=0, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    mode: str = Field(default="full_mix", pattern=r"^(full_mix|stem)$")
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
    created_at: datetime


# ---------- Release packages (final delivery) ----------
class ReleasePackageCreate(BaseModel):
    session_id: int
    approved_version_id: int
    name: str = Field(default="Final delivery", max_length=160)


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
    immutable_at: datetime | None = None
    manifest_hash: str | None = None
    delivery_token: str | None = None
    created_at: datetime
    locked_by: str = ""
    deliverables: list[DeliverableOut] = []
    events: list[dict] = []


class ReleaseLockIn(BaseModel):
    approval_scope: str = Field(default="master", pattern=r"^(arrangement|mix|master|release)$")
    note: str = Field(default="", max_length=1000)


class DeliveryManifestOut(BaseModel):
    package: ReleasePackageOut
    manifest_json: dict
    manifest_hash: str


class DeliveryPageOut(BaseModel):
    id: int
    name: str
    status: str
    invoice_status: str = "none"
    locked_by: str = ""
    immutable_at: datetime | None = None
    manifest_hash: str | None = None
    approved_label: str = ""
    approved_filename: str = ""
    deliverables: list[DeliverableOut] = []


class DeliveryInvoiceUpdate(BaseModel):
    invoice_status: str = Field(pattern=r"^(none|deposit_due|balance_due|paid|waived)$")


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
