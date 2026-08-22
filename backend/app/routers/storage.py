"""Storage router — pluggable object storage with presigned URLs.

Endpoints:
    POST   /api/storage/uploads                  — create upload intent → presigned PUT URL
    POST   /api/storage/uploads/{object_id}/complete — finalize upload, verify SHA-256
    GET    /api/storage/objects/{object_id}       — get object metadata
    POST   /api/storage/objects/{object_id}/download-url — get presigned download URL
    DELETE /api/storage/objects/{object_id}       — soft-delete (mark deleted)
    GET    /api/storage/objects/{object_id}/status — job / processing status
    GET    /api/storage/usage                    — storage usage for current user
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import MAX_UPLOAD_SIZE
from ..database import get_db
from ..models import StorageAuditEvent, StorageObject
from ..security import get_current_user
from ..services.storage import get_storage

router = APIRouter(prefix="/api/storage", tags=["storage"])


# ── Request / response schemas ──────────────────────────────────────────


class UploadIntentRequest(BaseModel):
    filename: str = ""
    content_type: str = "application/octet-stream"
    byte_size: int = 0
    sha256: str = ""
    kind: str = "artifact"  # daw_project | master | stem | preview | sample | preset | artifact
    project_id: Optional[int] = None
    commit_id: Optional[int] = None


class UploadIntentResponse(BaseModel):
    object_id: int
    sha256: str
    upload_url: str
    storage_key: str
    expires_in: int = 900


class ObjectMetadataResponse(BaseModel):
    id: int
    sha256: str
    storage_provider: str
    original_filename: str
    content_type: str
    byte_size: int
    kind: str
    status: str
    project_id: Optional[int] = None
    commit_id: Optional[int] = None
    created_at: datetime


class DownloadUrlResponse(BaseModel):
    download_url: str
    expires_in: int = 900


class StorageUsageResponse(BaseModel):
    total_objects: int
    total_bytes: int
    by_kind: dict[str, int]


# ── Helpers ─────────────────────────────────────────────────────────────


def _get_object_or_404(object_id: int, db: Session) -> StorageObject:
    obj = db.get(StorageObject, object_id)
    if obj is None or obj.status == "deleted":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Storage object not found")
    return obj


def _check_project_access(obj: StorageObject, user, db: Session) -> None:
    """Verify the user has access to the project owning this storage object."""
    if obj.project_id is None:
        # No project association — object belongs to the uploading user
        if obj.uploaded_by_id and obj.uploaded_by_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
        return
    from ..models import Project
    project = db.get(Project, obj.project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: not project owner")
    return obj


def _content_address_key(sha256: str) -> str:
    """Build content-addressed storage key from SHA-256 hex."""
    return f"blobs/{sha256[:2]}/{sha256[2:4]}/{sha256}"


def _audit(
    db: Session,
    obj: StorageObject,
    action: str,
    user_id: int | None,
    request: Request | None = None,
    detail: str = "",
) -> None:
    event = StorageAuditEvent(
        storage_object_id=obj.id,
        actor_id=user_id,
        action=action,
        ip_address=request.client.host if request and request.client else "",
        user_agent=request.headers.get("user-agent", "") if request else "",
        detail=detail,
    )
    db.add(event)


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post("/uploads", response_model=UploadIntentResponse, status_code=status.HTTP_201_CREATED)
def create_upload_intent(
    body: UploadIntentRequest,
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an upload intent and return a presigned URL.

    Flow:
        1. Client asks for upload permission → API returns object_id + upload URL.
        2. Client PUTs the file directly to the presigned URL.
        3. Client POSTs to /uploads/{object_id}/complete.
    """
    storage = get_storage()

    # If sha256 provided, check for existing dedup
    if body.sha256:
        existing = db.scalar(
            select(StorageObject).where(StorageObject.sha256 == body.sha256)
        )
        if existing and existing.status not in ("deleted", "failed"):
            # Already stored — return the existing object
            _audit(db, existing, "presign", user.id, request, "dedup-hit")
            db.commit()
            storage_key = _content_address_key(existing.sha256)
            return UploadIntentResponse(
                object_id=existing.id,
                sha256=existing.sha256,
                upload_url=storage.create_upload_url(
                    storage_key, body.content_type or "application/octet-stream"
                ),
                storage_key=storage_key,
            )

    # Determine storage key
    if body.sha256:
        storage_key = _content_address_key(body.sha256)
    else:
        # Will be determined after upload (need the file to compute hash)
        storage_key = f"pending/{hashlib.sha256(str(datetime.now(timezone.utc).timestamp()).encode()).hexdigest()[:16]}"

    obj = StorageObject(
        sha256=body.sha256 or "",
        storage_provider="local" if not hasattr(storage, "bucket") else "s3",
        storage_key=storage_key,
        original_filename=body.filename,
        content_type=body.content_type or "application/octet-stream",
        byte_size=body.byte_size,
        kind=body.kind,
        status="pending_upload" if not body.sha256 else "uploaded",
        uploaded_by_id=user.id,
        project_id=body.project_id,
        commit_id=body.commit_id,
    )
    db.add(obj)
    db.flush()  # get obj.id

    _audit(db, obj, "upload_intent", user.id, request, f"filename={body.filename}")
    db.commit()
    db.refresh(obj)

    upload_url = storage.create_upload_url(storage_key, body.content_type or "application/octet-stream")

    return UploadIntentResponse(
        object_id=obj.id,
        sha256=obj.sha256,
        upload_url=upload_url,
        storage_key=storage_key,
    )


