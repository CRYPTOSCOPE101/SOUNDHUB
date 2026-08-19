"""GraphQL types for SoundHub — auto-mapped from SQLAlchemy models."""
from __future__ import annotations
from typing import Optional, List
import strawberry


# ══════════════════════════════════════════════════════════════════════════════
# Core Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class UserType:
    id: int
    username: str
    bio: str
    specialty: str
    location: str
    created_at: str


@strawberry.type
class BranchType:
    id: int
    name: str
    head_commit_id: Optional[int]
    is_default: bool
    head_message: str = ""
    head_sha: Optional[str] = None
    head_author: Optional[str] = None
    commit_count: int = 0
    created_at: str


@strawberry.type
class FileSnapshotType:
    id: int
    path: str
    blob_sha: str
    size: int


@strawberry.type
class CommitType:
    id: int
    message: str
    author: UserType
    files: List[FileSnapshotType]
    created_at: str


@strawberry.type
class ProjectType:
    id: int
    name: str
    slug: str
    description: str
    default_branch: str
    owner: UserType
    branches: List[BranchType]
    created_at: str
    updated_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Review Session Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class ReviewVersionType:
    id: int
    number: int
    label: str
    message: str
    status: str
    filename: str
    blob_sha: str
    size: int
    duration_s: float
    audio_format: str
    round_number: int
    created_at: str


@strawberry.type
class ReviewCommentType:
    id: int
    time_s: float
    body: str
    author_name: Optional[str]
    resolved: bool
    status: str
    created_at: str


@strawberry.type
class ReviewApprovalType:
    id: int
    scope: str
    approved: bool
    note: str
    approver_name: str
    role: str
    created_at: str


@strawberry.type
class ReviewSessionType:
    id: int
    name: str
    status: str
    share_token: str
    owner: UserType
    versions: List[ReviewVersionType]
    approvals: List[ReviewApprovalType]
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Pull Request Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class PullRequestType:
    id: int
    source_branch: str
    target_branch: str
    title: str
    description: str
    status: str
    created_at: str


@strawberry.type
class PullRequestReviewType:
    id: int
    reviewer_name: str
    decision: str
    body: str
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Task Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class MusicTaskType:
    id: int
    title: str
    body: str
    type: str
    priority: str
    status: str
    milestone: str
    created_at: str
    updated_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Git Tag Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class GitTagType:
    id: int
    name: str
    message: str
    is_release: bool
    created_at: str


@strawberry.type
class ReleaseNoteType:
    id: int
    title: str
    body: str
    highlights: str
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Discussion Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class DiscussionType:
    id: int
    title: str
    body: str
    category: str
    pinned: bool
    locked: bool
    created_at: str


@strawberry.type
class DiscussionCommentType:
    id: int
    body: str
    author_name: Optional[str]
    is_answer: bool
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Wiki Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class WikiPageType:
    id: int
    slug: str
    title: str
    content: str
    version: int
    created_at: str
    updated_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Sprint Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class SprintType:
    id: int
    name: str
    goal: str
    state: str
    velocity: int
    start_date: Optional[str]
    end_date: Optional[str]
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Retrospective Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class RetroItemType:
    id: int
    category: str
    content: str
    votes: int
    author_id: int
    created_at: str


@strawberry.type
class RetrospectiveType:
    id: int
    name: str
    state: str
    sprint_id: Optional[int]
    item_count: int
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Test Plan Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class TestPlanType:
    id: int
    name: str
    description: str
    state: str
    created_at: str


@strawberry.type
class TestCaseType:
    id: int
    title: str
    description: str
    priority: str
    state: str
    created_at: str


@strawberry.type
class TestRunType:
    id: int
    name: str
    state: str
    total: int
    passed: int
    failed: int
    skipped: int
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Epic Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class EpicType:
    id: int
    title: str
    description: str
    color: str
    status: str
    task_count: int
    start_date: Optional[str]
    due_date: Optional[str]
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Milestone Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class MilestoneType:
    id: int
    title: str
    description: str
    status: str
    due_date: Optional[str]
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Kanban Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class KanbanBoardType:
    id: int
    name: str
    created_at: str


@strawberry.type
class KanbanColumnType:
    id: int
    name: str
    position: int
    color: str


@strawberry.type
class KanbanCardType:
    id: int
    title: str
    description: str
    position: int
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Workflow Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class WorkflowType:
    id: int
    name: str
    filename: str
    enabled: bool
    created_at: str


@strawberry.type
class WorkflowRunType:
    id: int
    status: str
    trigger: str
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Incident Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class IncidentType:
    id: int
    title: str
    description: str
    severity: str
    status: str
    created_at: str


@strawberry.type
class ErrorType:
    id: int
    message: str
    severity: str
    status: str
    occurrence_count: int
    last_seen: str


# ══════════════════════════════════════════════════════════════════════════════
# Feature Flag Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class FeatureFlagType:
    id: int
    name: str
    description: str
    enabled: bool
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# OKR Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class KeyResultType:
    id: int
    title: str
    target_value: float
    current_value: float
    unit: str


@strawberry.type
class ObjectiveType:
    id: int
    title: str
    description: str
    period: str
    progress: int
    key_results: List[KeyResultType]
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Artifact Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class ArtifactFeedType:
    id: int
    name: str
    feed_type: str
    visibility: str
    created_at: str


@strawberry.type
class ArtifactPackageType:
    id: int
    name: str
    version: str
    size: int
    download_count: int
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Search Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class SearchResultType:
    type: str
    id: int
    title: str
    snippet: str
    tags: str
    score: float
    updated_at: str


@strawberry.type
class SearchFacetsType:
    entity_type: strawberry.scalars.JSON


@strawberry.type
class SearchResultsType:
    results: List[SearchResultType]
    total: int
    query: str
    took_ms: float
    facets: Optional[SearchFacetsType] = None


# ══════════════════════════════════════════════════════════════════════════════
# Dashboard / Stats Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class IndexStatsType:
    total_indexed: int
    by_type: strawberry.scalars.JSON


@strawberry.type
class PopularQueryType:
    query: str
    count: int
    avg_results: float


# ══════════════════════════════════════════════════════════════════════════════
# Time Tracking Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class TimeEntryType:
    id: int
    hours: int
    description: str
    date: str


@strawberry.type
class TimeTrackingType:
    total_minutes: int
    entries: List[TimeEntryType]


# ══════════════════════════════════════════════════════════════════════════════
# Deployment Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class DeploymentType:
    id: int
    environment_id: int
    status: str
    deployed_at: Optional[str]
    created_at: str


# ══════════════════════════════════════════════════════════════════════════════
# Status Page Types
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class StatusPageComponentType:
    id: int
    name: str
    status: str


@strawberry.type
class StatusPageIncidentType:
    id: int
    title: str
    status: str
    impact: str
    created_at: str
