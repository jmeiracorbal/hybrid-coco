"""Configuration and path helpers for hybrid-coco."""

from pathlib import Path

HC_DIR = ".hybrid-coco"
INDEX_FILE = "index.db"

ALWAYS_IGNORE = {
    ".git",
    "node_modules",
    "__pycache__",
    ".hybrid-coco",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",  # Rust build artifacts
}


def get_index_path(root: Path) -> Path:
    """Return the path to the index DB for the given project root."""
    return root / HC_DIR / INDEX_FILE


def ensure_index_dir(root: Path) -> Path:
    """Ensure .hybrid-coco/ directory exists and return index path."""
    hc_dir = root / HC_DIR
    hc_dir.mkdir(exist_ok=True)
    return hc_dir / INDEX_FILE
