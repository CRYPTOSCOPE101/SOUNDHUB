"""Release packages — final delivery after approval.

The review loop ends with an immutable release package: deliverables are
checked against SHA-256 checksums, locked to one approved version, and handed
off through a protected delivery link. This is the "one source of truth"
replacement for `final_final_2.wav`.
"""

import hashlib
import json
import secrets
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_SIZE
from ..database import get_db
from ..models import (
    Deliverable,
    DeliveryEvent,
    ReleasePackage,
    ReviewSession,
    ReviewVersion,
    User,
    utcnow,
)
from ..schemas import (
    ArchiveUpdate,
    CheckoutOut,
    DeliverableCreate,
    DeliverableOut,
    DeliveryInvoiceUpdate,
    DeliveryManifestOut,
    DeliveryPageOut,
    HandoffUpdate,
    PackageTemplateOut,
    PreflightOut,
    ReleaseLockIn,
    ReleasePackageCreate,
    ReleasePackageOut,
)
from ..security import get_current_user
from ..services import ledger, storage, stripe_pay, waveform

router = APIRouter(prefix="/api/release-packages", tags=["release packages"])

ALLOWED_FILES = {"wav", "mp3", "flac", "aif", "aiff", "m4a", "ogg", "png", "jpg", "jpeg", "pdf", "zip"}

AUDIO_TYPES = {"master", "instrumental", "acapella", "clean_edit", "stems"}

# Release-package templates: ready-made deliverable checklists so the engineer
# doesn't rebuild every package by hand. The template pins which deliverables
# are REQUIRED for the lock preflight (label/sync presets have real spec).
PACKAGE_TEMPLATES: dict[str, dict] = {
    "final_master": {
        "name": "Streaming master",
        "description": "Main master + instrumental + metadata",
        "deliverable_types": ["master", "instrumental"],
        "note": "Add artwork + ISRC/UPC metadata when the distributor requires it.",
    },
    "label_sync": {
        "name": "Label / sync delivery",
        "description": "Masters, alternates, stems, metadata, artwork, approval receipt",
        "deliverable_types": ["master", "instrumental", "acapella", "clean_edit", "stems", "artwork"],
        "note": "Label presets often require 3000×3000 artwork and named folders — check the preflight.",
    },
    "dj_promo": {
        "name": "DJ promo",
        "description": "WAV, extended mix, radio edit, instrumental",
        "deliverable_types": ["master", "clean_edit", "instrumental"],
        "note": "Add BPM + key in the session manifest for DJ pools.",
    },
    "stem_handoff": {
        "name": "Stem handoff",
        "description": "Stereo stems, tempo, key, README",
        "deliverable_types": ["stems"],
        "note": "Optional paid service — consolidate audio + session manifest recommended.",
    },
    "archive_handoff": {
        "name": "Archive handoff",
        "description": "DAW session, media, plugin manifest, frozen/rendered tracks",
        "deliverable_types": ["master", "other"],
        "note": "Paid, on request — never promises session restoration without a retention policy.",
    },
    "post_production": {
        "name": "Post-production",
        "description": "Full mix, DX/MX/FX stems, alternate mix, cue sheet",
        "deliverable_types": ["master", "stems", "clean_edit"],
        "note": "Cue sheet notes go in the session manifest.",
    },
}


def _event(db: Session, package: ReleasePackage, event: str, actor: str, detail: str = "") -> None:
    db.add(DeliveryEvent(package_id=package.id, event=event, actor=actor, detail=detail))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _riff_meta(data: bytes) -> dict:
    """sample_rate / bit_depth / channels from a WAV header."""
    import struct as _struct
    from io import BytesIO as _BytesIO

    sr = None
    bits = None
    ch = None
    if data[:4] == b"RIFF":
        buf = _BytesIO(data)
        buf.seek(12)
        while True:
            header = buf.read(8)
            if len(header) < 8:
                break
            cid, csize = _struct.unpack("<4sI", header)
            if cid == b"fmt ":
                chunk = buf.read(csize)
                if len(chunk) >= 16:
                    ch = _struct.unpack("<H", chunk[2:4])[0]
                    sr = _struct.unpack("<I", chunk[4:8])[0]
                    bits = _struct.unpack("<H", chunk[14:16])[0]
                break
            buf.seek(csize + (csize % 2), 1)
    return {
        "sample_rate": sr,
        "bit_depth": bits,
        "channels": ch,
        "integrated_lufs": None,  # loudness lives on the source version's analysis
        "true_peak": None,
    }


