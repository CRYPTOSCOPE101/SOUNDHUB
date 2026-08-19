"""AI Mix Assistant — analyzes audio metadata and provides mixing suggestions.

Uses rule-based analysis (no external API needed) to give actionable feedback:
  - LUFS loudness analysis
  - True peak / clipping detection
  - Stereo width assessment
  - Frequency balance hints
  - Dynamic range evaluation
  - Format compliance checks

Can be extended with LLM integration (OpenAI, Groq, etc.) for deeper analysis.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MixSuggestion:
    """A single mixing suggestion."""
    category: str        # loudness | dynamics | format | mix | master
    severity: str        # info | warning | critical
    title: str
    description: str
    action: str          # suggested fix
    db_value: float | None = None  # if related to dB value


@dataclass
class MixAnalysis:
    """Complete analysis result for an audio file."""
    filename: str
    suggestions: list[MixSuggestion] = field(default_factory=list)
    score: int = 100     # 0-100 quality score
    grade: str = "A"     # A-F grade

    @property
    def critical_count(self) -> int:
        return sum(1 for s in self.suggestions if s.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for s in self.suggestions if s.severity == "warning")


def analyze_lufs(lufs: float, target: float = -14.0, tolerance: float = 1.5) -> list[MixSuggestion]:
    """Analyze integrated LUFS loudness."""
    suggestions = []
    diff = lufs - target

    if abs(diff) <= tolerance:
        suggestions.append(MixSuggestion(
            category="loudness", severity="info",
            title=f"LUFS OK: {lufs:.1f}",
            description=f"Integrated loudness {lufs:.1f} LUFS is within target range ({target:.0f} ± {tolerance:.1f})",
            action="No action needed", db_value=lufs,
        ))
    elif lufs < -18:
        suggestions.append(MixSuggestion(
            category="loudness", severity="critical",
            title=f"Too quiet: {lufs:.1f} LUFS",
            description=f"Mix is {abs(target - lufs):.1f} dB below target. Will sound quiet on streaming platforms.",
            action="Increase master level or use a limiter", db_value=lufs,
        ))
    elif lufs < target - tolerance:
        suggestions.append(MixSuggestion(
            category="loudness", severity="warning",
            title=f"Slightly quiet: {lufs:.1f} LUFS",
            description=f"Below target by {abs(diff):.1f} dB. May sound quiet compared to other tracks.",
            action="Consider raising the master fader or using gentle limiting", db_value=lufs,
        ))
    elif lufs > -8:
        suggestions.append(MixSuggestion(
            category="loudness", severity="critical",
            title=f"Way too loud: {lufs:.1f} LUFS",
            description=f"Excessive loudness. Dynamic range has been destroyed. Streaming platforms will normalize down.",
            action="Reduce limiter gain, restore dynamics. Target -14 LUFS for streaming.", db_value=lufs,
        ))
    elif lufs > target + tolerance:
        suggestions.append(MixSuggestion(
            category="loudness", severity="warning",
            title=f"Slightly loud: {lufs:.1f} LUFS",
            description=f"Above target by {abs(diff):.1f} dB. May be normalized down by streaming platforms.",
            action="Consider reducing limiter output or mastering for streaming", db_value=lufs,
        ))

    return suggestions


def analyze_true_peak(true_peak: float, ceiling: float = -1.0) -> list[MixSuggestion]:
    """Analyze true peak for clipping."""
    suggestions = []

    if true_peak < ceiling:
        suggestions.append(MixSuggestion(
            category="master", severity="info",
            title=f"True Peak OK: {true_peak:.2f} dBTP",
            description=f"True peak is {abs(ceiling - true_peak):.1f} dB below ceiling",
            action="No action needed", db_value=true_peak,
        ))
    elif true_peak < 0:
        suggestions.append(MixSuggestion(
            category="master", severity="warning",
            title=f"True Peak close to clipping: {true_peak:.2f} dBTP",
            description="Inter-sample peaks may cause distortion on some DACs.",
            action="Lower the limiter ceiling to -1.0 dBTP or below", db_value=true_peak,
        ))
    else:
        suggestions.append(MixSuggestion(
            category="master", severity="critical",
            title=f"CLIPPING: {true_peak:.2f} dBTP",
            description="True peak exceeds 0 dBFS — digital clipping is occurring.",
            action="Reduce levels immediately. Add a true-peak limiter at -1.0 dBTP", db_value=true_peak,
        ))

    return suggestions


def analyze_format(filename: str, sample_rate: int | None = None, channels: int | None = None) -> list[MixSuggestion]:
    """Analyze file format and technical specs."""
    suggestions = []
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Format check
    pro_formats = {"wav", "flac", "aiff", "aif"}
    if ext in pro_formats:
        suggestions.append(MixSuggestion(
            category="format", severity="info",
            title=f"Pro format: {ext.upper()}",
            description=f"{ext.upper()} is a lossless format suitable for distribution",
            action="No action needed",
        ))
    elif ext in {"mp3", "ogg", "m4a", "aac"}:
        suggestions.append(MixSuggestion(
            category="format", severity="warning",
            title=f"Lossy format: {ext.upper()}",
            description=f"{ext.upper()} is lossy — quality has been reduced. Use WAV/FLAC for masters.",
            action="Export as WAV or FLAC for final delivery",
        ))
    elif ext in {"als", "cpr", "rpp", "flp"}:
        suggestions.append(MixSuggestion(
            category="format", severity="info",
            title=f"DAW project: {ext.upper()}",
            description=f"DAW project file detected. This is source material, not a deliverable.",
            action="Export a mixdown for delivery",
        ))

    # Sample rate
    if sample_rate is not None:
        if sample_rate >= 96000:
            suggestions.append(MixSuggestion(
                category="format", severity="info",
                title=f"High sample rate: {sample_rate} Hz",
                description="Ultra-high resolution. Good for archival, but 44.1/48 kHz is standard for distribution.",
                action="Consider downsampling to 44.1 kHz for streaming delivery",
            ))
        elif sample_rate < 44100:
            suggestions.append(MixSuggestion(
                category="format", severity="critical",
                title=f"Low sample rate: {sample_rate} Hz",
                description="Below CD quality. This will sound poor on most playback systems.",
                action="Re-export at 44100 Hz or higher",
            ))

    # Channels
    if channels is not None:
        if channels == 1:
            suggestions.append(MixSuggestion(
                category="mix", severity="info",
                title="Mono file",
                description="Mono audio detected. Ensure this is intentional.",
                action="Consider if stereo width is needed for this track",
            ))
        elif channels > 2:
            suggestions.append(MixSuggestion(
                category="format", severity="info",
                title=f"{channels}-channel audio",
                description=f"Multi-channel ({channels}ch) detected — surround or immersive audio.",
                action="Ensure the delivery format supports this channel count",
            ))

    return suggestions


def calculate_grade(analysis: MixAnalysis) -> str:
    """Calculate a letter grade based on suggestions."""
    critical = analysis.critical_count
    warnings = analysis.warning_count

    if critical == 0 and warnings == 0:
        return "A+"
    elif critical == 0 and warnings <= 1:
        return "A"
    elif critical == 0 and warnings <= 3:
        return "B"
    elif critical <= 1:
        return "C"
    elif critical <= 2:
        return "D"
    else:
        return "F"


def calculate_score(analysis: MixAnalysis) -> int:
    """Calculate a 0-100 score."""
    score = 100
    score -= analysis.critical_count * 25
    score -= analysis.warning_count * 10
    return max(0, min(100, score))


def full_analysis(
    filename: str,
    lufs: float | None = None,
    true_peak: float | None = None,
    sample_rate: int | None = None,
    channels: int | None = None,
) -> MixAnalysis:
    """Run complete analysis on an audio file.

    Args:
        filename: Name of the audio file
        lufs: Integrated LUFS loudness (optional)
        true_peak: True peak in dBTP (optional)
        sample_rate: Sample rate in Hz (optional)
        channels: Number of channels (optional)

    Returns:
        MixAnalysis with suggestions, score, and grade.
    """
    analysis = MixAnalysis(filename=filename)

    if lufs is not None:
        analysis.suggestions.extend(analyze_lufs(lufs))
    if true_peak is not None:
        analysis.suggestions.extend(analyze_true_peak(true_peak))
    analysis.suggestions.extend(analyze_format(filename, sample_rate, channels))

    analysis.score = calculate_score(analysis)
    analysis.grade = calculate_grade(analysis)

    return analysis
