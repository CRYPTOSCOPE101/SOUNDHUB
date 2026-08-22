"""Stale-upload cleanup — remove StorageObjects stuck in pending_upload.

Run periodically (e.g., cron every hour or via FastAPI startup scheduler):

    from app.services.storage_cleanup import cleanup_stale_uploads
    removed = cleanup_stale_uploads(ttl_minutes=60)

Objects in ``pending_upload`` state older than ``ttl_minutes`` are
marked as ``deleted`` and their blobs are removed from the storage
backend.  Objects that transitioned to ``uploaded`` or later are left
untouched.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update

from ..database import SessionLocal
from ..models import StorageObject
from . import storage

logger = logging.getLogger(__name__)


def cleanup_stale_uploads(
    ttl_minutes: int = 60,
    *,
    storage_provider: str | None = None,
) -> int:
    """Mark stale pending-upload objects as deleted and remove blobs.

    Returns the number of objects cleaned up.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes)
    db = SessionLocal()
    removed = 0
    try:
        q = (
            select(StorageObject)
            .where(
                StorageObject.status == "pending_upload",
                StorageObject.created_at < cutoff,
            )
        )
        stale = db.scalars(q).all()

        for obj in stale:
            try:
                # Remove blob from storage backend
                if storage_provider is None or obj.storage_provider == storage_provider:
                    try:
                        storage.get_storage().delete(obj.sha256)
                    except FileNotFoundError:
                        pass  # Already gone

                # Mark as deleted
                obj.status = "deleted"
                obj.deleted_at = datetime.now(timezone.utc)
                removed += 1
            except Exception as exc:
                logger.warning(
                    "Failed to clean up StorageObject %d (%s): %s",
                    obj.id, obj.sha256[:12], exc,
                )

        if removed:
            db.commit()
            logger.info("Cleaned up %d stale pending-upload objects", removed)

    except Exception as exc:
        db.rollback()
        logger.error("Stale upload cleanup failed: %s", exc)
    finally:
        db.close()

    return removed


def cleanup_expired_download_urls(ttl_minutes: int = 15) -> int:
    """Revoke download URLs older than TTL.

    This is a no-op for local storage (URLs are always valid).
    For S3, this would abort incomplete multipart uploads.

    Returns 0 (placeholder for future S3 multipart cleanup).
    """
    # TODO: For S3ObjectStorage, list and abort multipart uploads
    # that have been pending for longer than ttl_minutes.
    return 0
