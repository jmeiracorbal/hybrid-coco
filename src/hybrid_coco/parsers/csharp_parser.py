"""C# symbol parser using tree-sitter."""

from __future__ import annotations

import logging
from typing import Optional

import tree_sitter_c_sharp as tscsharp
from tree_sitter import Language, Node, Parser as TSParser

from .base import Parser, Symbol

log = logging.getLogger(__name__)

CSHARP_LANGUAGE = Language(tscsharp.language())

_TYPE_DECLS = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "struct_declaration": "struct",
    "record_declaration": "record",
    "enum_declaration": "enum",
}


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _child_of_type(node: Node, typ: str) -> Optional[Node]:
    for child in node.children:
        if child.type == typ:
            return child
    return None


def _preceding_doc_comments(node: Node, source: bytes) -> Optional[str]:
    parent = node.parent
    if parent is None:
        return None
    siblings = list(parent.children)
    idx = next((i for i, c in enumerate(siblings) if c.id == node.id), None)
    if idx is None:
        return None
    docs: list[str] = []
    for sibling in reversed(siblings[:idx]):
        if sibling.type != "comment":
            break
        text = _node_text(sibling, source).strip()
        if text.startswith("///"):
            docs.insert(0, text[3:].strip())
            continue
        break
    if not docs:
        return None
    joined = " ".join(docs)
    # strip simple <summary>...</summary> wrappers when present
    if "<summary>" in joined and "</summary>" in joined:
        start = joined.find("<summary>") + len("<summary>")
        end = joined.find("</summary>")
        if end > start:
            return joined[start:end].strip()
    return joined


def _sig_until_body(node: Node, source: bytes) -> Optional[str]:
    parts: list[str] = []
    for child in node.children:
        if child.type in ("block", "arrow_expression_clause", "declaration_list",
                          "enum_member_declaration_list", "accessor_list"):
            break
        if child.type == ";":
            break
        parts.append(_node_text(child, source))
    text = " ".join(parts).strip()
    return text[:200] if text else None


class CSharpParser(Parser):
    def __init__(self):
        self._parser = TSParser(CSHARP_LANGUAGE)

    def parse(self, source: bytes, filepath: str) -> list[Symbol]:
        try:
            tree = self._parser.parse(source)
            symbols: list[Symbol] = []
            self._visit(tree.root_node, source, symbols, parent_name=None)
            return symbols
        except Exception as exc:
            log.error("csharp_parser: error parsing %s: %s", filepath, exc)
            return []

    def _visit(
        self,
        node: Node,
        source: bytes,
        symbols: list[Symbol],
        parent_name: Optional[str],
    ):
        if node.type in _TYPE_DECLS:
            name_node = _child_of_type(node, "identifier")
            if name_node is not None:
                name = _node_text(name_node, source)
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"{_TYPE_DECLS[node.type]} {name}",
                    docstring=_preceding_doc_comments(node, source),
                    parent_name=parent_name,
                ))
                body = (
                    _child_of_type(node, "declaration_list")
                    or _child_of_type(node, "enum_member_declaration_list")
                )
                if body is not None:
                    for child in body.children:
                        self._visit(child, source, symbols, parent_name=name)
                return

        if node.type in ("method_declaration", "constructor_declaration"):
            name_node = _child_of_type(node, "identifier")
            if name_node is not None:
                name = _node_text(name_node, source)
                kind = "method" if parent_name else "function"
                symbols.append(Symbol(
                    name=name,
                    kind=kind,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=_sig_until_body(node, source),
                    docstring=_preceding_doc_comments(node, source),
                    parent_name=parent_name,
                ))
            return

        if node.type == "using_directive":
            text = _node_text(node, source).strip()
            symbols.append(Symbol(
                name=text[:120],
                kind="import",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=text[:120],
            ))
            return

        if node.type == "namespace_declaration":
            body = _child_of_type(node, "declaration_list")
            if body is not None:
                for child in body.children:
                    self._visit(child, source, symbols, parent_name=parent_name)
                return

        for child in node.children:
            self._visit(child, source, symbols, parent_name=parent_name)
