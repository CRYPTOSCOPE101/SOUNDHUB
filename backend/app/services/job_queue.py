"""Background job queue — in-process worker with thread pool.

Designed for development and self-hosted deployments.
For production scale, swap the executor for Celery + Redis or Arq + Redis.

Usage:
    from .services.job_queue import enqueue_job, get_job_status

    job_id = enqueue_job("generate_waveform", storage_object_id=42, input_json={"filename": "mix.wav"})
    status = get_job_status(job_id)
"""
from __future__ import annotations

import json
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import DATABASE_URL
from ..models import Job

logger = logging.getLogger(__name__)

# ── Engine & session factory (isolated from request sessions) ───────────

_engine = create_engine(DATABASE_URL, echo=False)
_SessionFactory = sessionmaker(bind=_engine)

# ── Worker pool ─────────────────────────────────────────────────────────

_WORKERS = int(os.environ.get("SOUNDHUB_JOB_WORKERS", "4"))
_executor = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="job-worker")

# ── Job type → handler mapping ──────────────────────────────────────────

_HANDLERS: dict[str, callable] = {}


def register_handler(job_type: str):
    """Decorator to register a job handler function."""

    def decorator(fn):
        _HANDLERS[job_type] = fn
        return fn

    return decorator


# ── Public API ──────────────────────────────────────────────────────────


def enqueue_job(
    job_type: str,
    *,
    storage_object_id: int | None = None,
    project_id: int | None = None,
    commit_id: int | None = None,
    version_id: int | None = None,
    session_id: int | None = None,
    input_json: dict[str, Any] | None = None,
    created_by_id: int | None = None,
) -> int:
    """Create a job record and submit it to the worker pool.

    Returns the job id.
    """
    if job_type not in _HANDLERS:
        raise ValueError(
            f"Unknown job type {job_type!r}. "
            f"Registered: {sorted(_HANDLERS)}"
        )

    db = _SessionFactory()
    try:
        job = Job(
            type=job_type,
            status="queued",
            storage_object_id=storage_object_id,
            project_id=project_id,
            commit_id=commit_id,
            version_id=version_id,
            session_id=session_id,
            input_json=input_json or {},
            created_by_id=created_by_id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    _executor.submit(_run_job, job_id)
    return job_id


def get_job_status(job_id: int) -> dict[str, Any] | None:
    """Fetch current job state from the database."""
    db = _SessionFactory()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return None
        return {
            "id": job.id,
            "type": job.type,
            "status": job.status,
            "progress": job.progress,
            "output_json": job.output_json,
            "error_message": job.error_message,
            "attempts": job.attempts,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }
    finally:
        db.close()


def cancel_job(job_id: int) -> bool:
    """Mark a queued job as cancelled (no-op if already running)."""
    db = _SessionFactory()
    try:
        job = db.get(Job, job_id)
        if job is None or job.status not in ("queued",):
            return False
        job.status = "cancelled"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return True
    finally:
        db.close()


def list_jobs(
    *,
    project_id: int | None = None,
    status: str | None = None,
    job_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List jobs with optional filters."""
    db = _SessionFactory()
    try:
        q = db.query(Job)
        if project_id is not None:
            q = q.filter(Job.project_id == project_id)
        if status is not None:
            q = q.filter(Job.status == status)
        if job_type is not None:
            q = q.filter(Job.type == job_type)
        jobs = q.order_by(Job.id.desc()).limit(limit).all()
        return [
            {
                "id": j.id,
                "type": j.type,
                "status": j.status,
                "progress": j.progress,
                "storage_object_id": j.storage_object_id,
                "project_id": j.project_id,
                "commit_id": j.commit_id,
                "created_by_id": j.created_by_id,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ]
    finally:
        db.close()


# ── Internal worker ─────────────────────────────────────────────────────


def _run_job(job_id: int) -> None:
    """Execute a job in a background thread."""
    db = _SessionFactory()
    try:
        job = db.get(Job, job_id)
        if job is None:
            logger.warning("Job %d not found", job_id)
            return

        if job.status == "cancelled":
            return

        handler = _HANDLERS.get(job.type)
        if handler is None:
            job.status = "failed"
            job.error_message = f"No handler for job type {job.type!r}"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.attempts += 1
        db.commit()

        try:
            result = handler(job, db)
            job.status = "completed"
            job.progress = 100
            job.output_json = result or {}
            job.finished_at = datetime.now(timezone.utc)

            # Persist results into domain models (DAW metadata, loudness, etc.)
            try:
                from .job_result_persistence import persist_job_result
                persist_job_result(job, result or {}, db)
            except Exception:
                logger.exception("Result persistence failed for job %d", job_id)

        except Exception as exc:
            logger.exception("Job %d failed", job_id)
            job.error_message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.finished_at = datetime.now(timezone.utc)
            else:
                # Retry: reset to queued
                job.status = "queued"
                job.progress = 0

        db.commit()

        # Emit webhook events for job lifecycle (best-effort)
        try:
            from ..routers.integrations import dispatch_event
            event_data = {
                "job_id": job.id,
                "job_type": job.type,
                "status": job.status,
                "project_id": job.project_id,
                "commit_id": job.commit_id,
            }
            if job.status == "completed":
                dispatch_event("job.completed", event_data, job.created_by_id)
            elif job.status == "failed":
                event_data["error"] = (job.error_message or "")[:200]
                dispatch_event("job.failed", event_data, job.created_by_id)
        except Exception:
            pass  # Best-effort webhook delivery
    finally:
        db.close()
