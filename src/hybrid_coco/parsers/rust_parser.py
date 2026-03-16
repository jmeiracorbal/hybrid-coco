"""Rust symbol parser using tree-sitter."""

from __future__ import annotations

import logging
from typing import Optional

import tree_sitter_rust as tsrust
from tree_sitter import Language, Parser as TSParser, Node

from .base import Parser, Symbol

log = logging.getLogger(__name__)

RUST_LANGUAGE = Language(tsrust.language())


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _get_identifier(node: Node, source: bytes) -> Optional[str]:
    for child in node.children:
        if child.type == "identifier":
            return _node_text(child, source)
    return None


def _get_type_identifier(node: Node, source: bytes) -> Optional[str]:
    for child in node.children:
        if child.type == "type_identifier":
            return _node_text(child, source)
    return None


def _get_doc_comments(node: Node, source: bytes) -> Optional[str]:
    """Collect /// doc comments that appear immediately before this node (no gap)."""
    parent = node.parent
    if parent is None:
        return None
    # Collect all siblings in order, then find those directly before this node
    siblings = list(parent.children)
    idx = next((i for i, c in enumerate(siblings) if c == node), None)
    if idx is None:
        return None
    docs = []
    # Walk backwards from idx-1 collecting contiguous doc comments
    for sibling in reversed(siblings[:idx]):
        if sibling.type == "line_comment":
            text = _node_text(sibling, source)
            if text.startswith("///"):
                docs.insert(0, text[3:].strip())
                continue
        # Any non-doc-comment breaks the chain
        break
    return " ".join(docs) if docs else None


def _get_function_signature(node: Node, source: bytes) -> Optional[str]:
    """Build a compact function signature (up to the body)."""
    parts = []
    for child in node.children:
        if child.type == "block":
            break
        parts.append(_node_text(child, source))
    return " ".join(parts).strip() if parts else None


class RustParser(Parser):
    def __init__(self):
        self._parser = TSParser(RUST_LANGUAGE)

    def parse(self, source: bytes, filepath: str) -> list[Symbol]:
        try:
            tree = self._parser.parse(source)
            symbols: list[Symbol] = []
            self._visit(tree.root_node, source, symbols, parent_name=None)
            return symbols
        except Exception as exc:
            log.error("rust_parser: error parsing %s: %s", filepath, exc)
            return []

    def _visit(self, node: Node, source: bytes, symbols: list[Symbol], parent_name: Optional[str]):
        if node.type == "function_item":
            name = _get_identifier(node, source)
            sig = _get_function_signature(node, source)
            doc = _get_doc_comments(node, source)
            kind = "method" if parent_name else "function"
            if name:
                symbols.append(Symbol(
                    name=name,
                    kind=kind,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=sig[:200] if sig else None,
                    docstring=doc,
                    parent_name=parent_name,
                ))

        elif node.type in ("struct_item", "enum_item"):
            name = _get_type_identifier(node, source)
            doc = _get_doc_comments(node, source)
            kind_word = "struct" if node.type == "struct_item" else "enum"
            if name:
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"{kind_word} {name}",
                    docstring=doc,
                    parent_name=parent_name,
                ))

        elif node.type == "impl_item":
            # Get the type being implemented
            impl_type = _get_type_identifier(node, source)
            body = next((c for c in node.children if c.type == "declaration_list"), None)
            if body:
                for child in body.children:
                    self._visit(child, source, symbols, parent_name=impl_type)
            return  # handled children already

        elif node.type == "use_declaration":
            text = _node_text(node, source).strip()
            symbols.append(Symbol(
                name=text[:120],
                kind="import",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=text[:120],
            ))

        for child in node.children:
            if node.type != "impl_item":  # impl_item already handled
                self._visit(child, source, symbols, parent_name=parent_name)
