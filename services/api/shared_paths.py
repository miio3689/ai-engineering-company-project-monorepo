"""Import-path helpers for the shared Python package in the monorepo."""

from pathlib import Path
import sys


def ensure_shared_python_path(repository_root: Path | None = None) -> Path:
    """Add the repository and shared Python package roots to ``sys.path``."""
    root = (
        Path(repository_root).resolve()
        if repository_root is not None
        else Path(__file__).resolve().parents[2]
    )
    for path in (root, root / "packages" / "shared" / "python"):
        path_string = str(path)
        if path_string not in sys.path:
            sys.path.insert(0, path_string)
    return root
