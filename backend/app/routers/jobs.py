"""Jobs router — background processing queue API.

Endpoints:
    POST   /api/jobs                     — enqueue a new job
    GET    /api/jobs                     — list jobs (filtered)
    GET    /api/jobs/{job_id}            — get job status
    DELETE /api/jobs/{job_id}            — cancel a queued job
    POST   /api/jobs/{job_id}/retry      — retry a failed job
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import JOB_TYPES, Job
from ..security import get_current_user
from ..services import job_queue

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── Permission helpers ─────────────────────────────────────────────────

def _check_job_access(job_info: dict, user, db: Session) -> None:
    """Verify the user owns the project associated with this job."""
    project_id = job_info.get("project_id")
    if project_id is None:
        # No project — job was created by this user
        return
    from ..models import Project
    project = db.get(Project, project_id)
    if project is None or project.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: not project owner")


# ── Request / response schemas ──────────────────────────────────────────


class CreateJobRequest(BaseModel):
    type: str = Field(..., description="Job type (parse_daw, generate_waveform, ...)")
    storage_object_id: Optional[int] = None
    project_id: Optional[int] = None
    commit_id: Optional[int] = None
    version_id: Optional[int] = None
    session_id: Optional[int] = None
    input_json: Optional[dict] = None


class JobResponse(BaseModel):
    id: int
    type: str
    status: str
    progress: int
    output_json: Optional[dict] = None
    error_message: str = ""
    attempts: int
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: list[dict]
    total: int


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    body: CreateJobRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enqueue a background job. Returns 202 Accepted with job metadata."""
    if body.type not in JOB_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Invalid job type {body.type!r}. Valid: {JOB_TYPES}",
        )

    try:
        job_id = job_queue.enqueue_job(
            body.type,
            storage_object_id=body.storage_object_id,
            project_id=body.project_id,
            commit_id=body.commit_id,
            version_id=body.version_id,
            session_id=body.session_id,
            input_json=body.input_json,
            created_by_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    info = job_queue.get_job_status(job_id)
    return JobResponse(**info)


@router.get("")
def list_jobs(
    project_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 50,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List jobs with optional filters.

    If project_id is specified, verifies the user owns that project.
    If not specified, returns only jobs created by the current user.
    """
    if project_id is not None:
        from ..models import Project
        project = db.get(Project, project_id)
        if project is None or project.owner_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: not project owner")
    else:
        # No project filter — show only user's own jobs
        project_id = None

    jobs = job_queue.list_jobs(
        project_id=project_id,
        status=status_filter,
        job_type=job_type,
        limit=limit,
    )

    # When no project_id filter, additionally filter by creator
    if project_id is None:
        jobs = [j for j in jobs if j.get("created_by_id") == user.id]

    return {"jobs": jobs, "total": len(jobs)}


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get job status by id."""
    info = job_queue.get_job_status(job_id)
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    _check_job_access(info, user, db)
    return JobResponse(**info)


@router.delete("/{job_id}")
def cancel_job(
    job_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a queued job. Running jobs cannot be cancelled."""
    info = job_queue.get_job_status(job_id)
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    _check_job_access(info, user, db)
    ok = job_queue.cancel_job(job_id)
    if not ok:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot cancel job in '{info['status']}' state",
        )
    return {"id": job_id, "status": "cancelled"}


@router.post("/{job_id}/retry", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_job(
    job_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry a failed job by re-enqueuing it."""
    info = job_queue.get_job_status(job_id)
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    _check_job_access(info, user, db)
    if info["status"] != "failed":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Can only retry failed jobs, current status: {info['status']}",
        )

    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    new_id = job_queue.enqueue_job(
        job.type,
        storage_object_id=job.storage_object_id,
        project_id=job.project_id,
        commit_id=job.commit_id,
        version_id=job.version_id,
        session_id=job.session_id,
        input_json=job.input_json,
        created_by_id=user.id,
    )
    new_info = job_queue.get_job_status(new_id)
    return JobResponse(**new_info)