@router.post("/uploads/{object_id}/complete")
def complete_upload(
    object_id: int,
    request: Request,
    sha256: Optional[str] = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Finalize an upload.  Optionally verify SHA-256."""
    obj = _get_object_or_404(object_id, db)
    _check_project_access(obj, user, db)
    if obj.status not in ("pending_upload", "uploaded"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Object is in '{obj.status}' state")

    if sha256 and obj.sha256 and sha256 != obj.sha256:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"SHA-256 mismatch: expected {obj.sha256}, got {sha256}",
        )

    # If sha256 was not set at intent time, update it now
    if sha256 and not obj.sha256:
        obj.sha256 = sha256
        obj.storage_key = _content_address_key(sha256)

    obj.status = "uploaded"
    obj.byte_size = obj.byte_size  # could re-verify from storage
    _audit(db, obj, "complete", user.id, request)
    db.commit()
    return {"id": obj.id, "status": obj.status, "sha256": obj.sha256}


@router.get("/objects/{object_id}", response_model=ObjectMetadataResponse)
def get_object_metadata(
    object_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    obj = _get_object_or_404(object_id, db)
    _check_project_access(obj, user, db)
    return ObjectMetadataResponse(
        id=obj.id,
        sha256=obj.sha256,
        storage_provider=obj.storage_provider,
        original_filename=obj.original_filename,
        content_type=obj.content_type,
        byte_size=obj.byte_size,
        kind=obj.kind,
        status=obj.status,
        project_id=obj.project_id,
        commit_id=obj.commit_id,
        created_at=obj.created_at,
    )


@router.post("/objects/{object_id}/download-url", response_model=DownloadUrlResponse)
def create_download_url(
    object_id: int,
    request: Request,
    expires_in: int = 900,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    obj = _get_object_or_404(object_id, db)
    _check_project_access(obj, user, db)
    if obj.status not in ("uploaded", "ready"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Object is in '{obj.status}' state")

    storage = get_storage()
    url = storage.create_download_url(obj.storage_key, expires_in=expires_in)

    _audit(db, obj, "download", user.id, request, f"expires_in={expires_in}")
    db.commit()

    return DownloadUrlResponse(download_url=url, expires_in=expires_in)


@router.delete("/objects/{object_id}")
def delete_object(
    object_id: int,
    request: Request,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    obj = _get_object_or_404(object_id, db)
    _check_project_access(obj, user, db)
    obj.status = "deleted"
    obj.deleted_at = datetime.now(timezone.utc)
    _audit(db, obj, "delete", user.id, request)
    db.commit()
    return {"id": obj.id, "status": "deleted"}


@router.get("/objects/{object_id}/status")
def get_object_status(
    object_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    obj = _get_object_or_404(object_id, db)
    _check_project_access(obj, user, db)
    return {
        "id": obj.id,
        "status": obj.status,
        "sha256": obj.sha256,
        "processed_at": obj.processed_at,
    }


@router.get("/usage", response_model=StorageUsageResponse)
def get_storage_usage(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return storage usage stats for the current user."""
    base = select(StorageObject).where(
        StorageObject.uploaded_by_id == user.id,
        StorageObject.status != "deleted",
    )
    objects = db.scalars(base).all()

    total_bytes = sum(o.byte_size for o in objects)
    by_kind: dict[str, int] = {}
    for o in objects:
        by_kind[o.kind] = by_kind.get(o.kind, 0) + 1

    return StorageUsageResponse(
        total_objects=len(objects),
        total_bytes=total_bytes,
        by_kind=by_kind,
    )


@router.post("/cleanup")
def cleanup_stale_uploads(
    ttl_minutes: int = 60,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove StorageObjects stuck in pending_upload for longer than TTL.

    Only admins should call this. For now, any authenticated user can trigger it.
    """
    from ..services.storage_cleanup import cleanup_stale_uploads as _cleanup
    removed = _cleanup(ttl_minutes=ttl_minutes)
    return {"removed": removed, "ttl_minutes": ttl_minutes}
