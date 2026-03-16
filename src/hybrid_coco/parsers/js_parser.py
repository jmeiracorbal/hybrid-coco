"""JavaScript/TypeScript symbol parser using tree-sitter."""

from __future__ import annotations

import logging
from typing import Optional

from tree_sitter import Language, Parser as TSParser, Node

from .base import Parser, Symbol

log = logging.getLogger(__name__)


def _get_js_language(lang: str):
    if lang == "typescript":
        import tree_sitter_typescript as tsts
        return Language(tsts.language_typescript())
    elif lang == "tsx":
        import tree_sitter_typescript as tsts
        return Language(tsts.language_tsx())
    else:
        import tree_sitter_javascript as tsjs
        return Language(tsjs.language())


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _get_name_child(node: Node, source: bytes) -> Optional[str]:
    for child in node.children:
        if child.type in ("identifier", "property_identifier"):
            return _node_text(child, source)
    return None


class JSParser(Parser):
    def __init__(self, lang: str = "javascript"):
        self._lang_name = lang
        self._language = _get_js_language(lang)
        self._parser = TSParser(self._language)

    def parse(self, source: bytes, filepath: str) -> list[Symbol]:
        try:
            tree = self._parser.parse(source)
            symbols: list[Symbol] = []
            self._visit(tree.root_node, source, symbols, parent_name=None)
            return symbols
        except Exception as exc:
            log.error("js_parser: error parsing %s: %s", filepath, exc)
            return []

    def _visit(self, node: Node, source: bytes, symbols: list[Symbol], parent_name: Optional[str]):
        if node.type == "function_declaration":
            name = _get_name_child(node, source)
            if name:
                kind = "method" if parent_name else "function"
                symbols.append(Symbol(
                    name=name,
                    kind=kind,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"function {name}()",
                    parent_name=parent_name,
                ))

        elif node.type == "class_declaration":
            name = _get_name_child(node, source)
            if name:
                symbols.append(Symbol(
                    name=name,
                    kind="class",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"class {name}",
                    parent_name=parent_name,
                ))
                body = next((c for c in node.children if c.type == "class_body"), None)
                if body:
                    for child in body.children:
                        self._visit(child, source, symbols, parent_name=name)
                return

        elif node.type == "method_definition":
            name = _get_name_child(node, source)
            if name:
                symbols.append(Symbol(
                    name=name,
                    kind="method",
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=f"{name}()",
                    parent_name=parent_name,
                ))

        elif node.type == "import_statement":
            text = _node_text(node, source).strip()
            symbols.append(Symbol(
                name=text[:120],
                kind="import",
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=text[:120],
            ))

        elif node.type == "lexical_declaration":
            # const foo = () => ... or const foo = function ...
            for child in node.children:
                if child.type == "variable_declarator":
                    var_name = _get_name_child(child, source)
                    # check if it has an arrow_function or function_expression value
                    val = next((c for c in child.children if c.type in ("arrow_function", "function_expression")), None)
                    if var_name and val:
                        kind = "method" if parent_name else "function"
                        symbols.append(Symbol(
                            name=var_name,
                            kind=kind,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            signature=f"const {var_name} = () => ...",
                            parent_name=parent_name,
                        ))

        for child in node.children:
            if node.type not in ("class_declaration",):  # already handled class body
                self._visit(child, source, symbols, parent_name=parent_name)
