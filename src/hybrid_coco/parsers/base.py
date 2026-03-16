"""Base types for symbol parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Symbol:
    name: str
    kind: str  # function | method | class | import | variable
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent_name: Optional[str] = None  # for methods: name of enclosing class


class Parser(ABC):
    """Abstract base class for language-specific parsers."""

    @abstractmethod
    def parse(self, source: bytes, filepath: str) -> list[Symbol]:
        """Parse source bytes and return a list of extracted symbols."""
        ...
