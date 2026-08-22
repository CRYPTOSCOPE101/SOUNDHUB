"""Projects router — CRUD, commits, branches, merge, compare.

GitHub-quality branch management:
  - create_branch copies HEAD from source (like git checkout -b)
  - list_branches returns real commit metadata
  - delete_branch with default-branch protection
  - merge (fast-forward, merge commit, squash)
  - compare (ahead/behind/files changed)
"""
import hashlib
import json
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Branch,
    Commit,
    FileSnapshot,
    Project,
    StorageObject,
    User,
    utcnow,
    AudioCheck,
)
from ..services import job_queue
from ..schemas import (
    BranchCreate,
    BranchOut,
    CommitCreate,
    CommitOut,
    CompareOut,
    DiffChangeOut,
    DiffOut,
    MergeCreate,
    MergeOut,
    ProjectCreate,
    ProjectFileOut,
    ProjectOut,
    ProjectUpdate,
    PushOut,
    TreeOut,
)
from ..security import get_current_user
from ..services import storage, versioning, loudness
from .integrations import dispatch_event
from ..config import MAX_UPLOAD_SIZE

router = APIRouter(prefix="/api/projects", tags=["projects"])

DAW_EXTENSIONS = {"als", "cpr", "rpp", "flp", "logic", "ptx", "band"}
DAW_MAP = {"als": "Ableton Live", "cpr": "Cubase", "rpp": "REAPER", "flp": "FL Studio", "logic": "Logic Pro", "ptx": "Pro Tools"}


# ── helpers ──────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:160]


def _get_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def _get_branch(db: Session, project_id: int, name: str) -> Branch:
    branch = db.scalar(
        select(Branch).where(Branch.project_id == project_id, Branch.name == name)
    )
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Branch '{name}' not found")
    return branch


def _commit_chain_length(db: Session, commit_id: int | None) -> int:
    """Walk parent pointers and count commits."""
    if commit_id is None:
        return 0
    count = 0
    current = commit_id
    while current is not None:
        count += 1
        c = db.get(Commit, current)
        if c is None:
            break
        current = c.parent_id
    return count


def _branch_out(db: Session, b: Branch, project_default: str) -> BranchOut:
    """Build BranchOut with real commit metadata."""
    head = db.get(Commit, b.head_commit_id) if b.head_commit_id else None
    commit_count = _commit_chain_length(db, b.head_commit_id)
    return BranchOut(
        name=b.name,
        is_default=b.name == project_default,
        head_commit_id=b.head_commit_id,
        head_message=head.message if head else "",
        head_sha=_short_sha(head) if head else None,
        head_author=head.author.username if head and head.author else "",
        head_date=head.created_at if head else None,
        commit_count=commit_count,
        created_at=b.created_at,
    )


def _short_sha(commit: Commit | None) -> str | None:
    if commit is None:
        return None
    return hashlib.sha256(f"soundhub:{commit.id}".encode()).hexdigest()[:7]


def _collect_tree(db: Session, commit_id: int | None) -> dict[str, FileSnapshot]:
    """Walk the commit chain and collect the latest snapshot per path."""
    tree: dict[str, FileSnapshot] = {}
    current = commit_id
    visited = set()
    while current is not None and current not in visited:
        visited.add(current)
        snaps = db.scalars(
            select(FileSnapshot).where(FileSnapshot.commit_id == current)
        ).all()
        for s in snaps:
            if s.path not in tree:
                tree[s.path] = s
        c = db.get(Commit, current)
        if c is None:
            break
        current = c.parent_id
    return tree


def _merge_trees(
    base: dict[str, FileSnapshot],
    head: dict[str, FileSnapshot],
) -> tuple[dict[str, FileSnapshot], list[str]]:
    """Three-way merge: base → head. Returns merged tree + conflicts."""
    merged = dict(base)
    conflicts: list[str] = []

    for path, snap in head.items():
        if path not in base:
            # new file — take it
            merged[path] = snap
        elif base[path].blob_sha != snap.blob_sha:
            # modified in head — take head version (no content merge for binary DAW files)
            merged[path] = snap
        # else: unchanged, keep base

    return merged, conflicts


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ProjectOut])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc())
    ).all()
    return [ProjectOut.model_validate(p, from_attributes=True) for p in projects]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    slug = _slugify(payload.name)
    existing = db.scalar(
        select(Project).where(Project.owner_id == user.id, Project.slug == slug)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A project with this name already exists")
    project = Project(owner_id=user.id, name=payload.name.strip(), slug=slug, description=payload.description)
    db.add(project)
    db.flush()
    branch = Branch(project_id=project.id, name="main")
    db.add(branch)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project, from_attributes=True)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = _get_project(db, project_id, user)
    return ProjectOut.model_validate(project, from_attributes=True)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = _get_project(db, project_id, user)
    if payload.name is not None:
        project.name = payload.name.strip()
        project.slug = _slugify(payload.name)
    if payload.description is not None:
        project.description = payload.description
    project.updated_at = utcnow()
    db.commit()
    return ProjectOut.model_validate(project, from_attributes=True)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = _get_project(db, project_id, user)
    db.delete(project)
    db.commit()


# ── Branches ─────────────────────────────────────────────────────────────────

