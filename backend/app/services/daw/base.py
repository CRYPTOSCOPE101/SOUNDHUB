"""DAW format data model and parser interface."""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class TrackInfo:
    name: str
    kind: str = "audio"  # audio | midi | group | return | master
    devices: list[str] = field(default_factory=list)


@dataclass
class DAWInfo:
    """Structured view of a DAW project file."""

    format: str  # display name, e.g. "Ableton Live"
    format_key: str  # "als" | "cpr" | "rpp" | "flp"
    version: str = ""
    bpm: float | None = None
    time_signature: str | None = None
    tracks: list[TrackInfo] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def plugin_set(self) -> list[str]:
        return sorted(set(self.plugins))

    def summary_text(self) -> str:
        """Normalized textual form used for line-level diffing."""
        lines: list[str] = []
        lines.append(f"FORMAT: {self.format} ({self.version})")
        if self.bpm is not None:
            lines.append(f"BPM: {self.bpm:g}")
        if self.time_signature:
            lines.append(f"TIME_SIGNATURE: {self.time_signature}")
        for t in self.tracks:
            devs = ", ".join(t.devices) if t.devices else "-"
            lines.append(f"TRACK: {t.name} [{t.kind}] devices={devs}")
        for p in self.plugin_set:
            lines.append(f"PLUGIN: {p}")
        for s in sorted(set(self.samples)):
            lines.append(f"SAMPLE: {s}")
        for k, v in sorted(self.extra.items()):
            lines.append(f"META: {k}={v}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "format": self.format,
            "format_key": self.format_key,
            "version": self.version,
            "bpm": self.bpm,
            "time_signature": self.time_signature,
            "tracks": [
                {"name": t.name, "kind": t.kind, "devices": t.devices} for t in self.tracks
            ],
            "plugins": self.plugin_set,
            "samples": sorted(set(self.samples)),
            "extra": self.extra,
        }


Parser = Callable[[bytes], DAWInfo]


class ParseError(Exception):
    """Raised when a file can't be parsed as the expected format."""
