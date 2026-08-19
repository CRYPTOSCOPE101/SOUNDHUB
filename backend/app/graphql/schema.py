"""GraphQL schema for SoundHub — queries and mutations for all 235+ endpoints."""
from __future__ import annotations
from typing import Optional, List
import strawberry
from strawberry.scalars import JSON

from .types import (
    ProjectType, UserType, BranchType, CommitType, FileSnapshotType,
    ReviewSessionType, ReviewVersionType, ReviewCommentType, ReviewApprovalType,
    PullRequestType, PullRequestReviewType,
    MusicTaskType, GitTagType, ReleaseNoteType,
    DiscussionType, DiscussionCommentType,
    WikiPageType, SprintType, RetrospectiveType, RetroItemType,
    TestPlanType, TestCaseType, TestRunType,
    EpicType, MilestoneType,
    KanbanBoardType, KanbanColumnType, KanbanCardType,
    WorkflowType, WorkflowRunType,
    IncidentType, ErrorType, FeatureFlagType,
    ObjectiveType, KeyResultType,
    ArtifactFeedType, ArtifactPackageType,
    TimeEntryType, TimeTrackingType, DeploymentType,
    StatusPageComponentType, StatusPageIncidentType,
    SearchResultType, SearchResultsType, SearchFacetsType,
    IndexStatsType, PopularQueryType,
)

from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import (
    Project, User, Branch, Commit, FileSnapshot,
    ReviewSession, ReviewVersion, ReviewComment, ReviewApproval,
    PullRequest, PullRequestReview,
    MusicTask, GitTag, ReleaseNote,
    Discussion, DiscussionComment,
    WikiPage, Sprint, Retrospective, RetroItem,
    TestPlan, TestSuite, TestCase, TestRun, TestResult,
    Epic, Milestone,
    KanbanBoard, KanbanColumn, KanbanCard,
    Workflow, WorkflowRun,
    Incident, Error as ErrorModel, FeatureFlag,
    Objective, KeyResult,
    ArtifactFeed, ArtifactPackage,
    TimeEntry, Deployment,
    StatusPageComponent, StatusPageIncident,
)
from ..services.search_engine import search as fts_search, get_index_stats, get_popular_queries


def _db():
    """Get a database session."""
    return SessionLocal()


def _user_to_gql(u: User) -> UserType:
    return UserType(id=u.id, username=u.username, bio=u.bio or "",
                    specialty=u.specialty or "", location=u.location or "",
                    created_at=str(u.created_at))


def _project_to_gql(p: Project, db: Session) -> ProjectType:
    branches = db.scalars(select(Branch).where(Branch.project_id == p.id)).all()
    return ProjectType(
        id=p.id, name=p.name, slug=p.slug, description=p.description or "",
        default_branch=p.default_branch, owner=_user_to_gql(p.owner),
        branches=[_branch_to_gql(b, db) for b in branches],
        created_at=str(p.created_at), updated_at=str(p.updated_at),
    )


def _branch_to_gql(b: Branch, db: Session) -> BranchType:
    head = db.get(Commit, b.head_commit_id) if b.head_commit_id else None
    chain_len = 0
    c = head
    while c:
        chain_len += 1
        c = db.get(Commit, c.parent_id) if c.parent_id else None
    return BranchType(
        id=b.id, name=b.name, head_commit_id=b.head_commit_id,
        is_default=b.is_default, head_message=head.message if head else "",
        head_sha=str(head.id).zfill(7) if head else None,
        head_author=head.author.username if head else None,
        commit_count=chain_len, created_at=str(b.created_at),
    )


def _commit_to_gql(c: Commit, db: Session) -> CommitType:
    files = db.scalars(select(FileSnapshot).where(FileSnapshot.commit_id == c.id)).all()
    return CommitType(
        id=c.id, message=c.message or "", author=_user_to_gql(c.author),
        files=[FileSnapshotType(id=f.id, path=f.path, blob_sha=f.blob_sha, size=f.size) for f in files],
        created_at=str(c.created_at),
    )


