"""Swift symbol parser using tree-sitter."""

from __future__ import annotations

import logging
from typing import Optional

import tree_sitter_swift as tsswift
from tree_sitter import Language, Node, Parser as TSParser

from .base import Parser, Symbol
from .ts_utils import child_of_type, node_text, preceding_triple_slash_comments

log = logging.getLogger(__name__)

SWIFT_LANGUAGE = Language(tsswift.language())

_BODY_TYPES = frozenset({
    "function_body",
    "class_body",
    "enum_class_body",
    "protocol_body",
})


def _field_name_text(node: Node, source: bytes) -> Optional[str]:
    name = node.child_by_field_name("name")
    if name is None:
        return None
    if name.type == "type_identifier" or name.type == "simple_identifier":
        return node_text(name, source)
    if name.type == "user_type":
        nested = child_of_type(name, "type_identifier")
        if nested is not None:
            return node_text(nested, source)
        return node_text(name, source)
    # init keyword, etc.
    return node_text(name, source)


def _type_kind_word(node: Node) -> str:
    kind = node.child_by_field_name("declaration_kind")
    if kind is not None:
        return kind.type
    for child in node.children:
        if child.type in ("class", "struct", "enum", "actor", "extension", "protocol"):
            return child.type
    return "class"


def _sig_until_body(node: Node, source: bytes) -> Optional[str]:
    parts: list[str] = []
    for child in node.children:
        if child.type in _BODY_TYPES:
            break
        parts.append(node_text(child, source))
    text = " ".join(parts).strip()
    return text[:200] if text else None


class SwiftParser(Parser):
    def __init__(self):
        self._parser = TSParser(SWIFT_LANGUAGE)

    def parse(self, source: bytes, filepath: str) -> list[Symbol]:
        try:
            tree = self._parser.parse(source)
            symbols: list[Symbol] = []
            self._visit(tree.root_node, source, symbols, parent_name=None)
            return symbols
        except Exception as exc:
            log.error("swift_parser: error parsing %s: %s", filepath, exc)
            return []

    def _visit(
        self,
        node: Node,
        source: bytes,
        symbols: list[Symbol],
        parent_name: Optional[str],
    ):
        if node.type == "class_declaration":
            kind_word = _type_kind_word(node)
            name = _field_name_text(node, source)
            # extension Greeter { ... } — methods belong to Greeter
            if kind_word == "extension":
                body = node.child_by_field_name("body") or child_of_type(node, "class_body")
                if body is not None and name is not None:
                    for child in body.children:
                        self._visit(child, source, symbols, parent_name=name)
                return
            if name is not None:
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"{kind_word} {name}",
                    docstring=preceding_triple_slash_comments(node, source),
                    parent_name=parent_name,
                ))
                body = node.child_by_field_name("body") or (
                    child_of_type(node, "class_body")
                    or child_of_type(node, "enum_class_body")
                )
                if body is not None:
                    for child in body.children:
                        self._visit(child, source, symbols, parent_name=name)
                return

        if node.type == "protocol_declaration":
            name = _field_name_text(node, source)
            if name is not None:
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"protocol {name}",
                    docstring=preceding_triple_slash_comments(node, source),
                    parent_name=parent_name,
                ))
                body = node.child_by_field_name("body") or child_of_type(node, "protocol_body")
                if body is not None:
                    for child in body.children:
                        self._visit(child, source, symbols, parent_name=name)
                return

        if node.type in ("function_declaration", "protocol_function_declaration"):
            name = _field_name_text(node, source)
            if name is not None:
                kind = "method" if parent_name else "function"
                symbols.append(Symbol(
                    name=name,
                    kind=kind,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=_sig_until_body(node, source),
                    docstring=preceding_triple_slash_comments(node, source),
                    parent_name=parent_name,
                ))
            return

        if node.type == "init_declaration":
            symbols.append(Symbol(
                name="init",
                kind="method" if parent_name else "function",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=_sig_until_body(node, source),
                docstring=preceding_triple_slash_comments(node, source),
                parent_name=parent_name,
            ))
            return

        if node.type == "import_declaration":
            text = node_text(node, source).strip()
            symbols.append(Symbol(
                name=text[:120],
                kind="import",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=text[:120],
            ))
            return

        for child in node.children:
            self._visit(child, source, symbols, parent_name=parent_name)
