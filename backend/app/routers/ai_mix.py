"""AI Mix Assistant — analyze audio and get mixing suggestions."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.ai_mix import MixSuggestion, full_analysis

router = APIRouter(prefix="/api/ai", tags=["ai mix assistant"])


class MixSuggestionOut(BaseModel):
    category: str
    severity: str
    title: str
    description: str
    action: str
    db_value: float | None = None


class MixAnalysisOut(BaseModel):
    filename: str
    suggestions: list[MixSuggestionOut]
    score: int
    grade: str
    critical_count: int
    warning_count: int


class AnalyzeRequest(BaseModel):
    filename: str = "master.wav"
    lufs: float | None = None
    true_peak: float | None = None
    sample_rate: int | None = None
    channels: int | None = None


@router.post("/analyze", response_model=MixAnalysisOut)
def analyze_audio(payload: AnalyzeRequest, user: User = Depends(get_current_user)):
    """Analyze audio metadata and get mixing suggestions.

    Provide any combination of:
      - lufs: Integrated LUFS loudness
      - true_peak: True peak in dBTP
      - sample_rate: Sample rate in Hz
      - channels: Number of channels

    Returns suggestions, quality score (0-100), and letter grade (A+-F).
    """
    analysis = full_analysis(
        filename=payload.filename,
        lufs=payload.lufs,
        true_peak=payload.true_peak,
        sample_rate=payload.sample_rate,
        channels=payload.channels,
    )
    return MixAnalysisOut(
        filename=analysis.filename,
        suggestions=[
            MixSuggestionOut(
                category=s.category, severity=s.severity,
                title=s.title, description=s.description,
                action=s.action, db_value=s.db_value,
            ) for s in analysis.suggestions
        ],
        score=analysis.score,
        grade=analysis.grade,
        critical_count=analysis.critical_count,
        warning_count=analysis.warning_count,
    )


@router.get("/quick-check")
def quick_check(
    lufs: float = Query(..., description="Integrated LUFS"),
    true_peak: float = Query(..., description="True peak dBTP"),
    filename: str = Query("master.wav"),
):
    """Quick audio quality check — no auth required.

    Returns pass/warn/fail status and suggestions.
    """
    analysis = full_analysis(filename=filename, lufs=lufs, true_peak=true_peak)
    return {
        "status": "pass" if analysis.critical_count == 0 else "fail",
        "score": analysis.score,
        "grade": analysis.grade,
        "suggestions": [
            {"title": s.title, "severity": s.severity, "action": s.action}
            for s in analysis.suggestions
        ],
    }


@router.get("/presets")
def get_presets():
    """Get recommended loudness targets for different platforms."""
    return {
        "platforms": [
            {"name": "Spotify", "lufs": -14, "true_peak": -1.0, "notes": "Normalizes to -14 LUFS"},
            {"name": "Apple Music", "lufs": -16, "true_peak": -1.0, "notes": "Sound Check normalizes to -16"},
            {"name": "YouTube", "lufs": -14, "true_peak": -1.0, "notes": "Normalizes to -14 LUFS"},
            {"name": "Tidal", "lufs": -14, "true_peak": -1.0, "notes": "Normalizes to -14 LUFS"},
            {"name": "Bandcamp", "lufs": -14, "true_peak": -1.0, "notes": "No normalization, -14 is safe"},
            {"name": "CD Master", "lufs": -9, "true_peak": -0.3, "notes": "Traditional CD loudness"},
            {"name": "Vinyl Master", "lufs": -12, "true_peak": -0.5, "notes": "Softer for vinyl cutting"},
            {"name": "Club/DJ", "lufs": -8, "true_peak": -0.5, "notes": "Louder for club play"},
            {"name": "Podcast", "lufs": -16, "true_peak": -1.0, "notes": "EBU R128 standard"},
        ],
        "default": {"lufs": -14, "true_peak": -1.0},
    }