def _session_to_gql(s: ReviewSession, db: Session) -> ReviewSessionType:
    versions = db.scalars(select(ReviewVersion).where(ReviewVersion.session_id == s.id)).all()
    approvals = db.scalars(select(ReviewApproval).where(ReviewApproval.session_id == s.id)).all()
    return ReviewSessionType(
        id=s.id, name=s.name, status=s.status, share_token=s.share_token,
        owner=_user_to_gql(s.owner),
        versions=[_version_to_gql(v) for v in versions],
        approvals=[_approval_to_gql(a) for a in approvals],
        created_at=str(s.created_at),
    )


def _version_to_gql(v: ReviewVersion) -> ReviewVersionType:
    return ReviewVersionType(
        id=v.id, number=v.number, label=v.label, message=v.message or "",
        status=v.status, filename=v.filename, blob_sha=v.blob_sha,
        size=v.size, duration_s=v.duration_s, audio_format=v.audio_format,
        round_number=v.round_number, created_at=str(v.created_at),
    )


def _approval_to_gql(a: ReviewApproval) -> ReviewApprovalType:
    return ReviewApprovalType(
        id=a.id, scope=a.scope, approved=a.approved, note=a.note or "",
        approver_name=a.approver_name or "", role=a.role or "",
        created_at=str(a.created_at),
    )


def _pr_to_gql(pr: PullRequest) -> PullRequestType:
    return PullRequestType(
        id=pr.id, source_branch=pr.source_branch, target_branch=pr.target_branch,
        title=pr.title, description=pr.description or "", status=pr.status,
        created_at=str(pr.created_at),
    )


def _task_to_gql(t: MusicTask) -> MusicTaskType:
    return MusicTaskType(
        id=t.id, title=t.title, body=t.body or "", type=t.type,
        priority=t.priority, status=t.status, milestone=t.milestone or "",
        created_at=str(t.created_at), updated_at=str(t.updated_at),
    )


def _tag_to_gql(t: GitTag) -> GitTagType:
    return GitTagType(id=t.id, name=t.name, message=t.message or "",
                      is_release=t.is_release, created_at=str(t.created_at))


def _discussion_to_gql(d: Discussion) -> DiscussionType:
    return DiscussionType(id=d.id, title=d.title, body=d.body or "",
                          category=d.category, pinned=d.pinned, locked=d.locked,
                          created_at=str(d.created_at))


def _wiki_to_gql(w: WikiPage) -> WikiPageType:
    return WikiPageType(id=w.id, slug=w.slug, title=w.title, content=w.content or "",
                         version=w.version, created_at=str(w.created_at),
                         updated_at=str(w.updated_at))


def _sprint_to_gql(s: Sprint) -> SprintType:
    return SprintType(id=s.id, name=s.name, goal=s.goal or "", state=s.state,
                       velocity=s.velocity, start_date=str(s.start_date) if s.start_date else None,
                       end_date=str(s.end_date) if s.end_date else None,
                       created_at=str(s.created_at))


def _epic_to_gql(e: Epic, db: Session) -> EpicType:
    from ..models import EpicTaskLink
    tc = db.scalar(select(EpicTaskLink).where(EpicTaskLink.epic_id == e.id))
    task_count = len(db.scalars(select(EpicTaskLink).where(EpicTaskLink.epic_id == e.id)).all())
    return EpicType(id=e.id, title=e.title, description=e.description or "",
                     color=e.color or "#6366f1", status=e.status, task_count=task_count,
                     start_date=str(e.start_date) if e.start_date else None,
                     due_date=str(e.due_date) if e.due_date else None,
                     created_at=str(e.created_at))


def _milestone_to_gql(m: Milestone) -> MilestoneType:
    return MilestoneType(id=m.id, title=m.title, description=m.description or "",
                          status=m.status, due_date=str(m.due_date) if m.due_date else None,
                          created_at=str(m.created_at))


def _workflow_to_gql(w: Workflow) -> WorkflowType:
    return WorkflowType(id=w.id, name=w.name, filename=w.filename,
                         enabled=w.enabled, created_at=str(w.created_at))


def _incident_to_gql(i: Incident) -> IncidentType:
    return IncidentType(id=i.id, title=i.title, description=i.description or "",
                         severity=i.severity, status=i.status, created_at=str(i.created_at))


