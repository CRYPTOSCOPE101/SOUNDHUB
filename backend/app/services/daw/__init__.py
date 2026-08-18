"""DAW file parsing and diff engine."""


def is_daw_path(path: str) -> bool:
    """Check if a file path is a supported DAW project file."""
    daw_exts = {".als", ".cpr", ".rpp", ".flp"}
    lower = path.lower()
    return any(lower.endswith(ext) for ext in daw_exts)
