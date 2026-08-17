"""Java symbol parser using tree-sitter."""

from __future__ import annotations

import logging
from typing import Optional

import tree_sitter_java as tsjava
from tree_sitter import Language, Node, Parser as TSParser

from .base import Parser, Symbol
from .ts_utils import child_of_type, node_text, preceding_block_javadoc

log = logging.getLogger(__name__)

JAVA_LANGUAGE = Language(tsjava.language())


def _method_signature(node: Node, source: bytes) -> Optional[str]:
    parts: list[str] = []
    for child in node.children:
        if child.type in ("block", "constructor_body"):
            break
        parts.append(node_text(child, source))
    text = " ".join(parts).strip()
    return text[:200] if text else None


class JavaParser(Parser):
    def __init__(self):
        self._parser = TSParser(JAVA_LANGUAGE)

    def parse(self, source: bytes, filepath: str) -> list[Symbol]:
        try:
            tree = self._parser.parse(source)
            symbols: list[Symbol] = []
            self._visit(tree.root_node, source, symbols, parent_name=None)
            return symbols
        except Exception as exc:
            log.error("java_parser: error parsing %s: %s", filepath, exc)
            return []

    def _visit(
        self,
        node: Node,
        source: bytes,
        symbols: list[Symbol],
        parent_name: Optional[str],
    ):
        if node.type in ("class_declaration", "interface_declaration", "enum_declaration"):
            name_node = child_of_type(node, "identifier")
            if name_node is not None:
                name = node_text(name_node, source)
                kind_word = {
                    "class_declaration": "class",
                    "interface_declaration": "interface",
                    "enum_declaration": "enum",
                }[node.type]
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"{kind_word} {name}",
                    docstring=preceding_block_javadoc(node, source),
                    parent_name=parent_name,
                ))
                body = child_of_type(node, "class_body") or child_of_type(
                    node, "interface_body"
                ) or child_of_type(node, "enum_body")
                if body is not None:
                    for child in body.children:
                        self._visit(child, source, symbols, parent_name=name)
                return

        elif node.type in ("method_declaration", "constructor_declaration"):
            name_node = child_of_type(node, "identifier")
            if name_node is not None:
                name = node_text(name_node, source)
                kind = "method" if parent_name else "function"
                symbols.append(Symbol(
                    name=name,
                    kind=kind,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=_method_signature(node, source),
                    docstring=preceding_block_javadoc(node, source),
                    parent_name=parent_name,
                ))
            return

        elif node.type == "import_declaration":
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
