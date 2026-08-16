"""Go symbol parser using tree-sitter."""

from __future__ import annotations

import logging
from typing import Optional

import tree_sitter_go as tsgo
from tree_sitter import Language, Node, Parser as TSParser

from .base import Parser, Symbol

log = logging.getLogger(__name__)

GO_LANGUAGE = Language(tsgo.language())


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _child_of_type(node: Node, typ: str) -> Optional[Node]:
    for child in node.children:
        if child.type == typ:
            return child
    return None


def _preceding_line_docs(node: Node, source: bytes) -> Optional[str]:
    parent = node.parent
    if parent is None:
        return None
    siblings = list(parent.children)
    idx = next((i for i, c in enumerate(siblings) if c.id == node.id), None)
    if idx is None:
        return None
    docs: list[str] = []
    for sibling in reversed(siblings[:idx]):
        if sibling.type == "comment":
            text = _node_text(sibling, source).strip()
            if text.startswith("//"):
                docs.insert(0, text[2:].strip())
                continue
        break
    return " ".join(docs) if docs else None


def _receiver_type(node: Node, source: bytes) -> Optional[str]:
    """Extract type name from method receiver parameter list."""
    params = _child_of_type(node, "parameter_list")
    if params is None:
        return None
    for child in params.children:
        if child.type != "parameter_declaration":
            continue
        for part in child.children:
            if part.type == "type_identifier":
                return _node_text(part, source)
            if part.type == "pointer_type":
                ident = _child_of_type(part, "type_identifier")
                if ident is not None:
                    return _node_text(ident, source)
    return None


def _sig_until_block(node: Node, source: bytes) -> Optional[str]:
    parts: list[str] = []
    for child in node.children:
        if child.type == "block":
            break
        parts.append(_node_text(child, source))
    text = " ".join(parts).strip()
    return text[:200] if text else None


class GoParser(Parser):
    def __init__(self):
        self._parser = TSParser(GO_LANGUAGE)

    def parse(self, source: bytes, filepath: str) -> list[Symbol]:
        try:
            tree = self._parser.parse(source)
            symbols: list[Symbol] = []
            self._visit(tree.root_node, source, symbols)
            return symbols
        except Exception as exc:
            log.error("go_parser: error parsing %s: %s", filepath, exc)
            return []

    def _visit(self, node: Node, source: bytes, symbols: list[Symbol]):
        if node.type == "function_declaration":
            name_node = _child_of_type(node, "identifier")
            if name_node is not None:
                name = _node_text(name_node, source)
                symbols.append(Symbol(
                    name=name,
                    kind="function",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=_sig_until_block(node, source),
                    docstring=_preceding_line_docs(node, source),
                ))

        elif node.type == "method_declaration":
            name_node = _child_of_type(node, "field_identifier")
            if name_node is not None:
                name = _node_text(name_node, source)
                parent = _receiver_type(node, source)
                symbols.append(Symbol(
                    name=name,
                    kind="method",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=_sig_until_block(node, source),
                    docstring=_preceding_line_docs(node, source),
                    parent_name=parent,
                ))

        elif node.type == "type_declaration":
            for child in node.children:
                if child.type != "type_spec":
                    continue
                type_id = _child_of_type(child, "type_identifier")
                if type_id is None:
                    continue
                name = _node_text(type_id, source)
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line_start=child.start_point[0] + 1,
                    line_end=child.end_point[0] + 1,
                    signature=f"type {name}",
                    docstring=_preceding_line_docs(node, source),
                ))

        elif node.type == "import_declaration":
            text = _node_text(node, source).strip()
            symbols.append(Symbol(
                name=text[:120],
                kind="import",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=text[:120],
            ))

        for child in node.children:
            self._visit(child, source, symbols)
