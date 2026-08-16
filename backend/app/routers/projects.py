import hashlib
import json
import secrets
import unicodedata
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import FRONTEND_URL, MAX_UPLOAD_SIZE
from ..database import get_db
from ..models import (
    Commit,
    FileSnapshot,
    Project,
    ReviewSession,
    ReviewVersion,
    StemAsset,
    User,
    utcnow,
)
from ..schemas import (
    BranchCreate,
    BranchOut,
    CommitDetailOut,
    CommitOut,
    FileOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    ReleaseIn,
    TreeOut,
)
from ..services import ledger, storage, versioning, waveform
from ..services.daw import is_daw_path
from ..services.daw.registry import get_daw_info
from ..security import get_current_user

ALLOWED_AUDIO = {"wav", "mp3", "flac", "ogg", "aif", "aiff", "m4a"}
ALLOWED_STEM_AUDIO = {"wav", "mp3", "flac", "aif", "aiff", "m4a", "ogg"}

router = APIRouter(prefix="/api/projects", tags=["projects"])

# simple in-memory cache: blob_sha -> daw dict
_daw_cache: dict[str, dict] = {}
DAW_ANALYZE_MAX = 200 * 1024 * 1024  # don't decompress huge files for listing


def get_project_or_404(db: Session, user: User, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


def sanitize_path(name: str) -> str:
    name = name.replace("\\", "/")
    parts = [p for p in name.split("/") if p not in ("", ".", "..")]
    return "/".join(parts) or "unnamed"


def slugify(name: str) -> str:
    norm = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in norm.lower())
    slug = "-".join(s for s in slug.split("-") if s)
    return slug[:80] or "project"


def unique_slug(db: Session, owner_id: int, name: str) -> str:
    base = slugify(name)
    slug = base
    n = 2
    while db.scalar(select(Project).where(Project.owner_id == owner_id, Project.slug == slug)):
        slug = f"{base}-{n}"
        n += 1
    return slug