def _deliverable_out(d: Deliverable) -> DeliverableOut:
    return DeliverableOut(
        id=d.id,
        package_id=d.package_id,
        type=d.type,
        filename=d.filename,
        size=d.size,
        sha256=d.sha256,
        format=d.format,
        sample_rate=d.sample_rate,
        bit_depth=d.bit_depth,
        channels=d.channels,
        integrated_lufs=d.integrated_lufs,
        true_peak=d.true_peak,
        is_required=d.is_required,
        source_version_id=d.source_version_id,
        created_at=d.created_at,
    )


def _package_out(db: Session, p: ReleasePackage) -> ReleasePackageOut:
    delivs = db.scalars(
        select(Deliverable).where(Deliverable.package_id == p.id).order_by(Deliverable.id)
    ).all()
    events = db.scalars(
        select(DeliveryEvent).where(DeliveryEvent.package_id == p.id).order_by(DeliveryEvent.id)
    ).all()
    return ReleasePackageOut(
        id=p.id,
        session_id=p.session_id,
        approved_version_id=p.approved_version_id,
        name=p.name,
        status=p.status,
        invoice_status=p.invoice_status,
        amount_due_cents=p.amount_due_cents,
        currency=p.currency or "usd",
        immutable_at=p.immutable_at,
        manifest_hash=p.manifest_hash,
        delivery_token=p.delivery_token,
        created_at=p.created_at,
        locked_by=p.locked_by,
        template=p.template or "custom",
        plugin_manifest=p.plugin_manifest or "",
        session_manifest=p.session_manifest or {},
        consolidate_audio=p.consolidate_audio or False,
        archive_expires_at=p.archive_expires_at,
        archive_status=p.archive_status or "available_now",
        last_verified_opened_at=p.last_verified_opened_at,
        force_locked_reason=p.force_locked_reason or "",
        force_locked_by=p.force_locked_by or "",
        deliverables=[_deliverable_out(d) for d in delivs],
        events=[
            {"event": e.event, "actor": e.actor, "detail": e.detail, "created_at": e.created_at.isoformat()}
            for e in events
        ],
    )