def _error_to_gql(e: ErrorModel) -> ErrorType:
    return ErrorType(id=e.id, message=e.message, severity=e.severity, status=e.status,
                      occurrence_count=e.occurrence_count, last_seen=str(e.last_seen))


def _flag_to_gql(f: FeatureFlag) -> FeatureFlagType:
    return FeatureFlagType(id=f.id, name=f.name, description=f.description or "",
                            enabled=f.enabled, created_at=str(f.created_at))


def _objective_to_gql(o: Objective, db: Session) -> ObjectiveType:
    krs = db.scalars(select(KeyResult).where(KeyResult.objective_id == o.id)).all()
    return ObjectiveType(
        id=o.id, title=o.title, description=o.description or "",
        period=o.period, progress=o.progress, created_at=str(o.created_at),
        key_results=[KeyResultType(id=kr.id, title=kr.title, target_value=kr.target_value,
                                    current_value=kr.current_value, unit=kr.unit or "") for kr in krs],
    )


def _feed_to_gql(f: ArtifactFeed) -> ArtifactFeedType:
    return ArtifactFeedType(id=f.id, name=f.name, feed_type=f.feed_type,
                             visibility=f.visibility, created_at=str(f.created_at))


# ══════════════════════════════════════════════════════════════════════════════
# Query
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.type
class Query:
    # ── Projects ─────────────────────────────────────────────────────────
    @strawberry.field
    def projects(self) -> List[ProjectType]:
        db = _db()
        try:
            projects = db.scalars(select(Project)).all()
            return [_project_to_gql(p, db) for p in projects]
        finally:
            db.close()

    @strawberry.field
    def project(self, id: int) -> Optional[ProjectType]:
        db = _db()
        try:
            p = db.get(Project, id)
            return _project_to_gql(p, db) if p else None
        finally:
            db.close()

    # ── Branches ─────────────────────────────────────────────────────────
    @strawberry.field
    def branches(self, project_id: int) -> List[BranchType]:
        db = _db()
        try:
            bs = db.scalars(select(Branch).where(Branch.project_id == project_id)).all()
            return [_branch_to_gql(b, db) for b in bs]
        finally:
            db.close()

    # ── Commits ──────────────────────────────────────────────────────────
    @strawberry.field
    def commits(self, project_id: int, limit: int = 20) -> List[CommitType]:
        db = _db()
        try:
            cs = db.scalars(select(Commit).where(Commit.project_id == project_id)
                            .order_by(Commit.id.desc()).limit(limit)).all()
            return [_commit_to_gql(c, db) for c in cs]
        finally:
            db.close()

    @strawberry.field
    def commit(self, project_id: int, commit_id: int) -> Optional[CommitType]:
        db = _db()
        try:
            c = db.get(Commit, commit_id)
            if c and c.project_id == project_id:
                return _commit_to_gql(c, db)
            return None
        finally:
            db.close()

    # ── Review Sessions ──────────────────────────────────────────────────
    @strawberry.field
    def sessions(self) -> List[ReviewSessionType]:
        db = _db()
        try:
            ss = db.scalars(select(ReviewSession)).all()
            return [_session_to_gql(s, db) for s in ss]
        finally:
            db.close()

    @strawberry.field
    def session(self, id: int) -> Optional[ReviewSessionType]:
        db = _db()
        try:
            s = db.get(ReviewSession, id)
            return _session_to_gql(s, db) if s else None
        finally:
            db.close()

    # ── Pull Requests ────────────────────────────────────────────────────
    @strawberry.field
    def pull_requests(self, project_id: int) -> List[PullRequestType]:
        db = _db()
        try:
            prs = db.scalars(select(PullRequest).where(PullRequest.project_id == project_id)).all()
            return [_pr_to_gql(pr) for pr in prs]
        finally:
            db.close()

    # ── Tasks ────────────────────────────────────────────────────────────
    @strawberry.field
    def tasks(self, project_id: int) -> List[MusicTaskType]:
        db = _db()
        try:
            ts = db.scalars(select(MusicTask).where(MusicTask.project_id == project_id)).all()
            return [_task_to_gql(t) for t in ts]
        finally:
            db.close()

    # ── Tags ─────────────────────────────────────────────────────────────
    @strawberry.field
    def tags(self, project_id: int) -> List[GitTagType]:
        db = _db()
        try:
            ts = db.scalars(select(GitTag).where(GitTag.project_id == project_id)).all()
            return [_tag_to_gql(t) for t in ts]
        finally:
            db.close()

    # ── Discussions ──────────────────────────────────────────────────────
    @strawberry.field
    def discussions(self, project_id: int) -> List[DiscussionType]:
        db = _db()
        try:
            ds = db.scalars(select(Discussion).where(Discussion.project_id == project_id)).all()
            return [_discussion_to_gql(d) for d in ds]
        finally:
            db.close()

    # ── Wiki ─────────────────────────────────────────────────────────────
    @strawberry.field
    def wiki_pages(self, project_id: int) -> List[WikiPageType]:
        db = _db()
        try:
            ws = db.scalars(select(WikiPage).where(WikiPage.project_id == project_id)).all()
            return [_wiki_to_gql(w) for w in ws]
        finally:
            db.close()

    # ── Sprints ──────────────────────────────────────────────────────────
    @strawberry.field
    def sprints(self, project_id: int) -> List[SprintType]:
        db = _db()
        try:
            ss = db.scalars(select(Sprint).where(Sprint.project_id == project_id)).all()
            return [_sprint_to_gql(s) for s in ss]
        finally:
            db.close()

    # ── Epics ────────────────────────────────────────────────────────────
    @strawberry.field
    def epics(self, project_id: int) -> List[EpicType]:
        db = _db()
        try:
            es = db.scalars(select(Epic).where(Epic.project_id == project_id)).all()
            return [_epic_to_gql(e, db) for e in es]
        finally:
            db.close()

    # ── Milestones ───────────────────────────────────────────────────────
    @strawberry.field
    def milestones(self, project_id: int) -> List[MilestoneType]:
        db = _db()
        try:
            ms = db.scalars(select(Milestone).where(Milestone.project_id == project_id)).all()
            return [_milestone_to_gql(m) for m in ms]
        finally:
            db.close()

    # ── Workflows ────────────────────────────────────────────────────────
    @strawberry.field
    def workflows(self, project_id: int) -> List[WorkflowType]:
        db = _db()
        try:
            ws = db.scalars(select(Workflow).where(Workflow.project_id == project_id)).all()
            return [_workflow_to_gql(w) for w in ws]
        finally:
            db.close()

    # ── Incidents ────────────────────────────────────────────────────────
    @strawberry.field
    def incidents(self, project_id: int) -> List[IncidentType]:
        db = _db()
        try:
            is_ = db.scalars(select(Incident).where(Incident.project_id == project_id)).all()
            return [_incident_to_gql(i) for i in is_]
        finally:
            db.close()

    # ── Errors ───────────────────────────────────────────────────────────
    @strawberry.field
    def errors(self, project_id: int) -> List[ErrorType]:
        db = _db()
        try:
            es = db.scalars(select(ErrorModel).where(ErrorModel.project_id == project_id)).all()
            return [_error_to_gql(e) for e in es]
        finally:
            db.close()

    # ── Feature Flags ────────────────────────────────────────────────────
    @strawberry.field
    def feature_flags(self, project_id: int) -> List[FeatureFlagType]:
        db = _db()
        try:
            fs = db.scalars(select(FeatureFlag).where(FeatureFlag.project_id == project_id)).all()
            return [_flag_to_gql(f) for f in fs]
        finally:
            db.close()

    # ── OKRs ─────────────────────────────────────────────────────────────
    @strawberry.field
    def objectives(self, project_id: int) -> List[ObjectiveType]:
        db = _db()
        try:
            os_ = db.scalars(select(Objective).where(Objective.project_id == project_id)).all()
            return [_objective_to_gql(o, db) for o in os_]
        finally:
            db.close()

    # ── Artifact Feeds ──────────────────────────────────────────────────
    @strawberry.field
    def artifact_feeds(self, project_id: int) -> List[ArtifactFeedType]:
        db = _db()
        try:
            fs = db.scalars(select(ArtifactFeed).where(ArtifactFeed.project_id == project_id)).all()
            return [_feed_to_gql(f) for f in fs]
        finally:
            db.close()

    # ── Time Tracking ────────────────────────────────────────────────────
    @strawberry.field
    def time_tracking(self, project_id: int) -> TimeTrackingType:
        db = _db()
        try:
            entries = db.scalars(select(TimeEntry).where(TimeEntry.project_id == project_id)).all()
            total = sum(e.hours for e in entries)
            return TimeTrackingType(
                total_minutes=total,
                entries=[TimeEntryType(id=e.id, hours=e.hours, description=e.description or "",
                                       date=str(e.date)) for e in entries],
            )
        finally:
            db.close()

    # ── Deployments ──────────────────────────────────────────────────────
    @strawberry.field
    def deployments(self, project_id: int) -> List[DeploymentType]:
        db = _db()
        try:
            ds = db.scalars(select(Deployment).where(Deployment.project_id == project_id)).all()
            return [DeploymentType(id=d.id, environment_id=d.environment_id, status=d.status,
                                    deployed_at=str(d.deployed_at) if d.deployed_at else None,
                                    created_at=str(d.created_at)) for d in ds]
        finally:
            db.close()

    # ── Status Page ──────────────────────────────────────────────────────
    @strawberry.field
    def status_components(self, project_id: int) -> List[StatusPageComponentType]:
        db = _db()
        try:
            cs = db.scalars(select(StatusPageComponent).where(StatusPageComponent.project_id == project_id)).all()
            return [StatusPageComponentType(id=c.id, name=c.name, status=c.status) for c in cs]
        finally:
            db.close()

    # ── Search ───────────────────────────────────────────────────────────
    @strawberry.field
    def search(self, query: str, entity_type: Optional[str] = None,
               project_id: Optional[int] = None, limit: int = 20) -> SearchResultsType:
        result = fts_search(query=query, entity_type=entity_type,
                            project_id=project_id, limit=limit)
        return SearchResultsType(
            results=[SearchResultType(type=r["type"], id=r["id"], title=r["title"],
                                       snippet=r.get("snippet", ""), tags=r.get("tags", ""),
                                       score=r["score"], updated_at=r.get("updated_at", ""))
                     for r in result["results"]],
            total=result["total"], query=result["query"], took_ms=result["took_ms"],
        )

    # ── Search Stats ─────────────────────────────────────────────────────
    @strawberry.field
    def search_stats(self) -> IndexStatsType:
        stats = get_index_stats()
        return IndexStatsType(total_indexed=stats["total_indexed"],
                               by_type=stats["by_type"])

    @strawberry.field
    def popular_searches(self, limit: int = 10) -> List[PopularQueryType]:
        qs = get_popular_queries(limit)
        return [PopularQueryType(query=q["query"], count=q["count"],
                                  avg_results=q["avg_results"]) for q in qs]

    # ── Users ────────────────────────────────────────────────────────────
    @strawberry.field
    def user(self, id: int) -> Optional[UserType]:
        db = _db()
        try:
            u = db.get(User, id)
            return _user_to_gql(u) if u else None
        finally:
            db.close()

    @strawberry.field
    def users(self) -> List[UserType]:
        db = _db()
        try:
            us = db.scalars(select(User)).all()
            return [_user_to_gql(u) for u in us]
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════════════════
# Mutations
# ══════════════════════════════════════════════════════════════════════════════

