"""Python symbol parser using tree-sitter."""

from __future__ import annotations

import logging
from typing import Optional

import tree_sitter_python as tspython
from tree_sitter import Language, Parser as TSParser, Node

from .base import Parser, Symbol

log = logging.getLogger(__name__)

PY_LANGUAGE = Language(tspython.language())


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _get_docstring(body_node: Node, source: bytes) -> Optional[str]:
    """Return the first expression_statement string literal in a body, if any."""
    for child in body_node.children:
        if child.type == "expression_statement":
            inner = child.children[0] if child.children else None
            if inner and inner.type == "string":
                raw = _node_text(inner, source).strip()
                # Strip surrounding quotes
                for q in ('"""', "'''", '"', "'"):
                    if raw.startswith(q) and raw.endswith(q) and len(raw) > 2 * len(q):
                        return raw[len(q):-len(q)].strip()
                    elif raw.startswith(q) and raw.endswith(q):
                        return raw[len(q):-len(q)].strip()
            break
        elif child.type not in ("comment", "\n"):
            break
    return None


def _get_name(node: Node, source: bytes) -> Optional[str]:
    for child in node.children:
        if child.type == "identifier":
            return _node_text(child, source)
    return None


def _get_params(node: Node, source: bytes) -> Optional[str]:
    for child in node.children:
        if child.type == "parameters":
            return _node_text(child, source)
    return None


class PythonParser(Parser):
    def __init__(self):
        self._parser = TSParser(PY_LANGUAGE)

    def parse(self, source: bytes, filepath: str) -> list[Symbol]:
        try:
            tree = self._parser.parse(source)
            symbols: list[Symbol] = []
            self._visit(tree.root_node, source, symbols, parent_name=None)
            return symbols
        except Exception as exc:
            log.error("python_parser: error parsing %s: %s", filepath, exc)
            return []

    def _visit(self, node: Node, source: bytes, symbols: list[Symbol], parent_name: Optional[str]):
        if node.type == "function_definition":
            name = _get_name(node, source)
            params = _get_params(node, source)
            body = next((c for c in node.children if c.type == "block"), None)
            doc = _get_docstring(body, source) if body else None
            kind = "method" if parent_name else "function"
            sig = f"def {name}{params}" if name and params else None
            if name:
                symbols.append(Symbol(
                    name=name,
                    kind=kind,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=sig,
                    docstring=doc,
                    parent_name=parent_name,
                ))
            # recurse into body for nested functions/classes — keep parent_name
            if body:
                for child in body.children:
                    self._visit(child, source, symbols, parent_name=name if node.type == "class_definition" else parent_name)

        elif node.type == "class_definition":
            name = _get_name(node, source)
            body = next((c for c in node.children if c.type == "block"), None)
            doc = _get_docstring(body, source) if body else None
            if name:
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"class {name}",
                    docstring=doc,
                    parent_name=parent_name,
                ))
                if body:
                    for child in body.children:
                        self._visit(child, source, symbols, parent_name=name)
            return  # already recursed

        elif node.type in ("import_statement", "import_from_statement"):
            text = _node_text(node, source).strip()
            symbols.append(Symbol(
                name=text[:120],
                kind="import",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=text[:120],
            ))

        else:
            for child in node.children:
                self._visit(child, source, symbols, parent_name=parent_name)
