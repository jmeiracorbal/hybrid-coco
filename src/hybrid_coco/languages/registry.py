"""Single source of truth for language detection, parsers, and structure queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from tree_sitter import Language

if TYPE_CHECKING:
    from hybrid_coco.parsers.base import Parser

LanguageLoader = Callable[[], Language]
ParserFactory = Callable[[], "Parser"]


@dataclass(frozen=True)
class LanguageSpec:
    name: str
    extensions: tuple[str, ...]
    load_ts: LanguageLoader
    parser_factory: ParserFactory
    structure_queries: dict[str, str] = field(default_factory=dict)


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


def _python_parser() -> Parser:
    from hybrid_coco.parsers.python_parser import PythonParser
    return PythonParser()


def _javascript_parser() -> Parser:
    from hybrid_coco.parsers.js_parser import JSParser
    return JSParser("javascript")


def _typescript_parser() -> Parser:
    from hybrid_coco.parsers.js_parser import JSParser
    return JSParser("typescript")


def _tsx_parser() -> Parser:
    from hybrid_coco.parsers.js_parser import JSParser
    return JSParser("tsx")


def _rust_parser() -> Parser:
    from hybrid_coco.parsers.rust_parser import RustParser
    return RustParser()


def _go_parser() -> Parser:
    from hybrid_coco.parsers.go_parser import GoParser
    return GoParser()


def _java_parser() -> Parser:
    from hybrid_coco.parsers.java_parser import JavaParser
    return JavaParser()


def _c_parser() -> Parser:
    from hybrid_coco.parsers.c_parser import CFamilyParser
    return CFamilyParser("c")


def _cpp_parser() -> Parser:
    from hybrid_coco.parsers.c_parser import CFamilyParser
    return CFamilyParser("cpp")


def _csharp_parser() -> Parser:
    from hybrid_coco.parsers.csharp_parser import CSharpParser
    return CSharpParser()


def _kotlin_parser() -> Parser:
    from hybrid_coco.parsers.kotlin_parser import KotlinParser
    return KotlinParser()


def _swift_parser() -> Parser:
    from hybrid_coco.parsers.swift_parser import SwiftParser
    return SwiftParser()


LANGUAGE_SPECS: tuple[LanguageSpec, ...] = (
    LanguageSpec(
        name="python",
        extensions=(".py",),
        load_ts=_load_python,
        parser_factory=_python_parser,
        structure_queries={
            "function": "(function_definition name: (identifier) @name)",
            "method": "(class_definition body: (block (function_definition name: (identifier) @name)))",
            "class": "(class_definition name: (identifier) @name)",
            "import": "(import_statement) @node",
        },
    ),
    LanguageSpec(
        name="javascript",
        extensions=(".js", ".jsx"),
        load_ts=_load_javascript,
        parser_factory=_javascript_parser,
        structure_queries={
            "function": "(function_declaration name: (identifier) @name)",
            "method": "(method_definition name: (property_identifier) @name)",
            "class": "(class_declaration name: (identifier) @name)",
            "import": "(import_statement) @node",
        },
    ),
    LanguageSpec(
        name="typescript",
        extensions=(".ts",),
        load_ts=_load_typescript,
        parser_factory=_typescript_parser,
        structure_queries={
            "function": "(function_declaration name: (identifier) @name)",
            "method": "(method_definition name: (property_identifier) @name)",
            "class": "(class_declaration name: (identifier) @name)",
            "import": "(import_statement) @node",
        },
    ),
    LanguageSpec(
        name="tsx",
        extensions=(".tsx",),
        load_ts=_load_tsx,
        parser_factory=_tsx_parser,
        structure_queries={
            "function": "(function_declaration name: (identifier) @name)",
            "method": "(method_definition name: (property_identifier) @name)",
            "class": "(class_declaration name: (identifier) @name)",
            "import": "(import_statement) @node",
        },
    ),
    LanguageSpec(
        name="rust",
        extensions=(".rs",),
        load_ts=_load_rust,
        parser_factory=_rust_parser,
        structure_queries={
            "function": "(function_item name: (identifier) @name)",
            "method": "(impl_item body: (declaration_list (function_item name: (identifier) @name)))",
            "class": "(struct_item name: (type_identifier) @name)",
            "import": "(use_declaration) @node",
        },
    ),
    LanguageSpec(
        name="go",
        extensions=(".go",),
        load_ts=_load_go,
        parser_factory=_go_parser,
        structure_queries={
            "function": "(function_declaration name: (identifier) @name)",
            "method": "(method_declaration name: (field_identifier) @name)",
            "class": "(type_declaration (type_spec name: (type_identifier) @name))",
            "import": "(import_declaration) @node",
        },
    ),
    LanguageSpec(
        name="java",
        extensions=(".java",),
        load_ts=_load_java,
        parser_factory=_java_parser,
        structure_queries={
            "function": "(method_declaration name: (identifier) @name)",
            "method": "(method_declaration name: (identifier) @name)",
            "class": "(class_declaration name: (identifier) @name)",
            "import": "(import_declaration) @node",
        },
    ),
    LanguageSpec(
        name="c",
        extensions=(".c", ".h"),
        load_ts=_load_c,
        parser_factory=_c_parser,
        structure_queries={
            "function": "(function_definition declarator: (function_declarator declarator: (identifier) @name))",
            "method": "(function_definition declarator: (function_declarator declarator: (identifier) @name))",
            "class": "(struct_specifier name: (type_identifier) @name)",
            "import": "(preproc_include) @node",
        },
    ),
    LanguageSpec(
        name="cpp",
        extensions=(".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"),
        load_ts=_load_cpp,
        parser_factory=_cpp_parser,
        structure_queries={
            "function": "(function_definition declarator: (function_declarator declarator: (identifier) @name))",
            "method": "(function_definition declarator: (function_declarator declarator: (field_identifier) @name))",
            "class": "(class_specifier name: (type_identifier) @name)",
            "import": "(preproc_include) @node",
        },
    ),
    LanguageSpec(
        name="csharp",
        extensions=(".cs",),
        load_ts=_load_csharp,
        parser_factory=_csharp_parser,
        structure_queries={
            "function": "(method_declaration name: (identifier) @name)",
            "method": "(method_declaration name: (identifier) @name)",
            "class": "(class_declaration name: (identifier) @name)",
            "import": "(using_directive) @node",
        },
    ),
    LanguageSpec(
        name="kotlin",
        extensions=(".kt", ".kts"),
        load_ts=_load_kotlin,
        parser_factory=_kotlin_parser,
        structure_queries={
            "function": "(function_declaration (simple_identifier) @name)",
            "method": "(class_declaration (function_declaration (simple_identifier) @name))",
            "class": "(class_declaration (type_identifier) @name)",
            "import": "(import_header) @node",
        },
    ),
    LanguageSpec(
        name="swift",
        extensions=(".swift",),
        load_ts=_load_swift,
        parser_factory=_swift_parser,
        structure_queries={
            "function": "(function_declaration simple_identifier: (simple_identifier) @name)",
            "method": "(class_declaration (function_declaration simple_identifier: (simple_identifier) @name))",
            "class": "(class_declaration type_identifier: (type_identifier) @name)",
            "import": "(import_declaration) @node",
        },
    ),
)

_SPECS_BY_NAME: dict[str, LanguageSpec] = {spec.name: spec for spec in LANGUAGE_SPECS}

EXTENSION_MAP: dict[str, str] = {}
for _spec in LANGUAGE_SPECS:
    for _ext in _spec.extensions:
        EXTENSION_MAP[_ext] = _spec.name

KNOWN_LANGUAGES: frozenset[str] = frozenset(_SPECS_BY_NAME)


def get_language_spec(name: str) -> LanguageSpec | None:
    return _SPECS_BY_NAME.get(name)


def detect_language(path: str | Path) -> Optional[str]:
    suffix = Path(path).suffix.lower()
    return EXTENSION_MAP.get(suffix)


def load_tree_sitter(language: str) -> Language:
    spec = get_language_spec(language)
    if spec is None:
        raise KeyError(f"unknown language: {language}")
    return spec.load_ts()


def get_structure_query(language: str, kind: str) -> Optional[str]:
    spec = get_language_spec(language)
    if spec is None:
        return None
    return spec.structure_queries.get(kind)


def create_parser(language: str) -> Optional[Parser]:
    spec = get_language_spec(language)
    if spec is None:
        return None
    return spec.parser_factory()
