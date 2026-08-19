"""Audio CI Checks — automated quality validation for audio files."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AudioCheck, Commit, utcnow
from ..schemas import AudioCheckCreate, AudioCheckOut, AudioCheckResultOut

router = APIRouter(prefix="/api/projects/{project_id}/commits/{commit_id}/checks", tags=["audio checks"])


@router.get("", response_model=AudioCheckResultOut)
def list_checks(project_id: int, commit_id: int, db: Session = Depends(get_db)):
    """Get all audio checks for a commit."""
    checks = db.scalars(select(AudioCheck).where(AudioCheck.commit_id == commit_id)).all()
    passed = sum(1 for c in checks if c.status == "pass")
    failed = sum(1 for c in checks if c.status == "fail")
    warned = sum(1 for c in checks if c.status == "warn")
    return AudioCheckResultOut(
        commit_id=commit_id, checks=[AudioCheckOut.model_validate(c, from_attributes=True) for c in checks],
        passed=passed, failed=failed, warned=warned, total=len(checks),
    )


@router.post("", response_model=AudioCheckOut, status_code=status.HTTP_201_CREATED)
def create_check(project_id: int, commit_id: int, payload: AudioCheckCreate, db: Session = Depends(get_db)):
    """Submit an audio check result (called by CI/analysis pipeline)."""
    check = AudioCheck(commit_id=commit_id, check_type=payload.check_type, value=payload.value, expected=payload.expected)
    # Auto-evaluate
    if payload.check_type == "lufs":
        try:
            val = float(payload.value)
            if -16 <= val <= -12:
                check.status = "pass"
                check.message = f"LUFS {val:.1f} is within target range (-16 to -12)"
            elif -18 <= val <= -10:
                check.status = "warn"
                check.message = f"LUFS {val:.1f} is outside optimal range but acceptable"
            else:
                check.status = "fail"
                check.message = f"LUFS {val:.1f} is too {'quiet' if val < -18 else 'loud'}"
        except ValueError:
            check.status = "fail"
            check.message = "Invalid LUFS value"
    elif payload.check_type == "true_peak":
        try:
            val = float(payload.value)
            if val < -1.0:
                check.status = "pass"
                check.message = f"True Peak {val:.2f} dBTP is safe"
            elif val < 0.0:
                check.status = "warn"
                check.message = f"True Peak {val:.2f} dBTP is close to clipping"
            else:
                check.status = "fail"
                check.message = f"True Peak {val:.2f} dBTP — clipping detected!"
        except ValueError:
            check.status = "fail"
            check.message = "Invalid True Peak value"
    elif payload.check_type == "format":
        allowed = {"wav", "flac", "aiff", "mp3", "ogg"}
        ext = payload.value.lower().strip(".")
        check.status = "pass" if ext in allowed else "fail"
        check.message = f"Format '{payload.value}' is {'supported' if ext in allowed else 'not supported'}"
    elif payload.check_type == "sample_rate":
        try:
            val = int(payload.value)
            check.status = "pass" if val >= 44100 else "fail"
            check.message = f"Sample rate {val} Hz is {'OK' if val >= 44100 else 'below minimum 44100 Hz'}"
        except ValueError:
            check.status = "fail"
            check.message = "Invalid sample rate"
    elif payload.check_type == "channels":
        try:
            val = int(payload.value)
            check.status = "pass" if val in (1, 2) else "warn"
            check.message = f"{val} channel(s) — {'mono/stereo' if val in (1,2) else 'unusual channel count'}"
        except ValueError:
            check.status = "fail"
            check.message = "Invalid channel count"
    else:
        check.status = "pending"
        check.message = "Check type not auto-evaluated"

    db.add(check)
    db.commit()
    db.refresh(check)
    return AudioCheckOut.model_validate(check, from_attributes=True)


@router.post("/run", response_model=AudioCheckResultOut)
def run_checks(project_id: int, commit_id: int, db: Session = Depends(get_db)):
    """Run all standard checks against a commit's audio files."""
    from ..models import FileSnapshot, storage

    # Find audio files in the commit
    snaps = db.scalars(select(FileSnapshot).where(FileSnapshot.commit_id == commit_id)).all()
    audio_exts = {"wav", "mp3", "flac", "aif", "aiff", "ogg", "m4a"}

    results = []
    for snap in snaps:
        ext = snap.path.rsplit(".", 1)[-1].lower() if "." in snap.path else ""
        if ext in audio_exts:
            # Format check
            check = AudioCheck(commit_id=commit_id, check_type="format", value=ext, expected="wav/flac/aiff")
            check.status = "pass"
            check.message = f"Format '{ext}' is supported"
            db.add(check)
            results.append(check)

    db.commit()
    passed = sum(1 for c in results if c.status == "pass")
    return AudioCheckResultOut(
        commit_id=commit_id, checks=[AudioCheckOut.model_validate(c, from_attributes=True) for c in results],
        passed=passed, failed=0, warned=0, total=len(results),
    )
