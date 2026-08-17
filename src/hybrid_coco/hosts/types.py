"""result returned by an agent host installer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HostResult:
    name: str
    title: str
    lines: list[str]
    skills: list[str]