@strawberry.input
class ProjectInput:
    name: str
    description: str = ""
    slug: str = ""


@strawberry.input
class TaskInput:
    title: str
    body: str = ""
    type: str = "task"
    priority: str = "medium"


@strawberry.input
class DiscussionInput:
    title: str
    body: str = ""


@strawberry.input
class WikiInput:
    slug: str
    title: str
    content: str = ""


@strawberry.input
class SprintInput:
    name: str
    goal: str = ""


@strawberry.input
class RetroInput:
    name: str
    sprint_id: Optional[int] = None


@strawberry.input
class RetroItemInput:
    category: str
    content: str


@strawberry.input
class EpicInput:
    title: str
    description: str = ""
    color: str = "#6366f1"


@strawberry.input
class MilestoneInput:
    title: str
    description: str = ""
    due_date: Optional[str] = None


@strawberry.input
class FeatureFlagInput:
    name: str
    description: str = ""


@strawberry.input
class IncidentInput:
    title: str
    description: str = ""
    severity: str = "minor"


@strawberry.input
class TagInput:
    name: str
    commit_id: int
    message: str = ""


@strawberry.type
class Mutation:
    # ── Project ──────────────────────────────────────────────────────────
    @strawberry.mutation
    def create_project(self, name: str, description: str = "", owner_id: int = 1) -> ProjectType:
        db = _db()
        try:
            slug = name.lower().replace(" ", "-")[:160]
            p = Project(owner_id=owner_id, name=name, slug=slug, description=description)
            db.add(p)
            db.commit()
            db.refresh(p)
            db.add(Branch(project_id=p.id, name="main", head_commit_id=None))
            db.commit()
            return _project_to_gql(p, db)
        finally:
            db.close()

    # ── Tasks ────────────────────────────────────────────────────────────
    @strawberry.mutation
    def create_task(self, project_id: int, title: str, body: str = "",
                    type: str = "task", priority: str = "medium",
                    author_id: int = 1) -> MusicTaskType:
        db = _db()
        try:
            t = MusicTask(project_id=project_id, author_id=author_id, title=title,
                          body=body, type=type, priority=priority)
            db.add(t)
            db.commit()
            db.refresh(t)
            return _task_to_gql(t)
        finally:
            db.close()

    # ── Discussions ──────────────────────────────────────────────────────
    @strawberry.mutation
    def create_discussion(self, project_id: int, title: str, body: str = "",
                          author_id: int = 1) -> DiscussionType:
        db = _db()
        try:
            d = Discussion(project_id=project_id, author_id=author_id, title=title, body=body)
            db.add(d)
            db.commit()
            db.refresh(d)
            return _discussion_to_gql(d)
        finally:
            db.close()

    # ── Wiki ─────────────────────────────────────────────────────────────
    @strawberry.mutation
    def create_wiki_page(self, project_id: int, slug: str, title: str,
                         content: str = "", author_id: int = 1) -> WikiPageType:
        db = _db()
        try:
            w = WikiPage(project_id=project_id, slug=slug, title=title,
                         content=content, author_id=author_id)
            db.add(w)
            db.commit()
            db.refresh(w)
            return _wiki_to_gql(w)
        finally:
            db.close()

    # ── Sprints ──────────────────────────────────────────────────────────
    @strawberry.mutation
    def create_sprint(self, project_id: int, name: str, goal: str = "") -> SprintType:
        db = _db()
        try:
            s = Sprint(project_id=project_id, name=name, goal=goal)
            db.add(s)
            db.commit()
            db.refresh(s)
            return _sprint_to_gql(s)
        finally:
            db.close()

    @strawberry.mutation
    def update_sprint_state(self, project_id: int, sprint_id: int, state: str) -> SprintType:
        db = _db()
        try:
            s = db.get(Sprint, sprint_id)
            if s and s.project_id == project_id:
                s.state = state
                db.commit()
                db.refresh(s)
                return _sprint_to_gql(s)
            raise ValueError("Sprint not found")
        finally:
            db.close()

    # ── Retros ───────────────────────────────────────────────────────────
    @strawberry.mutation
    def create_retro(self, project_id: int, name: str, author_id: int = 1,
                     sprint_id: Optional[int] = None) -> RetrospectiveType:
        db = _db()
        try:
            r = Retrospective(project_id=project_id, name=name, author_id=author_id,
                              sprint_id=sprint_id)
            db.add(r)
            db.commit()
            db.refresh(r)
            return RetrospectiveType(id=r.id, name=r.name, state=r.state,
                                      sprint_id=r.sprint_id, item_count=0,
                                      created_at=str(r.created_at))
        finally:
            db.close()

    @strawberry.mutation
    def add_retro_item(self, project_id: int, retro_id: int, category: str,
                       content: str, author_id: int = 1) -> RetroItemType:
        db = _db()
        try:
            item = RetroItem(retrospective_id=retro_id, author_id=author_id,
                             category=category, content=content)
            db.add(item)
            db.commit()
            db.refresh(item)
            return RetroItemType(id=item.id, category=item.category, content=item.content,
                                  votes=item.votes, author_id=item.author_id,
                                  created_at=str(item.created_at))
        finally:
            db.close()

    @strawberry.mutation
    def vote_retro_item(self, project_id: int, item_id: int) -> RetroItemType:
        db = _db()
        try:
            item = db.get(RetroItem, item_id)
            if item:
                item.votes += 1
                db.commit()
                db.refresh(item)
                return RetroItemType(id=item.id, category=item.category, content=item.content,
                                      votes=item.votes, author_id=item.author_id,
                                      created_at=str(item.created_at))
            raise ValueError("Item not found")
        finally:
            db.close()

    # ── Epics ────────────────────────────────────────────────────────────
    @strawberry.mutation
    def create_epic(self, project_id: int, title: str, description: str = "",
                    color: str = "#6366f1", author_id: int = 1) -> EpicType:
        db = _db()
        try:
            e = Epic(project_id=project_id, author_id=author_id, title=title,
                     description=description, color=color)
            db.add(e)
            db.commit()
            db.refresh(e)
            return _epic_to_gql(e, db)
        finally:
            db.close()

    # ── Milestones ───────────────────────────────────────────────────────
    @strawberry.mutation
    def create_milestone(self, project_id: int, title: str,
                         description: str = "") -> MilestoneType:
        db = _db()
        try:
            m = Milestone(project_id=project_id, title=title, description=description)
            db.add(m)
            db.commit()
            db.refresh(m)
            return _milestone_to_gql(m)
        finally:
            db.close()

    # ── Feature Flags ────────────────────────────────────────────────────
    @strawberry.mutation
    def create_feature_flag(self, project_id: int, name: str,
                            description: str = "") -> FeatureFlagType:
        db = _db()
        try:
            f = FeatureFlag(project_id=project_id, name=name, description=description)
            db.add(f)
            db.commit()
            db.refresh(f)
            return _flag_to_gql(f)
        finally:
            db.close()

    @strawberry.mutation
    def toggle_feature_flag(self, project_id: int, flag_id: int,
                            enabled: bool) -> FeatureFlagType:
        db = _db()
        try:
            f = db.get(FeatureFlag, flag_id)
            if f and f.project_id == project_id:
                f.enabled = enabled
                db.commit()
                db.refresh(f)
                return _flag_to_gql(f)
            raise ValueError("Flag not found")
        finally:
            db.close()

    # ── Incidents ────────────────────────────────────────────────────────
    @strawberry.mutation
    def create_incident(self, project_id: int, title: str,
                        description: str = "", severity: str = "minor") -> IncidentType:
        db = _db()
        try:
            i = Incident(project_id=project_id, title=title,
                         description=description, severity=severity)
            db.add(i)
            db.commit()
            db.refresh(i)
            return _incident_to_gql(i)
        finally:
            db.close()

    # ── Tags ─────────────────────────────────────────────────────────────
    @strawberry.mutation
    def create_tag(self, project_id: int, name: str, commit_id: int,
                   message: str = "", creator_id: int = 1) -> GitTagType:
        db = _db()
        try:
            t = GitTag(project_id=project_id, name=name, commit_id=commit_id,
                       message=message, created_by=creator_id)
            db.add(t)
            db.commit()
            db.refresh(t)
            return _tag_to_gql(t)
        finally:
            db.close()

    # ── Delete operations ────────────────────────────────────────────────
    @strawberry.mutation
    def delete_project(self, id: int) -> bool:
        db = _db()
        try:
            p = db.get(Project, id)
            if p:
                db.delete(p)
                db.commit()
                return True
            return False
        finally:
            db.close()

    @strawberry.mutation
    def delete_task(self, project_id: int, task_id: int) -> bool:
        db = _db()
        try:
            t = db.get(MusicTask, task_id)
            if t and t.project_id == project_id:
                db.delete(t)
                db.commit()
                return True
            return False
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════════════════
# Schema
# ══════════════════════════════════════════════════════════════════════════════

schema = strawberry.Schema(query=Query, mutation=Mutation)