def _run_preflight(db: Session, package: ReleasePackage) -> PreflightOut:
    """QC preflight before the lock: required deliverables, file integrity,
    duplicates, naming, lossy masters. Loudness is a warning, never a block —
    we show neutral measurements, not a quality verdict."""
    from ..models import AudioAnalysis

    delivs = db.scalars(
        select(Deliverable).where(Deliverable.package_id == package.id)
    ).all()
    checks: list[dict] = []
    tpl = PACKAGE_TEMPLATES.get(package.template or "custom")
    required = tpl["deliverable_types"] if tpl else [d.type for d in delivs if d.is_required]
    present = {d.type for d in delivs}
    for rt in required:
        if rt not in present:
            checks.append({"status": "block", "label": "Required deliverable missing", "detail": rt})
    if not delivs:
        checks.append({"status": "block", "label": "No deliverables", "detail": "Add at least one file before locking"})
    seen: set[str] = set()
    for d in delivs:
        if d.size == 0:
            checks.append({"status": "block", "label": "Empty file", "detail": d.filename})
        if d.type in AUDIO_TYPES and d.format in ("wav", "aif", "aiff"):
            data = storage.read_blob(d.blob_sha)
            magic_ok = data[:4] == b"RIFF" if d.format == "wav" else data[:4] == b"FORM"
            if not magic_ok:
                checks.append({"status": "block", "label": "Corrupt audio", "detail": f"{d.filename} is not a valid {d.format}"})
        if d.sha256 in seen:
            checks.append({"status": "block", "label": "Duplicate file", "detail": f"{d.filename} duplicates another deliverable"})
        seen.add(d.sha256)
        if " " in d.filename:
            checks.append({"status": "warn", "label": "Naming", "detail": f"{d.filename} contains spaces — most delivery presets expect snake_case"})
        if d.type == "master" and d.format in ("mp3", "ogg", "m4a"):
            checks.append({"status": "warn", "label": "Lossy master", "detail": f"{d.filename} is {d.format} — labels usually want WAV for the master"})
        if d.source_version_id:
            a = db.scalar(select(AudioAnalysis).where(AudioAnalysis.version_id == d.source_version_id))
            if a and a.integrated_lufs is not None and a.integrated_lufs > -7:
                checks.append({
                    "status": "warn",
                    "label": "Hot master",
                    "detail": f"{d.filename}: {a.integrated_lufs:.1f} LUFS integrated — loudness warning, not a block",
                })
    blocking = any(c["status"] == "block" for c in checks)
    return PreflightOut(
        passed=not blocking,
        blocking=blocking,
        checks=[{"status": c["status"], "label": c["label"], "detail": c["detail"]} for c in checks],
    )


def _require_owner(package: ReleasePackage, user: User) -> None:
    if package.session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")


# ---------- templates ----------


@router.get("/templates", response_model=list[PackageTemplateOut])
def list_package_templates():
    """Ready-made package presets for the release UI."""
    return [
        PackageTemplateOut(
            id=tid,
            name=meta["name"],
            description=meta["description"],
            deliverable_types=meta["deliverable_types"],
            note=meta["note"],
        )
        for tid, meta in PACKAGE_TEMPLATES.items()
    ]


# ---------- owner endpoints ----------


@router.get("", response_model=list[ReleasePackageOut])
def list_packages(
    session_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(ReleasePackage).join(ReviewSession)
    if session_id is not None:
        q = q.where(ReleasePackage.session_id == session_id)
    q = q.where(ReviewSession.owner_id == user.id).order_by(ReleasePackage.created_at.desc())
    return [_package_out(db, p) for p in db.scalars(q).all()]


@router.post("", response_model=ReleasePackageOut, status_code=status.HTTP_201_CREATED)
def create_package(
    payload: ReleasePackageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.get(ReviewSession, payload.session_id)
    if session is None or session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    version = db.get(ReviewVersion, payload.approved_version_id)
    if version is None or version.session_id != session.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    if version.status != "approved":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Version {version.label} is not approved — lock the approval before creating a release package",
        )
    template = payload.template or "custom"
    if template not in PACKAGE_TEMPLATES and template != "custom":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown package template '{template}'")
    tpl = PACKAGE_TEMPLATES.get(template)
    name = payload.name.strip() or (tpl["name"] if tpl else "Final delivery")
    package = ReleasePackage(
        session_id=session.id,
        approved_version_id=version.id,
        name=name,
        template=template,
    )
    db.add(package)
    db.flush()
    _event(db, package, "package.created", user.username, f"approved {version.label} · {template}")
    ledger.append(
        db,
        "package.created",
        session_id=session.id,
        package_id=package.id,
        actor=user.username,
        entity_type="package",
        entity_id=package.id,
        payload={"approved_version": version.label, "name": package.name, "template": template},
    )
    db.commit()
    return _package_out(db, package)


@router.post("/{package_id}/deliverables/upload", response_model=DeliverableOut, status_code=status.HTTP_201_CREATED)
def upload_deliverable(
    package_id: int,
    type: str = Form(...),
    is_required: bool = Form(True),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    if package.status != "draft":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Package is locked — deliverables are immutable")
    filename = PurePosixPath((file.filename or "file.wav").replace("\\", "/")).name
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_FILES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported file type '{ext}'")
    try:
        data = storage.put_upload_file(file, MAX_UPLOAD_SIZE)
    except ValueError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))
    blob_sha = storage.put_blob(data)
    meta = _riff_meta(data) if ext in ("wav", "aif", "aiff") else {
        "sample_rate": None, "bit_depth": None, "channels": None, "integrated_lufs": None, "true_peak": None
    }
    d = Deliverable(
        package_id=package.id,
        type=type,
        filename=filename,
        blob_sha=blob_sha,
        size=len(data),
        sha256=_sha256(data),
        format=ext,
        sample_rate=meta["sample_rate"],
        bit_depth=meta["bit_depth"],
        channels=meta["channels"],
        integrated_lufs=meta["integrated_lufs"],
        true_peak=meta["true_peak"],
        is_required=is_required,
    )
    db.add(d)
    db.flush()
    _event(db, package, "deliverable.added", user.username, f"{type} · {filename}")
    ledger.append(
        db,
        "deliverable.added",
        session_id=package.session_id,
        package_id=package.id,
        actor=user.username,
        entity_type="deliverable",
        entity_id=d.id,
        payload={"type": type, "filename": filename, "sha256": d.sha256},
    )
    db.commit()
    return _deliverable_out(d)


