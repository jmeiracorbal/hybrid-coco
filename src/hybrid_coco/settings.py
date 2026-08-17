"""Project settings loaded from `.hybrid-coco/config.toml`."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .config import HC_DIR, SETTINGS_FILE
from .parsers import KNOWN_LANGUAGES

REQUIRED_KEYS = ("include", "exclude", "languages")

DEFAULT_CONFIG = """\
include = []
exclude = []
languages = {}
"""


class SettingsError(ValueError):
    """Invalid or incomplete project settings file."""


@dataclass(frozen=True)
class ProjectSettings:
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    languages: Mapping[str, str]


def settings_path(root: Path) -> Path:
    return root / HC_DIR / SETTINGS_FILE


def _require_string_list(data: dict, key: str, origin: Path) -> tuple[str, ...]:
    if key not in data:
        raise SettingsError(f"{origin}: missing required key {key!r}")
    value = data[key]
    if not isinstance(value, list):
        raise SettingsError(f"{origin}: {key} must be an array of strings")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise SettingsError(f"{origin}: {key} entries must be non-empty strings")
        cleaned.append(item)
    return tuple(cleaned)


def _require_languages(data: dict, origin: Path) -> dict[str, str]:
    if "languages" not in data:
        raise SettingsError(f"{origin}: missing required key 'languages'")
    value = data["languages"]
    if not isinstance(value, dict):
        raise SettingsError(f"{origin}: languages must be a table of extension = language")
    mapping: dict[str, str] = {}
    for ext, lang in value.items():
        if not isinstance(ext, str) or not ext.startswith(".") or ext == ".":
            raise SettingsError(
                f"{origin}: language keys must be extensions starting with '.' (got {ext!r})"
            )
        if not isinstance(lang, str) or not lang.strip():
            raise SettingsError(f"{origin}: language value for {ext!r} must be a non-empty string")
        normalized_ext = ext.lower()
        normalized_lang = lang.strip().lower()
        if normalized_lang not in KNOWN_LANGUAGES:
            known = ", ".join(sorted(KNOWN_LANGUAGES))
            raise SettingsError(
                f"{origin}: unknown language {lang!r} for {ext}; known: {known}"
            )
        mapping[normalized_ext] = normalized_lang
    return mapping


def ensure_settings(root: Path) -> bool:
    """Write the default config.toml when it is missing. Returns True if created."""
    path = settings_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        return False
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return True


def load_or_create_settings(root: Path) -> tuple[ProjectSettings, bool]:
    """Create the default config if missing, then load it.

    Does not overwrite an existing file, even if that file is invalid.
    Returns (settings, created).
    """
    created = ensure_settings(root)
    return load_settings(root), created


def load_settings(root: Path) -> ProjectSettings:
    """Return project settings. The file must exist and contain every required key."""
    path = settings_path(root)
    if not path.is_file():
        raise SettingsError(f"{path}: missing — run: hc init {root}")

    try:
        raw = path.read_text(encoding="utf-8")
        data = tomllib.loads(raw)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SettingsError(f"{path}: {exc}") from exc

    extra = set(data.keys()) - set(REQUIRED_KEYS)
    if extra:
        names = ", ".join(sorted(extra))
        raise SettingsError(f"{path}: unknown keys: {names}")

    include = _require_string_list(data, "include", path)
    exclude = _require_string_list(data, "exclude", path)
    languages = _require_languages(data, path)
    return ProjectSettings(include=include, exclude=exclude, languages=languages)
