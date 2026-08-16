"""C / C++ symbol parser using tree-sitter."""

from __future__ import annotations

import logging
from typing import Optional

import tree_sitter_c as tsc
import tree_sitter_cpp as tscpp
from tree_sitter import Language, Node, Parser as TSParser

from .base import Parser, Symbol

log = logging.getLogger(__name__)

_C_LANGUAGE = Language(tsc.language())
_CPP_LANGUAGE = Language(tscpp.language())


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _child_of_type(node: Node, typ: str) -> Optional[Node]:
    for child in node.children:
        if child.type == typ:
            return child
    return None


def _find_descendant(node: Node, typ: str) -> Optional[Node]:
    if node.type == typ:
        return node
    for child in node.children:
        found = _find_descendant(child, typ)
        if found is not None:
            return found
    return None


def _preceding_comment(node: Node, source: bytes) -> Optional[str]:
    parent = node.parent
    if parent is None:
        return None
    siblings = list(parent.children)
    idx = next((i for i, c in enumerate(siblings) if c.id == node.id), None)
    if idx is None or idx == 0:
        return None
    prev = siblings[idx - 1]
    if prev.type != "comment":
        return None
    text = _node_text(prev, source).strip()
    if text.startswith("/*") and text.endswith("*/"):
        return text[2:-2].strip()
    if text.startswith("//"):
        return text[2:].strip()
    return None


def _function_name(declarator: Node, source: bytes) -> Optional[str]:
    """Name of a function_declarator (not parameter identifiers)."""
    for child in declarator.children:
        if child.type in ("identifier", "field_identifier"):
            return _node_text(child, source)
        if child.type == "qualified_identifier":
            idents = [
                c for c in child.children
                if c.type in ("identifier", "field_identifier")
            ]
            if idents:
                return _node_text(idents[-1], source)
    return None


def _qualified_parent(declarator: Node, source: bytes) -> Optional[str]:
    """For out-of-line C++ defs like Greeter::greet, return Greeter."""
    for child in declarator.children:
        if child.type != "qualified_identifier":
            continue
        ns = _child_of_type(child, "namespace_identifier")
        if ns is not None:
            return _node_text(ns, source)
    return None


def _sig_until_body(node: Node, source: bytes) -> Optional[str]:
    parts: list[str] = []
    for child in node.children:
        if child.type in ("compound_statement", "field_declaration_list"):
            break
        parts.append(_node_text(child, source))
    text = " ".join(parts).strip().rstrip(";")
    return text[:200] if text else None


class CFamilyParser(Parser):
    def __init__(self, lang: str):
        if lang == "c":
            self._parser = TSParser(_C_LANGUAGE)
        elif lang == "cpp":
            self._parser = TSParser(_CPP_LANGUAGE)
        else:
            raise ValueError(f"unsupported c-family language: {lang}")
        self._lang = lang

    def parse(self, source: bytes, filepath: str) -> list[Symbol]:
        try:
            tree = self._parser.parse(source)
            symbols: list[Symbol] = []
            self._visit(tree.root_node, source, symbols, parent_name=None)
            return symbols
        except Exception as exc:
            log.error("%s_parser: error parsing %s: %s", self._lang, filepath, exc)
            return []

    def _visit(
        self,
        node: Node,
        source: bytes,
        symbols: list[Symbol],
        parent_name: Optional[str],
    ):
        if node.type == "function_definition":
            declarator = _find_descendant(node, "function_declarator")
            if declarator is not None:
                name = _function_name(declarator, source)
                parent = _qualified_parent(declarator, source) or parent_name
                if name is not None:
                    symbols.append(Symbol(
                        name=name,
                        kind="method" if parent else "function",
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=_sig_until_body(node, source),
                        docstring=_preceding_comment(node, source),
                        parent_name=parent,
                    ))

        elif node.type == "field_declaration":
            declarator = _child_of_type(node, "function_declarator")
            if declarator is not None and parent_name is not None:
                name = _function_name(declarator, source)
                if name is not None:
                    symbols.append(Symbol(
                        name=name,
                        kind="method",
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=_sig_until_body(node, source),
                        docstring=_preceding_comment(node, source),
                        parent_name=parent_name,
                    ))
                return

        elif node.type in ("struct_specifier", "class_specifier", "enum_specifier"):
            type_id = _child_of_type(node, "type_identifier")
            body = _child_of_type(node, "field_declaration_list")
            if type_id is not None:
                name = _node_text(type_id, source)
                kind_word = {
                    "struct_specifier": "struct",
                    "class_specifier": "class",
                    "enum_specifier": "enum",
                }[node.type]
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"{kind_word} {name}",
                    docstring=_preceding_comment(node, source),
                    parent_name=parent_name,
                ))
                if body is not None:
                    for child in body.children:
                        self._visit(child, source, symbols, parent_name=name)
                return

        elif node.type == "preproc_include":
            text = _node_text(node, source).strip()
            symbols.append(Symbol(
                name=text[:120],
                kind="import",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=text[:120],
            ))
            return

        elif node.type == "namespace_definition":
            body = _child_of_type(node, "declaration_list")
            if body is not None:
                for child in body.children:
                    self._visit(child, source, symbols, parent_name=parent_name)
                return

        for child in node.children:
            self._visit(child, source, symbols, parent_name=parent_name)