@router.post("/{package_id}/deliverables/from-version", response_model=DeliverableOut, status_code=status.HTTP_201_CREATED)
def add_deliverable_from_version(
    package_id: int,
    payload: DeliverableCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reuse an existing version's audio as a deliverable (e.g. approved master)."""
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    if package.status != "draft":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Package is locked — deliverables are immutable")
    source = db.get(ReviewVersion, payload.from_version_id)
    if source is None or source.session_id != package.session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source version not found")
    data = storage.read_blob(source.blob_sha)
    meta = _riff_meta(data) if source.audio_format in ("wav", "aif", "aiff") else {
        "sample_rate": None, "bit_depth": None, "channels": None, "integrated_lufs": None, "true_peak": None
    }
    d = Deliverable(
        package_id=package.id,
        type=payload.type,
        filename=f"{source.label}_{payload.type}.{source.audio_format}".replace(" ", "_"),
        blob_sha=source.blob_sha,
        size=len(data),
        sha256=_sha256(data),
        format=source.audio_format,
        sample_rate=meta["sample_rate"],
        bit_depth=meta["bit_depth"],
        channels=meta["channels"],
        integrated_lufs=meta["integrated_lufs"],
        true_peak=meta["true_peak"],
        is_required=payload.is_required,
        source_version_id=source.id,
    )
    db.add(d)
    db.flush()
    _event(db, package, "deliverable.added", user.username, f"{payload.type} · from {source.label}")
    ledger.append(
        db,
        "deliverable.added",
        session_id=package.session_id,
        package_id=package.id,
        actor=user.username,
        entity_type="deliverable",
        entity_id=d.id,
        payload={"type": payload.type, "filename": d.filename, "sha256": d.sha256, "source": source.label},
    )
    db.commit()
    return _deliverable_out(d)


@router.post("/{package_id}/lock", response_model=ReleasePackageOut)
def lock_package(
    package_id: int,
    payload: ReleaseLockIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Freeze the package: compute the manifest hash and open the delivery link."""
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    if package.status != "draft":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Package is already locked")
    if package.session.deposit_status == "deposit_due":
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "Booking deposit due — collect the deposit before locking the final delivery",
        )
    preflight = _run_preflight(db, package)
    if preflight.blocking and not payload.force:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Preflight found blocking issues — fix them, or lock anyway with force",
        )
    if payload.force and not payload.force_reason.strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provide a reason (force_reason) for the forced lock — it is recorded in the manifest and the ledger",
        )
    delivs = db.scalars(
        select(Deliverable).where(Deliverable.package_id == package.id)
    ).all()
    if not delivs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add at least one deliverable before locking")
    warnings = [c.detail for c in preflight.checks if c.status == "warn"]
    manifest = {
        "package": package.name,
        "approved_version": package.approved_version.label,
        "approval_scope": payload.approval_scope,
        "locked_by": user.username,
        "locked_at": utcnow().isoformat(),
        "note": payload.note.strip(),
        "qc_status": "forced" if payload.force else "passed",
        "unresolved_warnings": warnings,
        "confirmed_by": user.username,
        "force_reason": payload.force_reason.strip() if payload.force else "",
        "files": [
            {
                "type": d.type,
                "filename": d.filename,
                "sha256": d.sha256,
                "size": d.size,
                "format": d.format,
                "sample_rate": d.sample_rate,
                "bit_depth": d.bit_depth,
            }
            for d in delivs
        ],
    }
    manifest_hash = _sha256(json.dumps(manifest, sort_keys=True).encode())
    package.status = "ready"
    package.immutable_at = utcnow()
    package.manifest_hash = manifest_hash
    package.locked_by = user.username
    package.delivery_token = secrets.token_urlsafe(16)
    if payload.force:
        package.force_locked_reason = payload.force_reason.strip()
        package.force_locked_by = user.username
    _event(db, package, "package.locked", user.username, f"SHA-256 {manifest_hash[:12]}…")
    ledger.append(
        db,
        "package.locked",
        session_id=package.session_id,
        package_id=package.id,
        actor=user.username,
        entity_type="package",
        entity_id=package.id,
        payload={
            "approved_version": package.approved_version.label,
            "manifest_sha256": manifest_hash,
            "approval_scope": payload.approval_scope,
            "qc_status": "forced" if payload.force else "passed",
        },
    )
    if payload.force:
        ledger.append(
            db,
            "package.lock_forced",
            session_id=package.session_id,
            package_id=package.id,
            actor=user.username,
            entity_type="package",
            entity_id=package.id,
            payload={
                "package": package.name,
                "reason": payload.force_reason.strip()[:300],
                "warnings": warnings[:10],
                "confirmed_by": user.username,
            },
        )
    db.commit()
    return _package_out(db, package)


@router.post("/{package_id}/preflight", response_model=PreflightOut)
def package_preflight(
    package_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the QC preflight without locking — the UI shows the checklist first."""
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    return _run_preflight(db, package)


@router.patch("/{package_id}/handoff", response_model=ReleasePackageOut)
def update_handoff(
    package_id: int,
    payload: HandoffUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Session-file handoff metadata: plugin manifest, session manifest,
    consolidate-audio flag and archive expiry."""
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    if payload.plugin_manifest is not None:
        package.plugin_manifest = payload.plugin_manifest
    if payload.session_manifest is not None:
        package.session_manifest = payload.session_manifest
    if payload.consolidate_audio is not None:
        package.consolidate_audio = payload.consolidate_audio
    if payload.archive_expires_at is not None:
        package.archive_expires_at = payload.archive_expires_at
    if payload.last_verified_opened_at is not None:
        package.last_verified_opened_at = payload.last_verified_opened_at
    _event(db, package, "package.handoff_updated", user.username, "session/plugin manifest")
    ledger.append(
        db,
        "package.handoff_updated",
        session_id=package.session_id,
        package_id=package.id,
        actor=user.username,
        entity_type="package",
        entity_id=package.id,
        payload={
            "package": package.name,
            "consolidate_audio": package.consolidate_audio,
            "archive_expires_at": package.archive_expires_at.isoformat() if package.archive_expires_at else "",
        },
    )
    db.commit()
    return _package_out(db, package)


@router.post("/{package_id}/archive", response_model=ReleasePackageOut)
def set_archive_status(
    package_id: int,
    payload: ArchiveUpdate = ArchiveUpdate(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Move the package through its archive lifecycle. Archived projects keep
    their retention date; nothing promises session restoration without it."""
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    from datetime import timedelta

    package.archive_status = payload.archive_status
    if payload.archive_expires_at is not None:
        package.archive_expires_at = payload.archive_expires_at
    elif payload.archive_status == "archived" and not package.archive_expires_at:
        package.archive_expires_at = utcnow() + timedelta(days=90)
    _event(db, package, f"package.{payload.archive_status}", user.username, "archive status")
    ledger.append(
        db,
        "package.archived" if payload.archive_status == "archived" else "package.handoff_updated",
        session_id=package.session_id,
        package_id=package.id,
        actor=user.username,
        entity_type="package",
        entity_id=package.id,
        payload={"package": package.name, "archive_status": package.archive_status},
    )
    db.commit()
    return _package_out(db, package)


@router.get("/{package_id}/manifest", response_model=DeliveryManifestOut)
def get_manifest(
    package_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    if not package.manifest_hash:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Package is not locked yet")
    delivs = db.scalars(
        select(Deliverable).where(Deliverable.package_id == package.id)
    ).all()
    manifest = {
        "package": package.name,
        "approved_version": package.approved_version.label,
        "locked_by": package.locked_by,
        "locked_at": package.immutable_at.isoformat() if package.immutable_at else "",
        "qc_status": "forced" if package.force_locked_by else "passed",
        "unresolved_warnings": [],
        "confirmed_by": package.force_locked_by or package.locked_by,
        "force_reason": package.force_locked_reason or "",
        "files": [
            {"type": d.type, "filename": d.filename, "sha256": d.sha256, "size": d.size}
            for d in delivs
        ],
    }
    return DeliveryManifestOut(
        package=_package_out(db, package),
        manifest_json=manifest,
        manifest_hash=package.manifest_hash,
    )


@router.patch("/{package_id}/invoice", response_model=ReleasePackageOut)
def update_invoice(
    package_id: int,
    payload: DeliveryInvoiceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    if payload.invoice_status in ("deposit_due", "balance_due") and not payload.amount_due_cents:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Set an amount (amount_due_cents) before charging '{payload.invoice_status}'",
        )
    package.invoice_status = payload.invoice_status
    if payload.amount_due_cents is not None:
        package.amount_due_cents = payload.amount_due_cents
    if payload.currency:
        package.currency = payload.currency
    if payload.invoice_status == "paid":
        _event(db, package, "invoice.paid", user.username, "payment confirmed — delivery unlocked")
        ledger.append(
            db,
            "invoice.paid",
            session_id=package.session_id,
            package_id=package.id,
            actor=user.username,
            entity_type="package",
            entity_id=package.id,
            payload={"package": package.name, "method": "manual"},
        )
    db.commit()
    return _package_out(db, package)


@router.get("/{package_id}/download")
def download_package_file(
    package_id: int,
    deliverable_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    d = db.get(Deliverable, deliverable_id)
    if d is None or d.package_id != package.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deliverable not found")
    data = storage.read_blob(d.blob_sha)
    _event(db, package, "delivery.downloaded", user.username, d.filename)
    db.commit()
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type=f"application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{d.filename}"'},
    )


# ---------- public delivery link (/d/:token) ----------


@router.get("/public/{delivery_token}", response_model=DeliveryPageOut)
def public_delivery_page(
    delivery_token: str,
    db: Session = Depends(get_db),
):
    package = db.scalar(
        select(ReleasePackage).where(ReleasePackage.delivery_token == delivery_token)
    )
    if package is None or package.status != "ready":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Delivery link not found")
    delivs = db.scalars(
        select(Deliverable).where(Deliverable.package_id == package.id)
    ).all()
    _event(db, package, "delivery.link_opened", "anonymous", "")
    ledger.append(
        db,
        "delivery.link_opened",
        session_id=package.session_id,
        package_id=package.id,
        actor="anonymous",
        entity_type="package",
        entity_id=package.id,
        payload={},
    )
    db.commit()
    return DeliveryPageOut(
        id=package.id,
        name=package.name,
        status=package.status,
        invoice_status=package.invoice_status,
        amount_due_cents=package.amount_due_cents,
        currency=package.currency or "usd",
        deposit_due_cents=package.session.deposit_due_cents,
        deposit_status=package.session.deposit_status,
        locked_by=package.locked_by,
        immutable_at=package.immutable_at,
        manifest_hash=package.manifest_hash,
        approved_label=package.approved_version.label,
        approved_filename=package.approved_version.filename,
        template=package.template or "custom",
        archive_status=package.archive_status or "available_now",
        archive_expires_at=package.archive_expires_at,
        last_verified_opened_at=package.last_verified_opened_at,
        retention_until=package.session.retention_until,
        share_token=package.session.share_token,
        deliverables=[_deliverable_out(d) for d in delivs],
    )


@router.get("/public/{delivery_token}/files/{deliverable_id}")
def public_delivery_download(
    delivery_token: str,
    deliverable_id: int,
    db: Session = Depends(get_db),
):
    package = db.scalar(
        select(ReleasePackage).where(ReleasePackage.delivery_token == delivery_token)
    )
    if package is None or package.status != "ready":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Delivery link not found")
    if package.session.deposit_status == "deposit_due":
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "Booking deposit due — pay it before downloading the final files",
        )
    if package.invoice_status not in ("none", "paid", "waived"):
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Payment required — invoice status: {package.invoice_status}",
        )
    d = db.get(Deliverable, deliverable_id)
    if d is None or d.package_id != package.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deliverable not found")
    data = storage.read_blob(d.blob_sha)
    _event(db, package, "delivery.downloaded", "anonymous", d.filename)
    db.commit()
    from fastapi.responses import Response

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{d.filename}"'},
    )


# ---------- Stripe paid delivery ----------


def _checkout_session(
    package: ReleasePackage,
    success_url: str,
    cancel_url: str,
    db: Session,
) -> CheckoutOut:
    """Create (or reuse) a Stripe Checkout Session for this package."""
    if not stripe_pay.enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Stripe is not configured — set STRIPE_SECRET_KEY or use the manual invoice flow",
        )
    if package.status != "ready":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Lock the package before charging")
    if package.invoice_status not in ("deposit_due", "balance_due"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Invoice status '{package.invoice_status}' has nothing to charge",
        )
    amount = package.amount_due_cents
    if not amount or amount <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Set an amount on the invoice before creating a checkout session",
        )
    if package.stripe_session_id:
        # idempotent: return the existing session so a refresh doesn't double-charge
        try:
            data = stripe_pay.retrieve_checkout_session(package.stripe_session_id)
            return CheckoutOut(
                checkout_url=data["url"],
                session_id=data["id"],
                amount_due_cents=amount,
                currency=package.currency or "usd",
            )
        except Exception:
            pass  # fall through and create a fresh session
    try:
        session_id, url = stripe_pay.create_checkout_session(
            amount_cents=amount,
            currency=package.currency or "usd",
            package_id=package.id,
            package_name=package.name,
            session_id=package.session_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    package.stripe_session_id = session_id
    db.add(package)
    _event(db, package, "invoice.checkout_created", "owner", session_id)
    ledger.append(
        db,
        "invoice.checkout_created",
        session_id=package.session_id,
        package_id=package.id,
        actor="owner",
        entity_type="package",
        entity_id=package.id,
        payload={"stripe_session": session_id, "amount_cents": amount},
    )
    db.commit()
    return CheckoutOut(
        checkout_url=url,
        session_id=session_id,
        amount_due_cents=amount,
        currency=package.currency or "usd",
    )


@router.post("/{package_id}/checkout", response_model=CheckoutOut)
def owner_checkout(
    package_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    package = db.get(ReleasePackage, package_id)
    if package is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")
    _require_owner(package, user)
    origin = "http://localhost:5173"  # dev; frontend passes its own URL
    return _checkout_session(
        package,
        success_url=f"{origin}/d/{package.delivery_token}?paid=1",
        cancel_url=f"{origin}/d/{package.delivery_token}",
        db=db,
    )


@router.post("/public/{delivery_token}/checkout", response_model=CheckoutOut)
def public_checkout(
    delivery_token: str,
    kind: str = Form("package"),
    success_url: str = Form(""),
    cancel_url: str = Form(""),
    db: Session = Depends(get_db),
):
    """Let the client pay from the delivery page without an account.

    `kind=package` charges the package invoice; `kind=deposit` charges the
    session's booking deposit (same webhook, metadata kind=deposit).
    """
    package = db.scalar(
        select(ReleasePackage).where(ReleasePackage.delivery_token == delivery_token)
    )
    if package is None or package.status != "ready":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Delivery link not found")
    origin = success_url or f"http://localhost:5173/d/{delivery_token}?paid=1"
    if kind == "deposit":
        from .sessions import _session_checkout

        return _session_checkout(
            package.session,
            "deposit",
            success_url=origin,
            cancel_url=cancel_url or f"http://localhost:5173/d/{delivery_token}",
            db=db,
        )
    return _checkout_session(
        package,
        success_url=origin,
        cancel_url=cancel_url or f"http://localhost:5173/d/{delivery_token}",
        db=db,
    )


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook: checkout.session.completed → mark invoice paid.

    Signature is verified with the Stripe-Signature header before any state
    change; the handler is idempotent (a replayed event is a no-op).
    """
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe_pay.verify_webhook_signature(payload, sig)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid signature: {exc}")

    if event.get("type") != "checkout.session.completed":
        return {"received": True, "handled": False}
    session_obj = event.get("data", {}).get("object", {})
    metadata = session_obj.get("metadata") or {}

    # Session-level charges: booking deposit and extra revision rounds are
    # paid through the same webhook, identified by metadata `kind`.
    kind = metadata.get("kind")
    session_id = metadata.get("session_id")
    if kind == "change_order":
        co_id = metadata.get("change_order_id")
        if not co_id:
            return {"received": True, "handled": False}
        from .change_orders import grant_change_order_round

        granted = grant_change_order_round(db, int(co_id), actor="stripe")
        db.commit()
        return {"received": True, "handled": granted}
    if kind in ("deposit", "extra_round") and session_id:
        session = db.get(ReviewSession, int(session_id))
        if session is None:
            return {"received": True, "handled": False}
        if kind == "deposit" and session.deposit_status != "paid":
            session.deposit_status = "paid"
            session.updated_at = utcnow()
            ledger.append(
                db,
                "deposit.paid",
                session_id=session.id,
                actor="stripe",
                entity_type="session",
                entity_id=session.id,
                payload={"session": session.name, "method": "stripe", "checkout": session_obj.get("id")},
            )
        if kind == "extra_round":
            session.rounds_paid = (session.rounds_paid or 0) + 1
            session.updated_at = utcnow()
            ledger.append(
                db,
                "round.extra_paid",
                session_id=session.id,
                actor="stripe",
                entity_type="round",
                entity_id=session.id,
                payload={"round": session.round_number + 1, "method": "stripe", "checkout": session_obj.get("id")},
            )
        db.commit()
        return {"received": True, "handled": True}

    package_id = metadata.get("package_id")
    if package_id is None or package_id == "0":
        return {"received": True, "handled": False}
    package = db.get(ReleasePackage, int(package_id))
    if package is None:
        return {"received": True, "handled": False}
    if package.invoice_status == "paid":
        return {"received": True, "handled": True, "already_paid": True}  # idempotent
    package.invoice_status = "paid"
    package.stripe_session_id = session_obj.get("id") or package.stripe_session_id
    _event(db, package, "invoice.paid", "stripe", "checkout.session.completed")
    ledger.append(
        db,
        "invoice.paid",
        session_id=package.session_id,
        package_id=package.id,
        actor="stripe",
        entity_type="package",
        entity_id=package.id,
        payload={"package": package.name, "method": "stripe", "session": session_obj.get("id")},
    )
    db.commit()
    return {"received": True, "handled": True}