def _commit_out(db: Session, commit: Commit) -> CommitOut:
    files = db.query(FileSnapshot).filter(FileSnapshot.commit_id == commit.id).all()
    return CommitOut(
        id=commit.id,
        message=commit.message,
        created_at=commit.created_at,
        parent_id=commit.parent_id,
        author=commit.author,
        file_count=len(files),
        total_size=sum(f.size for f in files),
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc())
    ).all()


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = Project(
        owner_id=user.id,
        name=payload.name.strip(),
        slug=unique_slug(db, user.id, payload.name),
        description=payload.description.strip(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_project_or_404(db, user, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    if payload.name is not None and payload.name.strip() != project.name:
        project.name = payload.name.strip()
        project.slug = unique_slug(db, user.id, project.name)
    if payload.description is not None:
        project.description = payload.description.strip()
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    db.delete(project)
    db.commit()


@router.get("/{project_id}/branches", response_model=list[BranchOut])
def list_branches(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    return versioning.list_branches(db, project)


@router.post("/{project_id}/branches", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
def create_branch(
    project_id: int,
    payload: BranchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        row = versioning.create_branch(db, project, payload.name.strip(), payload.from_branch)
    except LookupError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    head = db.get(Commit, row.head_commit_id) if row.head_commit_id else None
    return BranchOut(
        name=row.name,
        is_default=row.name == project.default_branch,
        head_commit_id=row.head_commit_id,
        head_message=head.message if head else "",
        head_sha=f"{head.id:08x}"[:7] if head else None,
        head_author=head.author.username if head and head.author else "",
        head_date=head.created_at if head else None,
        commit_count=len(versioning.iter_commits(db, project, row.name)),
        created_at=row.created_at,
    )


@router.delete("/{project_id}/branches/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(
    project_id: int,
    name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        deleted = versioning.delete_branch(db, project, name)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Branch not found")


@router.get("/{project_id}/tree", response_model=TreeOut)
def get_tree(
    project_id: int,
    commit_id: int | None = None,
    branch: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        commit = versioning.get_commit(db, project, commit_id, branch)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commit not found")
    snapshots = versioning.tree_files(db, commit)
    files: list[FileOut] = []
    for snap in sorted(snapshots, key=lambda s: s.path):
        ext = PurePosixPath(snap.path).suffix.lower()
        daw_format = ext.lstrip(".") if is_daw_path(snap.path) else None
        daw_info: dict | None = None
        if daw_format and snap.size <= DAW_ANALYZE_MAX:
            daw_info = _analyze_cached(snap)
        files.append(
            FileOut(
                path=snap.path,
                size=snap.size,
                blob_sha=snap.blob_sha,
                kind="file",
                daw_format=daw_format,
                daw_info=daw_info,
            )
        )
    return TreeOut(
        commit_id=commit.id, commit_message=commit.message, files=files
    )


def _analyze_cached(snap: FileSnapshot) -> dict | None:
    if snap.blob_sha in _daw_cache:
        return _daw_cache[snap.blob_sha]
    try:
        data = storage.read_blob(snap.blob_sha)
        info = get_daw_info(snap.path, data)
    except Exception:  # noqa: BLE001
        info = None
    result = info.to_dict() if info else None
    _daw_cache[snap.blob_sha] = result
    return result


@router.get("/{project_id}/commits", response_model=list[CommitOut])
def list_commits(
    project_id: int,
    branch: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    commits = versioning.iter_commits(db, project, branch)
    return [_commit_out(db, c) for c in commits]


@router.get("/{project_id}/commits/{commit_id}", response_model=CommitDetailOut)
def get_commit(
    project_id: int,
    commit_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    try:
        commit = versioning.get_commit(db, project, commit_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commit not found")
    snapshots = versioning.tree_files(db, commit)
    out = CommitDetailOut(
        id=commit.id,
        message=commit.message,
        created_at=commit.created_at,
        parent_id=commit.parent_id,
        author=commit.author,
        file_count=len(snapshots),
        total_size=sum(s.size for s in snapshots),
        files=[
            FileOut(
                path=s.path,
                size=s.size,
                blob_sha=s.blob_sha,
                kind="file",
                daw_format=PurePosixPath(s.path).suffix.lstrip(".") or None,
            )
            for s in sorted(snapshots, key=lambda x: x.path)
        ],
    )
    return out


def _guess_stem_name(filename: str) -> str:
    """Derive the canonical stem logical_name from a render filename.

    `Bass_v13.wav` and `Kick_short_03.wav` both map to the same logical name
    so stems compare across versions by role, not by filename.
    """
    lower = filename.lower()
    for keywords, name in (
        (("kick", "drum", "snare", "hat", "perc", "clap", "tom", "cymbal", "808"), "drums"),
        (("bass", "sub"), "bass"),
        (("vocal", "vox"), "vocal"),
        (("synth", "key", "pad", "pluck", "lead", "arp", "string", "piano"), "synths"),
    ):
        if any(k in lower for k in keywords):
            return name
    return "other"


def _next_version_number(db: Session, session_id: int) -> int:
    return (
        db.scalar(
            select(ReviewVersion.number)
            .where(ReviewVersion.session_id == session_id)
            .order_by(ReviewVersion.number.desc())
            .limit(1)
        )
        or 0
    ) + 1


def _read_audio(upload: UploadFile, allowed: set[str], kind: str) -> tuple[bytes, str, str]:
    """Validate + read an audio upload (master or stem). Returns (data, filename, ext)."""
    filename = PurePosixPath((upload.filename or f"{kind}.wav").replace("\\", "/")).name
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported {kind} audio format '{ext}'. Allowed: {', '.join(sorted(allowed))}",
        )
    data = upload.file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Empty {kind} audio file: {filename}")
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"{kind.capitalize()} file too large: {filename}")
    return data, filename, ext


def _put_dedup(data: bytes) -> tuple[str, int]:
    """Store a blob content-addressed; returns (sha, 1 if it was new else 0)."""
    sha = hashlib.sha256(data).hexdigest()
    if storage.blob_exists(sha):
        return sha, 0
    storage.put_blob(data)
    return sha, 1


@router.post("/{project_id}/push")
def push_project_files(
    project_id: int,
    message: str = Form(""),
    manifest: str = Form(""),
    branch: str = Form("main"),
    round: int = Form(0, alias="round"),
    files: list[UploadFile] = File(...),
    audio: UploadFile | None = File(default=None),
    stems: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Push a full project snapshot (DAW files + media) as one commit, and
    optionally open a review version (master audio + stems) for gapless A/B.

    Used by the `snd push` CLI. Atomic by construction: every blob is
    content-addressed and stored FIRST (repeated pushes dedup), then the
    commit + review session/version/stems are created in ONE transaction —
    a mid-upload error never leaves a user-visible half-pushed version.

    Returns a stable JSON contract for automation:
      {"ok", "project_id", "branch", "commit_id", "version_id", "session_id",
       "share_token", "review_url", "uploaded": {"als", "master", "stems"},
       "deduplicated"}
    """
    project = get_project_or_404(db, user, project_id)
    tree: dict[str, bytes] = {}
    for f in files:
        path = PurePosixPath((f.filename or "file").replace("\\", "/")).as_posix()
        if not path or path.startswith("/") or ".." in path.split("/"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsafe file path: {path!r}")
        data = f.file.read()
        if not data:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Empty file: {path}")
        if len(data) > MAX_UPLOAD_SIZE:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File too large: {path}")
        tree[path] = data
    if not tree:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No files to push")
    if manifest.strip():
        try:
            json.loads(manifest)
        except json.JSONDecodeError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"manifest is not valid JSON: {exc}")
        tree["SOUNDHUB-MANIFEST.json"] = manifest.encode()

    # optional review materials — validated BEFORE any blob is written
    audio_data: tuple[bytes, str, str] | None = None
    if audio is not None and (audio.filename or "").strip():
        audio_data = _read_audio(audio, ALLOWED_AUDIO, "master")
    stems_data: list[tuple[bytes, str, str]] = []
    for s in stems:
        if s.filename and s.filename.strip():
            stems_data.append(_read_audio(s, ALLOWED_STEM_AUDIO, "stem"))
    # review mode (--audio/--stems) requires at least one listenable audio file
    if (audio_data is not None or stems_data) and audio_data is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Review mode requires --audio (the master) — stems attach to the master version",
        )

    # blobs first — content-addressed, so identical re-pushes dedup
    deduplicated = 0
    for path, data in sorted(tree.items()):
        _, new = _put_dedup(data)
        deduplicated += 0 if new else 1
    if audio_data is not None:
        _, new = _put_dedup(audio_data[0])
        deduplicated += 0 if new else 1
    for sdata, _sfn, _sext in stems_data:
        _, new = _put_dedup(sdata)
        deduplicated += 0 if new else 1

    # one transaction: commit + session + version + stems
    commit = versioning.create_commit(
        db, project, user, message.strip() or "snd push", tree, branch, commit_transaction=False
    )
    session = None
    version = None
    if audio_data is not None:
        session = db.scalar(
            select(ReviewSession)
            .where(ReviewSession.project_id == project.id, ReviewSession.owner_id == user.id)
            .order_by(ReviewSession.created_at.desc())
            .limit(1)
        )
        if session is None:
            session = ReviewSession(
                owner_id=user.id,
                project_id=project.id,
                name=project.name,
                share_token=secrets.token_urlsafe(16),
                # the review link is the whole point of a push — guests must be
                # able to listen (gapless A/B) and download without a password
                share_permission="download",
            )
            db.add(session)
            db.flush()
        data, filename, ext = audio_data
        blob_sha = hashlib.sha256(data).hexdigest()
        wf = waveform.generate(blob_sha, data, filename, ext)
        number = _next_version_number(db, session.id)
        version = ReviewVersion(
            session_id=session.id,
            number=number,
            label=f"v{number}",
            message=message.strip() or "snd push",
            filename=filename,
            blob_sha=blob_sha,
            size=len(data),
            duration_s=wf["duration_s"],
            audio_format=ext,
            round_number=round or session.round_number,
        )
        db.add(version)
        db.flush()
        for sdata, sfilename, sext in stems_data:
            db.add(
                StemAsset(
                    version_id=version.id,
                    logical_name=_guess_stem_name(sfilename),
                    display_name=sfilename.rsplit(".", 1)[0][:128] or sfilename,
                    blob_sha=hashlib.sha256(sdata).hexdigest(),
                    size=len(sdata),
                    audio_format=sext,
                )
            )
        db.flush()  # assign stem ids before writing the ledger
        for stem in db.scalars(
            select(StemAsset).where(StemAsset.version_id == version.id).order_by(StemAsset.id)
        ).all():
            ledger.append(
                db,
                "stem.uploaded",
                session_id=session.id,
                actor=user.username,
                entity_type="stem",
                entity_id=stem.id,
                payload={"version": version.label, "logical_name": stem.logical_name, "filename": stem.display_name},
            )
        session.updated_at = utcnow()
        ledger.append(
            db,
            "version.created",
            session_id=session.id,
            actor=user.username,
            entity_type="version",
            entity_id=version.id,
            payload={
                "label": version.label,
                "round": version.round_number,
                "filename": version.filename,
                "stems": len(stems_data),
            },
        )
    project.updated_at = utcnow()
    db.commit()
    db.refresh(commit)
    return {
        "ok": True,
        "project_id": project.id,
        "branch": branch,
        "commit_id": commit.id,
        "message": commit.message,
        "file_count": len(tree),
        "total_size": sum(len(d) for d in tree.values()),
        "manifest_stored": bool(manifest.strip()),
        "version_id": version.id if version else None,
        "session_id": session.id if session else None,
        "share_token": session.share_token if session else None,
        "review_url": f"{FRONTEND_URL}/r/{session.share_token}" if session else None,
        "uploaded": {
            "als": any(is_daw_path(p) for p in tree),
            "master": audio_data is not None,
            "stems": len(stems_data),
        },
        "deduplicated": deduplicated,
    }


@router.post("/{project_id}/release", response_model=ProjectOut)
def bind_release(
    project_id: int,
    payload: ReleaseIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bind an on-chain SoundHubRelease NFT to this project."""
    project = get_project_or_404(db, user, project_id)
    project.release_token_id = payload.token_id
    project.release_contract = payload.contract_address
    project.release_name = payload.name
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}/release", response_model=ProjectOut)
def unbind_release(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    project.release_token_id = None
    project.release_contract = None
    project.release_name = None
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/commits", response_model=CommitOut, status_code=status.HTTP_201_CREATED)
def create_commit(
    project_id: int,
    message: str = Form(""),
    branch: str = Form("main"),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, user, project_id)
    tree: dict[str, bytes] = {}
    for f in files:
        path = sanitize_path(f.filename or "")
        try:
            data = storage.put_upload_file(f, MAX_UPLOAD_SIZE)
        except ValueError as exc:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))
        if path in tree:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Duplicate path: {path}")
        tree[path] = data
    commit = versioning.create_commit(db, project, user, message.strip(), tree, branch=branch.strip() or "main")
    return _commit_out(db, commit)
