"""Structural search with tree-sitter queries over indexed files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from tree_sitter import Language, Parser, Query, QueryCursor

from .filters import (
    DEFAULT_QUERY_LIMIT,
    matches_path,
    path_filter_spec,
    validate_languages,
    validate_paging,
    validate_path_filter,
)
from .store import Store

STRUCTURE_KINDS: tuple[str, ...] = ("function", "method", "class", "import")

LanguageLoader = Callable[[], Language]

_LANGUAGE_LOADERS: dict[str, LanguageLoader] = {}


def _register_language(name: str, loader: LanguageLoader) -> None:
    _LANGUAGE_LOADERS[name] = loader


def _load_python() -> Language:
    import tree_sitter_python as tsp
    return Language(tsp.language())


def _load_javascript() -> Language:
    import tree_sitter_javascript as tsjs
    return Language(tsjs.language())


def _load_typescript() -> Language:
    import tree_sitter_typescript as tsts
    return Language(tsts.language_typescript())


def _load_tsx() -> Language:
    import tree_sitter_typescript as tsts
    return Language(tsts.language_tsx())


def _load_rust() -> Language:
    import tree_sitter_rust as tsr
    return Language(tsr.language())


def _load_go() -> Language:
    import tree_sitter_go as tsg
    return Language(tsg.language())


def _load_java() -> Language:
    import tree_sitter_java as tsj
    return Language(tsj.language())


def _load_c() -> Language:
    import tree_sitter_c as tsc
    return Language(tsc.language())


def _load_cpp() -> Language:
    import tree_sitter_cpp as tscpp
    return Language(tscpp.language())


def _load_csharp() -> Language:
    import tree_sitter_c_sharp as tscs
    return Language(tscs.language())


def _load_kotlin() -> Language:
    import tree_sitter_kotlin as tsk
    return Language(tsk.language())


def _load_swift() -> Language:
    import tree_sitter_swift as tss
    return Language(tss.language())


_register_language("python", _load_python)
_register_language("javascript", _load_javascript)
_register_language("typescript", _load_typescript)
_register_language("tsx", _load_tsx)
_register_language("rust", _load_rust)
_register_language("go", _load_go)
_register_language("java", _load_java)
_register_language("c", _load_c)
_register_language("cpp", _load_cpp)
_register_language("csharp", _load_csharp)
_register_language("kotlin", _load_kotlin)
_register_language("swift", _load_swift)

# kind → language → tree-sitter query (@name when available, else @node)
_QUERIES: dict[str, dict[str, str]] = {
    "function": {
        "python": "(function_definition name: (identifier) @name)",
        "javascript": "(function_declaration name: (identifier) @name)",
        "typescript": "(function_declaration name: (identifier) @name)",
        "tsx": "(function_declaration name: (identifier) @name)",
        "rust": "(function_item name: (identifier) @name)",
        "go": "(function_declaration name: (identifier) @name)",
        "java": "(method_declaration name: (identifier) @name)",
        "c": "(function_definition declarator: (function_declarator declarator: (identifier) @name))",
        "cpp": "(function_definition declarator: (function_declarator declarator: (identifier) @name))",
        "csharp": "(method_declaration name: (identifier) @name)",
        "kotlin": "(function_declaration (simple_identifier) @name)",
        "swift": "(function_declaration simple_identifier: (simple_identifier) @name)",
    },
    "method": {
        "python": "(class_definition body: (block (function_definition name: (identifier) @name)))",
        "javascript": "(method_definition name: (property_identifier) @name)",
        "typescript": "(method_definition name: (property_identifier) @name)",
        "tsx": "(method_definition name: (property_identifier) @name)",
        "rust": "(impl_item body: (declaration_list (function_item name: (identifier) @name)))",
        "go": "(method_declaration name: (field_identifier) @name)",
        "java": "(method_declaration name: (identifier) @name)",
        "cpp": "(function_definition declarator: (function_declarator declarator: (field_identifier) @name))",
        "csharp": "(method_declaration name: (identifier) @name)",
        "kotlin": "(class_declaration (function_declaration (simple_identifier) @name))",
        "swift": "(class_declaration (function_declaration simple_identifier: (simple_identifier) @name))",
    },
    "class": {
        "python": "(class_definition name: (identifier) @name)",
        "javascript": "(class_declaration name: (identifier) @name)",
        "typescript": "(class_declaration name: (identifier) @name)",
        "tsx": "(class_declaration name: (identifier) @name)",
        "rust": "(struct_item name: (type_identifier) @name)",
        "go": "(type_declaration (type_spec name: (type_identifier) @name))",
        "java": "(class_declaration name: (identifier) @name)",
        "c": "(struct_specifier name: (type_identifier) @name)",
        "cpp": "(class_specifier name: (type_identifier) @name)",
        "csharp": "(class_declaration name: (identifier) @name)",
        "kotlin": "(class_declaration (type_identifier) @name)",
        "swift": "(class_declaration type_identifier: (type_identifier) @name)",
    },
    "import": {
        "python": "(import_statement) @node",
        "javascript": "(import_statement) @node",
        "typescript": "(import_statement) @node",
        "tsx": "(import_statement) @node",
        "rust": "(use_declaration) @node",
        "go": "(import_declaration) @node",
        "java": "(import_declaration) @node",
        "c": "(preproc_include) @node",
        "cpp": "(preproc_include) @node",
        "csharp": "(using_directive) @node",
        "kotlin": "(import_header) @node",
        "swift": "(import_declaration) @node",
    },
}

_PARSER_CACHE: dict[str, Parser] = {}
_QUERY_CACHE: dict[tuple[str, str], Query] = {}


class StructureError(ValueError):
    """Invalid structural search request."""


@dataclass(frozen=True)
class StructureMatch:
    path: str
    language: str
    kind: str
    node_type: str
    name: Optional[str]
    line_start: int
    line_end: int
    preview: str


def validate_structure_kind(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized not in STRUCTURE_KINDS:
        allowed = ", ".join(STRUCTURE_KINDS)
        raise StructureError(f"unknown kind {kind!r}; expected one of: {allowed}")
    return normalized


def _node_text(node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _preview(node, source: bytes) -> str:
    text = _node_text(node, source)
    first = text.splitlines()[0] if text else ""
    return first[:120]


def _ancestor_types(node) -> set[str]:
    types: set[str] = set()
    current = node.parent
    while current is not None:
        types.add(current.type)
        current = current.parent
    return types


def _include_match(language: str, kind: str, node) -> bool:
    if kind == "function" and language == "python":
        return "class_definition" not in _ancestor_types(node)
    if kind == "method" and language == "python":
        return "class_definition" in _ancestor_types(node)
    return True


def _parser_for(language: str) -> Parser:
    if language not in _PARSER_CACHE:
        loader = _LANGUAGE_LOADERS[language]
        _PARSER_CACHE[language] = Parser(loader())
    return _PARSER_CACHE[language]


def _query_for(language: str, kind: str) -> Optional[Query]:
    query_text = _QUERIES[kind].get(language)
    if query_text is None:
        return None
    key = (language, kind)
    if key not in _QUERY_CACHE:
        _QUERY_CACHE[key] = Query(_LANGUAGE_LOADERS[language](), query_text)
    return _QUERY_CACHE[key]


def _match_file(
    *,
    root: Path,
    rel_path: str,
    language: str,
    kind: str,
    source: bytes,
) -> list[StructureMatch]:
    query = _query_for(language, kind)
    if query is None:
        return []

    parser = _parser_for(language)
    tree = parser.parse(source)
    cursor = QueryCursor(query)
    matches: list[StructureMatch] = []

    for _pattern_index, captures in cursor.matches(tree.root_node):
        name_nodes = captures.get("name")
        node_nodes = captures.get("node")
        if name_nodes:
            node = name_nodes[0]
            name = _node_text(node, source)
        elif node_nodes:
            node = node_nodes[0]
            name = None
        else:
            continue

        if not _include_match(language, kind, node):
            continue

        matches.append(
            StructureMatch(
                path=rel_path,
                language=language,
                kind=kind,
                node_type=node.type,
                name=name,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                preview=_preview(node, source),
            )
        )

    return matches


def search_structure(
    root: Path,
    store: Store,
    kind: str,
    *,
    path: Optional[str] = None,
    languages: Sequence[str] = (),
    offset: int = 0,
    limit: int = DEFAULT_QUERY_LIMIT,
) -> list[StructureMatch]:
    """Run a structural query over indexed files."""
    normalized_kind = validate_structure_kind(kind)
    path_pat = validate_path_filter(path)
    langs = validate_languages(languages)
    validate_paging(offset=offset, limit=limit)

    path_spec = path_filter_spec(path_pat) if path_pat is not None else None
    lang_set = set(langs) if langs else None

    collected: list[StructureMatch] = []
    root_resolved = root.resolve()

    for row in store.all_files():
        rel_path = row["path"]
        language = row["language"]
        if language is None:
            continue
        if lang_set is not None and language.lower() not in lang_set:
            continue
        if path_spec is not None and not matches_path(rel_path, path_spec):
            continue
        if language not in _LANGUAGE_LOADERS:
            continue
        if language not in _QUERIES[normalized_kind]:
            continue

        file_path = root_resolved / rel_path
        if not file_path.is_file():
            continue

        source = file_path.read_bytes()
        collected.extend(
            _match_file(
                root=root_resolved,
                rel_path=rel_path,
                language=language,
                kind=normalized_kind,
                source=source,
            )
        )

    collected.sort(key=lambda m: (m.path, m.line_start, m.name or ""))
    return collected[offset : offset + limit]