@router.get("/{project_id}/branches", response_model=list[BranchOut])
def list_branches(
    project_id: int,
    search: str = Query("", description="Filter branches by name"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_project(db, project_id, user)
    query = select(Branch).where(Branch.project_id == project_id)
    if search:
        query = query.where(Branch.name.ilike(f"%{search}%"))
    branches = db.scalars(query.order_by(Branch.name)).all()
    return [_branch_out(db, b, project.default_branch) for b in branches]


@router.post("/{project_id}/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
def create_branch(
    project_id: int,
    payload: BranchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new branch from an existing branch (copies HEAD like git)."""
    project = _get_project(db, project_id, user)
    existing = db.scalar(
        select(Branch).where(Branch.project_id == project_id, Branch.name == payload.name)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Branch already exists")

    source_name = payload.from_branch or project.default_branch
    source = db.scalar(
        select(Branch).where(Branch.project_id == project_id, Branch.name == source_name)
    )
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Source branch '{source_name}' not found")

    branch = Branch(
        project_id=project_id,
        name=payload.name,
        head_commit_id=source.head_commit_id,  # ← copy HEAD from source
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return _branch_out(db, branch, project.default_branch)


@router.delete("/{project_id}/branches/{branch_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(
    project_id: int,
    branch_name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a branch. Cannot delete the default branch."""
    project = _get_project(db, project_id, user)
    if branch_name == project.default_branch:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete the default branch")
    branch = _get_branch(db, project_id, branch_name)
    db.delete(branch)
    db.commit()


# ── Merge ────────────────────────────────────────────────────────────────────

@router.post("/{project_id}/merge", response_model=MergeOut, status_code=status.HTTP_201_CREATED)
def merge_branch(
    project_id: int,
    payload: MergeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Merge source branch into target branch.

    Strategies:
      - merge: create a merge commit (default)
      - squash: flatten all source commits into one on target
      - fast_forward: move target pointer to source HEAD (only if linear)
    """
    project = _get_project(db, project_id, user)
    source = _get_branch(db, project_id, payload.source_branch)
    target = _get_branch(db, project_id, payload.target_branch or project.default_branch)

    if source.name == target.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot merge a branch into itself")

    if source.head_commit_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Source branch has no commits")

    strategy = payload.strategy or "merge"

    # ── fast-forward ──
    if strategy == "fast_forward":
        # Check if source is ahead of target (linear)
        if target.head_commit_id is None:
            # target has no commits — just point it at source
            target.head_commit_id = source.head_commit_id
            project.updated_at = utcnow()
            db.commit()
            return MergeOut(
                strategy="fast_forward",
                source_branch=source.name,
                target_branch=target.name,
                merge_commit_id=None,
                files_changed=0,
            )

        # Walk from source to find if target HEAD is an ancestor
        current = source.head_commit_id
        found = False
        visited = set()
        while current is not None and current not in visited:
            if current == target.head_commit_id:
                found = True
                break
            visited.add(current)
            c = db.get(Commit, current)
            if c is None:
                break
            current = c.parent_id

        if not found:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Fast-forward not possible — target is not an ancestor of source. Use merge or squash.",
            )

        target.head_commit_id = source.head_commit_id
        project.updated_at = utcnow()
        db.commit()
        return MergeOut(
            strategy="fast_forward",
            source_branch=source.name,
            target_branch=target.name,
            merge_commit_id=None,
            files_changed=0,
        )

    # ── squash ──
    if strategy == "squash":
        # Collect all files from source branch, flatten into one commit
        source_tree = _collect_tree(db, source.head_commit_id)

        # Build squash message: list all commit messages
        msgs: list[str] = []
        current = source.head_commit_id
        visited = set()
        while current is not None and current not in visited:
            visited.add(current)
            c = db.get(Commit, current)
            if c is None:
                break
            if c.message:
                msgs.append(c.message)
            current = c.parent_id
        msgs.reverse()
        squash_msg = payload.message or f"Squash {len(msgs)} commit(s) from '{source.name}'"

        # Create one commit on target
        commit = Commit(
            project_id=project_id,
            author_id=user.id,
            parent_id=target.head_commit_id,
            message=squash_msg,
        )
        db.add(commit)
        db.flush()

        for path, snap in source_tree.items():
            db.add(FileSnapshot(
                commit_id=commit.id,
                path=path,
                blob_sha=snap.blob_sha,
                size=snap.size,
            ))

        target.head_commit_id = commit.id
        project.updated_at = utcnow()
        db.commit()
        db.refresh(commit)

        return MergeOut(
            strategy="squash",
            source_branch=source.name,
            target_branch=target.name,
            merge_commit_id=commit.id,
            files_changed=len(source_tree),
        )

    # ── merge commit (default) ──
    source_tree = _collect_tree(db, source.head_commit_id)
    target_tree = _collect_tree(db, target.head_commit_id)

    # Three-way: base is the common ancestor (target HEAD), merge source into target
    merged, conflicts = _merge_trees(target_tree, source_tree)

    if conflicts:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Merge conflicts in: {', '.join(conflicts[:10])}",
        )

    merge_msg = payload.message or f"Merge '{source.name}' into '{target.name}'"

    commit = Commit(
        project_id=project_id,
        author_id=user.id,
        parent_id=target.head_commit_id,
        message=merge_msg,
    )
    db.add(commit)
    db.flush()

    for path, snap in merged.items():
        db.add(FileSnapshot(
            commit_id=commit.id,
            path=path,
            blob_sha=snap.blob_sha,
            size=snap.size,
        ))

    target.head_commit_id = commit.id
    project.updated_at = utcnow()
    db.commit()
    db.refresh(commit)

    return MergeOut(
        strategy="merge",
        source_branch=source.name,
        target_branch=target.name,
        merge_commit_id=commit.id,
        files_changed=len(merged),
    )


# ── Compare ──────────────────────────────────────────────────────────────────

@router.get("/{project_id}/compare", response_model=CompareOut)
def compare_branches(
    project_id: int,
    base: str = Query(..., description="Base branch"),
    head: str = Query(..., description="Head branch"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compare two branches — returns ahead/behind counts and file diffs.

    Like GitHub: base...head
    """
    project = _get_project(db, project_id, user)
    base_branch = _get_branch(db, project_id, base)
    head_branch = _get_branch(db, project_id, head)

    base_tree = _collect_tree(db, base_branch.head_commit_id)
    head_tree = _collect_tree(db, head_branch.head_commit_id)

    all_paths = set(base_tree.keys()) | set(head_tree.keys())

    added: list[str] = []
    removed: list[str] = []
    modified: list[str] = []

    for path in sorted(all_paths):
        in_base = path in base_tree
        in_head = path in head_tree
        if not in_base and in_head:
            added.append(path)
        elif in_base and not in_head:
            removed.append(path)
        elif base_tree[path].blob_sha != head_tree[path].blob_sha:
            modified.append(path)

    # Count commits ahead/behind
    ahead = _count_ahead(db, base_branch.head_commit_id, head_branch.head_commit_id)
    behind = _count_ahead(db, head_branch.head_commit_id, base_branch.head_commit_id)

    total_commits = _commit_chain_length(db, head_branch.head_commit_id)

    return CompareOut(
        base_branch=base,
        head_branch=head,
        ahead=ahead,
        behind=behind,
        total_commits=total_commits,
        files_changed=len(added) + len(removed) + len(modified),
        added=added,
        removed=removed,
        modified=modified,
    )


def _count_ahead(db: Session, ancestor_id: int | None, descendant_id: int | None) -> int:
    """Count commits reachable from descendant but not from ancestor."""
    if descendant_id is None:
        return 0
    if ancestor_id is None:
        return _commit_chain_length(db, descendant_id)

    # Collect all ancestors of ancestor_id
    ancestor_set: set[int] = set()
    current = ancestor_id
    while current is not None:
        ancestor_set.add(current)
        c = db.get(Commit, current)
        if c is None:
            break
        current = c.parent_id

    # Walk descendant chain, count those not in ancestor set
    count = 0
    current = descendant_id
    visited: set[int] = set()
    while current is not None and current not in visited:
        if current not in ancestor_set:
            count += 1
        visited.add(current)
        c = db.get(Commit, current)
        if c is None:
            break
        current = c.parent_id
    return count


# ── Push (VST3 / CLI endpoint) ──────────────────────────────────────────────

@router.post("/{project_id}/push", response_model=PushOut)
def push_branch(
    project_id: int,
    message: str = Form("snd push"),
    branch: str = Form("main"),
    manifest: str = Form(""),
    round: int = Form(0),
    files: list[UploadFile] = File([]),
    audio: UploadFile | None = File(None),
    stems: list[UploadFile] = File([]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """VST3 / CLI push endpoint — upload files, create commit on branch.

    Accepts multipart/form-data with:
      - files: DAW project files (.als, .rpp, .cpr, .flp, etc.)
      - branch: target branch (default: "main")
      - message: commit message
      - manifest: JSON manifest from snd push (DAW metadata)
      - audio: optional master audio for review
      - stems: optional stem audio files for review
      - round: optional review round number

    Returns:
      - commit_id, file_count, uploaded stats, deduplicated count
      - review_url + version_id if audio was uploaded
    """
    project = _get_project(db, project_id, user)

    # ── Resolve or create branch ──
    branch_obj = db.scalar(
        select(Branch).where(Branch.project_id == project_id, Branch.name == branch)
    )
    if branch_obj is None:
        branch_obj = Branch(
            project_id=project_id,
            name=branch,
            head_commit_id=project.default_branch != branch and (
                db.scalar(select(Branch).where(
                    Branch.project_id == project_id,
                    Branch.name == project.default_branch,
                )) or Branch(project_id=project_id, name=project.default_branch)
            ).head_commit_id,
        )
        db.add(branch_obj)
        db.flush()

    # ── Upload files and create commit ──
    has_alsa = False
    has_master = False
    stem_count = 0
    dedup_count = 0
    file_snapshots: list[tuple[str, str, int]] = []  # (path, blob_sha, size)
    review_url: str | None = None
    version_id: int | None = None
    session: object | None = None
    session_id: int | None = None
    manifest_stored: bool = False

    total_upload_size = 0
    for upload in files:
        data = upload.file.read()
        total_upload_size += len(data)
        if total_upload_size > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        blob_sha = storage.put_blob(data)

        # Check if blob already exists (dedup)
        existing = db.scalar(
            select(FileSnapshot).where(FileSnapshot.blob_sha == blob_sha).limit(1)
        )
        if existing:
            dedup_count += 1

        filename = (upload.filename or "file").replace("\\", "/")
        # Prevent path traversal attacks
        if ".." in filename or filename.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid filename")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in DAW_EXTENSIONS:
            if ext == "als":
                has_alsa = True
        # Note: We don't track other file types in the uploaded dict for the API response

        # Create StorageObject record for asset lifecycle tracking
        # (content-addressed: same file always maps to the same row)
        existing_obj = db.scalar(
            select(StorageObject).where(StorageObject.sha256 == blob_sha).limit(1)
        )
        if existing_obj is None:
            so = StorageObject(
                sha256=blob_sha,
                storage_provider="local",
                storage_key=f"blobs/sha256/{blob_sha[:2]}/{blob_sha[2:4]}/{blob_sha}",
                original_filename=filename,
                content_type=upload.content_type or "application/octet-stream",
                byte_size=len(data),
                kind="daw_project" if ext in DAW_EXTENSIONS else "artifact",
                status="uploaded",
                uploaded_by_id=user.id,
                project_id=project_id,
            )
            db.add(so)
            db.flush()
        else:
            # Update project_id if not set
            if existing_obj.project_id is None:
                existing_obj.project_id = project_id
                db.flush()

        # Emit storage.object.uploaded webhook event
        try:
            dispatch_event(
                "storage.object.uploaded",
                {
                    "sha256": blob_sha,
                    "filename": filename,
                    "size": len(data),
                    "project_id": project_id,
                },
                user.id,
            )
        except Exception:
            pass  # Best-effort webhook delivery

        file_snapshots.append((filename, blob_sha, len(data)))

    # ── Validate audio extension before processing ──
    AUDIO_EXTENSIONS = {"wav", "mp3", "flac", "aiff", "aif", "ogg", "m4a", "aac"}
    if audio is not None:
        audio_ext = (audio.filename or "master.wav").rsplit(".", 1)[-1].lower()
        if audio_ext not in AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio extension '.{audio_ext}' for master. Supported: {', '.join(sorted(AUDIO_EXTENSIONS))}",
            )
    # Stems require a master
    if stems and not audio:
        raise HTTPException(status_code=400, detail="Stems require --audio (master)")
    # Validate stem extensions
    for stem in stems:
        stem_ext = (stem.filename or "stem.wav").rsplit(".", 1)[-1].lower()
        if stem_ext not in AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported stem extension '.{stem_ext}'. Supported: {', '.join(sorted(AUDIO_EXTENSIONS))}",
            )

    # ── Process manifest if provided ──
    if manifest:
        try:
            # Validate that manifest is valid JSON
            json.loads(manifest)
            manifest_data = manifest.encode('utf-8')
            manifest_sha = storage.put_blob(manifest_data)
            file_snapshots.append(("SOUNDHUB-MANIFEST.json", manifest_sha, len(manifest_data)))
            manifest_stored = True
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid manifest JSON")
        except Exception as e:
            # If manifest processing fails, reject the request
            raise HTTPException(status_code=400, detail="Invalid manifest")

    # ── Create commit ──
    commit = Commit(
        project_id=project_id,
        author_id=user.id,
        parent_id=branch_obj.head_commit_id,
        message=message,
    )
    db.add(commit)
    db.flush()

    for path, blob_sha, size in file_snapshots:
        db.add(FileSnapshot(
            commit_id=commit.id,
            path=path,
            blob_sha=blob_sha,
            size=size,
        ))

    branch_obj.head_commit_id = commit.id
    project.updated_at = utcnow()

    # ── Auto-trigger CI checks for audio files in regular uploads ──
    audio_file_snapshots = [
        (path, blob_sha, size) for path, blob_sha, size in file_snapshots
        if any(path.lower().endswith(ext) for ext in {'.wav', '.mp3', '.flac', '.aiff', '.ogg', '.m4a', '.aac'})
    ]

    for path, blob_sha, size in audio_file_snapshots:
        try:
            audio_data = storage.read_blob(blob_sha)
            loudness_data = loudness.analyse(audio_data)

            # LUFS check
            integrated_lufs = loudness_data.get('integrated_lufs')
            if integrated_lufs is not None:
                lufs_check = AudioCheck(
                    commit_id=commit.id,
                    check_type="lufs",
                    value=str(integrated_lufs),
                    expected="-16 to -12 LUFS (optimal for streaming)"
                )
                if -16 <= integrated_lufs <= -12:
                    lufs_check.status = "pass"
                    lufs_check.message = f"LUFS {integrated_lufs:.1f} is within target range (-16 to -12)"
                elif -18 <= integrated_lufs <= -10:
                    lufs_check.status = "warn"
                    lufs_check.message = f"LUFS {integrated_lufs:.1f} is outside optimal range but acceptable"
                else:
                    lufs_check.status = "fail"
                    lufs_check.message = f"LUFS {integrated_lufs:.1f} is too {'quiet' if integrated_lufs < -18 else 'loud'}"
                db.add(lufs_check)

            # True Peak check
            true_peak_dbtp = loudness_data.get('true_peak_dbtp')
            if true_peak_dbtp is not None:
                tp_check = AudioCheck(
                    commit_id=commit.id,
                    check_type="true_peak",
                    value=str(true_peak_dbtp),
                    expected="< -1.0 dBTP (safe), < 0.0 dBTP (warning)"
                )
                if true_peak_dbtp < -1.0:
                    tp_check.status = "pass"
                    tp_check.message = f"True Peak {true_peak_dbtp:.2f} dBTP is safe"
                elif true_peak_dbtp < 0.0:
                    tp_check.status = "warn"
                    tp_check.message = f"True Peak {true_peak_dbtp:.2f} dBTP is close to clipping"
                else:
                    tp_check.status = "fail"
                    tp_check.message = f"True Peak {true_peak_dbtp:.2f} dBTP — clipping detected!"
                db.add(tp_check)

            # Format check
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            format_check = AudioCheck(
                commit_id=commit.id,
                check_type="format",
                value=ext,
                expected="wav/flac/aiff/mp3/ogg/m4a/aac"
            )
            if ext in {"wav", "flac", "aiff", "mp3", "ogg", "m4a", "aac"}:
                format_check.status = "pass"
                format_check.message = f"Format '{ext}' is supported"
            else:
                format_check.status = "fail"
                format_check.message = f"Format '{ext}' is not supported"
            db.add(format_check)

            # Sample rate check
            sample_rate = loudness_data.get('sample_rate')
            if sample_rate is not None:
                sr_check = AudioCheck(
                    commit_id=commit.id,
                    check_type="sample_rate",
                    value=str(sample_rate),
                    expected="≥ 44100 Hz"
                )
                if sample_rate >= 44100:
                    sr_check.status = "pass"
                    sr_check.message = f"Sample rate {sample_rate} Hz is OK"
                else:
                    sr_check.status = "fail"
                    sr_check.message = f"Sample rate {sample_rate} Hz is below minimum 44100 Hz"
                db.add(sr_check)

            # Channels check
            channels = loudness_data.get('channels')
            if channels is not None:
                ch_check = AudioCheck(
                    commit_id=commit.id,
                    check_type="channels",
                    value=str(channels),
                    expected="1 or 2 channels (mono/stereo)"
                )
                if channels in (1, 2):
                    ch_check.status = "pass"
                    ch_check.message = f"{channels} channel(s) — mono/stereo"
                else:
                    ch_check.status = "warn"
                    ch_check.message = f"{channels} channel(s) — unusual channel count"
                db.add(ch_check)

        except Exception as e:
            # If audio analysis fails, create a failed check
            error_check = AudioCheck(
                commit_id=commit.id,
                check_type="lufs",
                value="",
                expected="Analysis failed"
            )
            error_check.status = "fail"
            error_check.message = f"Audio analysis failed: {str(e)}"
            db.add(error_check)

    # ── Review session (if audio provided) ──
    if audio is not None:
        from ..models import ReviewSession, ReviewVersion
        import secrets as _secrets

        audio_data = audio.file.read()
        audio_sha = storage.put_blob(audio_data)
        audio_ext = (audio.filename or "audio.wav").rsplit(".", 1)[-1].lower()

        # Check audio blob dedup (check both FileSnapshot and ReviewVersion)
        existing_audio = db.scalar(
            select(FileSnapshot).where(FileSnapshot.blob_sha == audio_sha).limit(1)
        )
        if not existing_audio:
            from ..models import ReviewVersion as _RV
            existing_audio = db.scalar(
                select(_RV).where(_RV.blob_sha == audio_sha).limit(1)
            )
        if existing_audio:
            dedup_count += 1

        session = None
        if audio is not None:
            # Look for an existing session in_review for this project and owner
            existing_session = db.scalar(
                select(ReviewSession)
                .where(
                    ReviewSession.project_id == project_id,
                    ReviewSession.owner_id == user.id,
                    ReviewSession.status == "in_review",
                )
                .order_by(ReviewSession.id.desc())  # get the most recent
                .limit(1)
            )
            if existing_session is not None:
                session = existing_session
            else:
                session = ReviewSession(
                    owner_id=user.id,
                    project_id=project_id,
                    name=message[:160] or f"Push from {branch}",
                    share_token=_secrets.token_urlsafe(16),
                    share_permission="download",
                )
                db.add(session)
                db.flush()

        # Determine the next version number for this session
        max_number = db.scalar(
            select(func.max(ReviewVersion.number))
            .where(ReviewVersion.session_id == session.id)
        )
        next_number = (max_number or 0) + 1

        rv = ReviewVersion(
            session_id=session.id,
            number=next_number,
            label=f"v{next_number}",
            message=message,
            filename=audio.filename or f"master.{audio_ext}",
            blob_sha=audio_sha,
            size=len(audio_data),
            audio_format=audio_ext,
            round_number=round or 1,
            commit_id=commit.id,
        )
        db.add(rv)
        db.flush()

        version_id = rv.id
        review_url = f"/r/{session.share_token}"
        session_id = session.id
        has_master = True

        # Audio CI checks for the dedicated audio upload
        try:
            loudness_data = loudness.analyse(audio_data)

            # LUFS check
            integrated_lufs = loudness_data.get('integrated_lufs')
            if integrated_lufs is not None:
                lufs_check = AudioCheck(
                    commit_id=commit.id,
                    check_type="lufs",
                    value=str(integrated_lufs),
                    expected="-16 to -12 LUFS (optimal for streaming)"
                )
                if -16 <= integrated_lufs <= -12:
                    lufs_check.status = "pass"
                    lufs_check.message = f"LUFS {integrated_lufs:.1f} is within target range (-16 to -12)"
                elif -18 <= integrated_lufs <= -10:
                    lufs_check.status = "warn"
                    lufs_check.message = f"LUFS {integrated_lufs:.1f} is outside optimal range but acceptable"
                else:
                    lufs_check.status = "fail"
                    lufs_check.message = f"LUFS {integrated_lufs:.1f} is too {'quiet' if integrated_lufs < -18 else 'loud'}"
                db.add(lufs_check)

            # True Peak check
            true_peak_dbtp = loudness_data.get('true_peak_dbtp')
            if true_peak_dbtp is not None:
                tp_check = AudioCheck(
                    commit_id=commit.id,
                    check_type="true_peak",
                    value=str(true_peak_dbtp),
                    expected="< -1.0 dBTP (safe), < 0.0 dBTP (warning)"
                )
                if true_peak_dbtp < -1.0:
                    tp_check.status = "pass"
                    tp_check.message = f"True Peak {true_peak_dbtp:.2f} dBTP is safe"
                elif true_peak_dbtp < 0.0:
                    tp_check.status = "warn"
                    tp_check.message = f"True Peak {true_peak_dbtp:.2f} dBTP is close to clipping"
                else:
                    tp_check.status = "fail"
                    tp_check.message = f"True Peak {true_peak_dbtp:.2f} dBTP — clipping detected!"
                db.add(tp_check)

            # Format check
            ext = audio_ext
            format_check = AudioCheck(
                commit_id=commit.id,
                check_type="format",
                value=ext,
                expected="wav/flac/aiff/mp3/ogg/m4a/aac"
            )
            if ext in {"wav", "flac", "aiff", "mp3", "ogg", "m4a", "aac"}:
                format_check.status = "pass"
                format_check.message = f"Format '{ext}' is supported"
            else:
                format_check.status = "fail"
                format_check.message = f"Format '{ext}' is not supported"
            db.add(format_check)

            # Sample rate check
            sample_rate = loudness_data.get('sample_rate')
            if sample_rate is not None:
                sr_check = AudioCheck(
                    commit_id=commit.id,
                    check_type="sample_rate",
                    value=str(sample_rate),
                    expected="≥ 44100 Hz"
                )
                if sample_rate >= 44100:
                    sr_check.status = "pass"
                    sr_check.message = f"Sample rate {sample_rate} Hz is OK"
                else:
                    sr_check.status = "fail"
                    sr_check.message = f"Sample rate {sample_rate} Hz is below minimum 44100 Hz"
                db.add(sr_check)

            # Channels check
            channels = loudness_data.get('channels')
            if channels is not None:
                ch_check = AudioCheck(
                    commit_id=commit.id,
                    check_type="channels",
                    value=str(channels),
                    expected="1 or 2 channels (mono/stereo)"
                )
                if channels in (1, 2):
                    ch_check.status = "pass"
                    ch_check.message = f"{channels} channel(s) — mono/stereo"
                else:
                    ch_check.status = "warn"
                    ch_check.message = f"{channels} channel(s) — unusual channel count"
                db.add(ch_check)

        except Exception as e:
            # If audio analysis fails, create a failed check
            error_check = AudioCheck(
                commit_id=commit.id,
                check_type="lufs",
                value="",
                expected="Analysis failed"
            )
            error_check.status = "fail"
            error_check.message = f"Audio analysis failed: {str(e)}"
            db.add(error_check)

        # Mapping from common stem filename prefixes to standardized logical names
        stem_name_mapping = {
            # Drum variations
            "kick": "drums",
            "kick in": "drums",
            "kick out": "drums",
            "snare": "drums",
            "snare top": "drums",
            "snare bottom": "drums",
            "tom": "drums",
            "tom 1": "drums",
            "tom 2": "drums",
            "floor tom": "drums",
            "hi hat": "drums",
            "hihat": "drums",
            "hat": "drums",
            "ride": "drums",
            "crash": "drums",
            "cymbal": "drums",
            "drum": "drums",
            "drums": "drums",
            "percussion": "drums",
            "perc": "drums",

            # Bass variations
            "bass": "bass",
            "bass guitar": "bass",
            "electric bass": "bass",
            "acoustic bass": "bass",
            "sub bass": "bass",
            "subbass": "bass",

            # Vocal variations
            "vocal": "vocal",
            "vocals": "vocal",
            "vox": "vocal",
            "voice": "vocal",
            "singing": "vocal",
            "singer": "vocal",
            "lead vocal": "vocal",
            "backing vocal": "vocal",
            "harmony": "vocal",

            # Guitar variations
            "guitar": "guitar",
            "rhythm guitar": "guitar",
            "lead guitar": "guitar",
            "acoustic guitar": "guitar",
            "electric guitar": "guitar",
            "gtr": "guitar",

            # Keyboard variations
            "keys": "keys",
            "keyboard": "keys",
            "piano": "keys",
            "synth": "keys",
            "synthesizer": "keys",
            "organ": "keys",

            # Other common stems
            "strings": "strings",
            "horns": "horns",
            "brass": "horns",
            "sax": "horns",
            "saxophone": "horns",
        }

        # Upload stems
        stem_count = 0
        for stem_upload in stems:
            stem_data = stem_upload.file.read()
            stem_sha = storage.put_blob(stem_data)
            from ..models import StemAsset

            # Extract filename without extension and convert to lowercase for mapping
            filename_stem = (stem_upload.filename or "stem").rsplit(".", 1)[0].lower().strip()

            # Try to map to a standardized logical name, fallback to original stem
            logical_name = stem_name_mapping.get(filename_stem, filename_stem)

            db.add(StemAsset(
                version_id=rv.id,
                logical_name=logical_name,
                display_name=stem_upload.filename or "stem",
                blob_sha=stem_sha,
                size=len(stem_data),
                audio_format=(stem_upload.filename or "stem.wav").rsplit(".", 1)[-1].lower(),
            ))
            stem_count += 1

    db.commit()

    # ── Enqueue background jobs for uploaded assets ──
    # The sync CI checks above run inline for fast feedback.
    # These async jobs do heavier processing that should not block the push response.
    for path, blob_sha, size in file_snapshots:
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        try:
            if ext in DAW_EXTENSIONS:
                # DAW project → parse structure, tracks, plugins, BPM
                # We need a StorageObject for the job to reference
                so = db.scalar(
                    select(StorageObject).where(StorageObject.sha256 == blob_sha).limit(1)
                )
                if so:
                    job_queue.enqueue_job(
                        "parse_daw",
                        storage_object_id=so.id,
                        project_id=project_id,
                        commit_id=commit.id,
                        input_json={"sha256": blob_sha, "filename": path},
                        created_by_id=user.id,
                    )
            elif ext in {"wav", "mp3", "flac", "aiff", "aif", "ogg", "m4a", "aac"}:
                # Audio file → waveform, metadata extraction, loudness analysis
                job_queue.enqueue_job(
                    "generate_waveform",
                    project_id=project_id,
                    commit_id=commit.id,
                    input_json={"sha256": blob_sha, "filename": path},
                    created_by_id=user.id,
                )
                job_queue.enqueue_job(
                    "extract_audio_metadata",
                    project_id=project_id,
                    commit_id=commit.id,
                    input_json={"sha256": blob_sha, "filename": path},
                    created_by_id=user.id,
                )
                job_queue.enqueue_job(
                    "analyze_loudness",
                    project_id=project_id,
                    commit_id=commit.id,
                    input_json={"sha256": blob_sha, "filename": path},
                    created_by_id=user.id,
                )
        except Exception as e:
            # Job enqueueing is best-effort — never block the push response
            logger.warning("Failed to enqueue job for %s: %s", path, e)

    # Build the uploaded dict for the API response
    uploaded = {
        "als": has_alsa,
        "master": has_master,
        "stems": stem_count
    }

    return PushOut(
        ok=True,
        project_id=project_id,
        branch=branch,
        commit_id=commit.id,
        file_count=len(file_snapshots),
        uploaded=uploaded,
        deduplicated=dedup_count,
        review_url=review_url,
        version_id=version_id,
        session_id=session_id,
        share_token=session.share_token if session else None,
        message=message,
        manifest_stored=manifest_stored,
    )


# ── Commits ──────────────────────────────────────────────────────────────────

@router.post("/{project_id}/commits", response_model=CommitOut, status_code=status.HTTP_201_CREATED)
def create_commit(
    project_id: int,
    message: str = Form(""),
    branch_name: str = Form("main", alias="branch"),
    files: list[UploadFile] = File([]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_project(db, project_id, user)
    branch = _get_branch(db, project_id, branch_name)

    commit = Commit(
        project_id=project_id,
        author_id=user.id,
        parent_id=branch.head_commit_id,
        message=message,
    )
    db.add(commit)
    db.flush()

    file_count = 0
    for upload in files:
        data = upload.file.read()
        blob_sha = storage.put_blob(data)
        filename = (upload.filename or "file").replace("\\", "/")
        snap = FileSnapshot(commit_id=commit.id, path=filename, blob_sha=blob_sha, size=len(data))
        db.add(snap)
        file_count += 1

    branch.head_commit_id = commit.id
    project.updated_at = utcnow()
    db.commit()
    db.refresh(commit)
    return CommitOut.model_validate(commit, from_attributes=True)


@router.get("/{project_id}/commits", response_model=list[CommitOut])
def list_commits(
    project_id: int,
    branch: str = Query("main"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List commits on a branch (newest first)."""
    _get_project(db, project_id, user)
    br = _get_branch(db, project_id, branch)
    commits: list[Commit] = []
    current = br.head_commit_id
    visited: set[int] = set()
    while current is not None and current not in visited and len(commits) < limit:
        c = db.get(Commit, current)
        if c is None:
            break
        commits.append(c)
        visited.add(current)
        current = c.parent_id
    return [CommitOut.model_validate(c, from_attributes=True) for c in commits]


@router.get("/{project_id}/commits/{commit_id}", response_model=CommitOut)
def get_commit(
    project_id: int,
    commit_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project(db, project_id, user)
    commit = db.get(Commit, commit_id)
    if commit is None or commit.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commit not found")
    return CommitOut.model_validate(commit, from_attributes=True)


# ── Tree ─────────────────────────────────────────────────────────────────────

def _detect_daw(path: str) -> tuple[str | None, str]:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext in DAW_EXTENSIONS:
        return ext, DAW_MAP.get(ext, ext.upper())
    return None, ""


@router.get("/{project_id}/tree", response_model=TreeOut)
def get_tree(
    project_id: int,
    commit_id: int | None = Query(None),
    branch: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the file tree for a commit or branch HEAD."""
    project = _get_project(db, project_id, user)

    if commit_id is not None:
        commit = db.get(Commit, commit_id)
        if commit is None or commit.project_id != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Commit not found")
    else:
        branch_name = branch or project.default_branch
        br = _get_branch(db, project_id, branch_name)
        if br.head_commit_id is None:
            return TreeOut(commit_id=None, commit_message="", files=[])
        commit = db.get(Commit, br.head_commit_id)
        if commit is None:
            return TreeOut(commit_id=None, commit_message="", files=[])

    # Collect tree by walking parent chain
    tree = _collect_tree(db, commit.id)
    files = []
    for path, snap in sorted(tree.items()):
        daw_ext, daw_name = _detect_daw(path)
        daw_info = None
        if daw_ext and snap.size < 500_000:
            try:
                data = storage.read_blob(snap.blob_sha)
                daw_info = _parse_daw(daw_ext, data)
            except Exception:
                pass
        # Convert dataclass to dict for Pydantic
        daw_dict = None
        if daw_info is not None:
            if hasattr(daw_info, '__dataclass_fields__'):
                daw_dict = {
                    'format': daw_info.format,
                    'format_key': daw_info.format_key,
                    'version': daw_info.version,
                    'bpm': daw_info.bpm,
                    'time_signature': daw_info.time_signature,
                    'tracks': [{'name': t.name, 'kind': t.kind, 'devices': t.devices} for t in daw_info.tracks],
                    'plugins': daw_info.plugins,
                    'samples': daw_info.samples,
                    'extra': daw_info.extra,
                }
            else:
                daw_dict = daw_info
        files.append(ProjectFileOut(
            path=path,
            size=snap.size,
            blob_sha=snap.blob_sha,
            kind=daw_name,
            daw_format=daw_ext,
            daw_info=daw_dict,
        ))
    return TreeOut(
        commit_id=commit.id,
        commit_message=commit.message or "",
        files=files,
    )


# ── Files (download) ─────────────────────────────────────────────────────────

@router.get("/{project_id}/files/{file_path:path}")
def download_file(
    project_id: int,
    file_path: str,
    download: bool = Query(False),
    branch: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a file from the latest commit on a branch."""
    project = _get_project(db, project_id, user)
    branch_name = branch or project.default_branch
    br = _get_branch(db, project_id, branch_name)
    if br.head_commit_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No commits on this branch")

    tree = _collect_tree(db, br.head_commit_id)
    if file_path not in tree:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

    snap = tree[file_path]
    data = storage.read_blob(snap.blob_sha)
    filename = file_path.rsplit("/", 1)[-1]
    disposition = f"{'attachment' if download else 'inline'}; filename=\"{filename}\""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime = {
        "wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac",
        "als": "application/octet-stream", "cpr": "application/octet-stream",
        "rpp": "application/octet-stream", "flp": "application/octet-stream",
    }.get(ext, "application/octet-stream")
    return Response(content=data, media_type=mime, headers={"Content-Disposition": disposition})


# ── Diff ─────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/diff", response_model=DiffOut)
def get_diff(
    project_id: int,
    path: str = Query(...),
    from_commit: int | None = Query(None),
    to_commit: int | None = Query(None),
    from_branch: str | None = Query(None),
    to_branch: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get diff for a file between two commits or branches."""
    project = _get_project(db, project_id, user)

    # Resolve commits
    if from_commit:
        c_from = db.get(Commit, from_commit)
    elif from_branch:
        br = _get_branch(db, project_id, from_branch)
        c_from = db.get(Commit, br.head_commit_id) if br.head_commit_id else None
    else:
        # default: parent of to_commit, or first commit
        if to_commit:
            c_to_temp = db.get(Commit, to_commit)
            c_from = db.get(Commit, c_to_temp.parent_id) if c_to_temp and c_to_temp.parent_id else None
        else:
            c_from = None

    if to_commit:
        c_to = db.get(Commit, to_commit)
    elif to_branch:
        br = _get_branch(db, project_id, to_branch)
        c_to = db.get(Commit, br.head_commit_id) if br.head_commit_id else None
    else:
        # default: latest commit on default branch
        br = _get_branch(db, project_id, project.default_branch)
        c_to = db.get(Commit, br.head_commit_id) if br.head_commit_id else None

    if c_to is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target commit not found")

    # Find file in each commit
    snap_from = versioning.file_in_commit(db, c_from, path) if c_from else None
    snap_to = versioning.file_in_commit(db, c_to, path)

    if snap_to is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"File '{path}' not found in target commit")

    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""

    # If both exist and same SHA — no diff
    if snap_from and snap_from.blob_sha == snap_to.blob_sha:
        return DiffOut(path=path, format=ext, summary=[], raw="", binary=False, truncated=False)

    # Try DAW-specific diff
    if ext in DAW_EXTENSIONS:
        try:
            from ..services.daw import diff_engine
            data_a = storage.read_blob(snap_from.blob_sha) if snap_from else None
            data_b = storage.read_blob(snap_to.blob_sha)
            info_a = _parse_daw(ext, data_a) if data_a else None
            info_b = _parse_daw(ext, data_b) if data_b else None
            summary_raw = diff_engine.summary_diff(info_a, info_b)
            summary = []
            if isinstance(summary_raw, dict):
                for kind, detail in summary_raw.items():
                    if isinstance(detail, dict):
                        before = detail.get('before', '—')
                        after = detail.get('after', '—')
                        summary.append(DiffChangeOut(kind=kind, label=f"{before} → {after}", old=str(before), new=str(after)))
                    elif isinstance(detail, list):
                        for item in detail:
                            summary.append(DiffChangeOut(kind=kind, label=str(item)))
                    elif isinstance(detail, dict) and 'added' in detail:
                        for item in detail.get('added', []):
                            summary.append(DiffChangeOut(kind=kind, label=f"+ {item}"))
                        for item in detail.get('removed', []):
                            summary.append(DiffChangeOut(kind=kind, label=f"- {item}"))
            raw_data = diff_engine.unified_diff(
                str(info_a) if info_a else "",
                str(info_b) if info_b else "",
            )
            raw = raw_data[0] if isinstance(raw_data, tuple) else str(raw_data)
            return DiffOut(path=path, format=ext, summary=summary, raw=raw, binary=False, truncated=False)
        except Exception:
            pass

    # Fallback: binary diff
    return DiffOut(path=path, format=ext, summary=[], raw="", binary=True, truncated=False)


def _dawinfo_to_dict(info) -> dict | None:
    """Convert DAWInfo dataclass to a plain dict for diff_engine."""
    if info is None:
        return None
    if isinstance(info, dict):
        return info
    if hasattr(info, '__dataclass_fields__'):
        return {
            'format': info.format,
            'format_key': info.format_key,
            'version': info.version,
            'bpm': info.bpm,
            'time_signature': info.time_signature,
            'tracks': [t.name for t in info.tracks],
            'plugins': info.plugins,
            'samples': info.samples,
            'extra': info.extra,
        }
    return None


def _parse_daw(ext: str, data: bytes) -> dict | None:
    """Parse DAW file and return DawInfo as dict."""
    try:
        if ext == "als":
            from ..services.daw.als_parser import parse_als
            return _dawinfo_to_dict(parse_als(data))
        elif ext == "rpp":
            from ..services.daw import registry
            return _dawinfo_to_dict(registry.parse_file(ext, data))
        elif ext == "cpr":
            from ..services.daw import registry
            return _dawinfo_to_dict(registry.parse_file(ext, data))
        elif ext == "flp":
            from ..services.daw import registry
            return _dawinfo_to_dict(registry.parse_file(ext, data))
    except Exception:
        return None
    return None
