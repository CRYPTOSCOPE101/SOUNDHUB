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

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
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
    DeliverableCreate,
    DeliverableOut,
    DeliveryInvoiceUpdate,
    DeliveryManifestOut,
    DeliveryPageOut,
    ReleaseLockIn,
    ReleasePackageCreate,
    ReleasePackageOut,
)
from ..security import get_current_user
from ..services import storage, waveform

router = APIRouter(prefix="/api/release-packages", tags=["release packages"])

ALLOWED_FILES = {"wav", "mp3", "flac", "aif", "aiff", "m4a", "ogg", "png", "jpg", "jpeg", "pdf", "zip"}


def _event(db: Session, package: ReleasePackage, event: str, actor: str, detail: str = "") -> None:
    db.add(DeliveryEvent(package_id=package.id, event=event, actor=actor, detail=detail))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _riff_meta(data: bytes) -> dict:
    """sample_rate / bit_depth from a WAV header; loudness placeholders are None."""
    info = waveform._riff_wave_info(data) if data[:4] == b"RIFF" else None
    if not info:
        return {"sample_rate": None, "bit_depth": None, "integrated_lufs": None, "true_peak": None}
    # sample_rate from fmt is not exposed by _riff_wave_info; re-derive cheaply
    import struct as _struct
    from io import BytesIO as _BytesIO

    buf = _BytesIO(data)
    buf.seek(12)
    sr = None
    bits = None
    while True:
        header = buf.read(8)
        if len(header) < 8:
            break
        cid, csize = _struct.unpack("<4sI", header)
        if cid == b"fmt ":
            chunk = buf.read(csize)
            if len(chunk) >= 16:
                sr = _struct.unpack("<I", chunk[4:8])[0]
                bits = _struct.unpack("<H", chunk[14:16])[0]
            break
        buf.seek(csize + (csize % 2), 1)
    return {
        "sample_rate": sr,
        "bit_depth": bits,
        "integrated_lufs": None,  # real loudness analysis is a later milestone
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
        immutable_at=p.immutable_at,
        manifest_hash=p.manifest_hash,
        delivery_token=p.delivery_token,
        created_at=p.created_at,
        locked_by=p.locked_by,
        deliverables=[_deliverable_out(d) for d in delivs],
        events=[
            {"event": e.event, "actor": e.actor, "detail": e.detail, "created_at": e.created_at.isoformat()}
            for e in events
        ],
    )


def _require_owner(package: ReleasePackage, user: User) -> None:
    if package.session.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Package not found")


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
    package = ReleasePackage(
        session_id=session.id,
        approved_version_id=version.id,
        name=payload.name.strip() or "Final delivery",
    )
    db.add(package)
    db.flush()
    _event(db, package, "package.created", user.username, f"approved {version.label}")
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
        "sample_rate": None, "bit_depth": None, "integrated_lufs": None, "true_peak": None
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
        integrated_lufs=meta["integrated_lufs"],
        true_peak=meta["true_peak"],
        is_required=is_required,
    )
    db.add(d)
    db.flush()
    _event(db, package, "deliverable.added", user.username, f"{type} · {filename}")
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
        "sample_rate": None, "bit_depth": None, "integrated_lufs": None, "true_peak": None
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
        integrated_lufs=meta["integrated_lufs"],
        true_peak=meta["true_peak"],
        is_required=payload.is_required,
        source_version_id=source.id,
    )
    db.add(d)
    db.flush()
    _event(db, package, "deliverable.added", user.username, f"{payload.type} · from {source.label}")
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
    delivs = db.scalars(
        select(Deliverable).where(Deliverable.package_id == package.id)
    ).all()
    if not delivs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add at least one deliverable before locking")
    manifest = {
        "package": package.name,
        "approved_version": package.approved_version.label,
        "approval_scope": payload.approval_scope,
        "locked_by": user.username,
        "locked_at": utcnow().isoformat(),
        "note": payload.note.strip(),
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
    _event(db, package, "package.locked", user.username, f"SHA-256 {manifest_hash[:12]}…")
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
    package.invoice_status = payload.invoice_status
    if payload.invoice_status == "paid":
        _event(db, package, "invoice.paid", user.username, "payment confirmed — delivery unlocked")
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
    db.commit()
    return DeliveryPageOut(
        id=package.id,
        name=package.name,
        status=package.status,
        invoice_status=package.invoice_status,
        locked_by=package.locked_by,
        immutable_at=package.immutable_at,
        manifest_hash=package.manifest_hash,
        approved_label=package.approved_version.label,
        approved_filename=package.approved_version.filename,
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
