from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JOBS = DATA / "jobs"
SAMPLES = DATA / "samples"


def safe_child(root: Path, name: str) -> Path:
    """Resolve a relative path and prevent traversal, including Windows drives."""
    from pathlib import PureWindowsPath
    candidate = Path(name)
    windows = PureWindowsPath(name)
    if candidate.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError("Absolute paths are not allowed")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("Path is outside the allowed directory") from exc
    return resolved
