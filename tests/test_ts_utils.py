"""Unit tests for shared tree-sitter helpers."""

from __future__ import annotations

import textwrap

import tree_sitter_c as tsc
import tree_sitter_c_sharp as tscs
import tree_sitter_go as tsg
import tree_sitter_java as tsj
import tree_sitter_python as tsp
from tree_sitter import Language, Parser

from hybrid_coco.parsers.ts_utils import (
    child_of_type,
    find_descendant,
    node_text,
    preceding_block_javadoc,
    preceding_immediate_comment,
    preceding_prefix_line_comments,
    preceding_triple_slash_comments,
)


def test_node_text_and_child_of_type():
    source = b"class Greeter:\n    pass\n"
    tree = Parser(Language(tsp.language())).parse(source)
    cls = child_of_type(tree.root_node, "class_definition")
    name = child_of_type(cls, "identifier")
    assert node_text(name, source) == "Greeter"


def test_find_descendant():
    source = b"def outer():\n    def inner():\n        pass\n"
    tree = Parser(Language(tsp.language())).parse(source)
    fn = find_descendant(tree.root_node, "function_definition")
    assert node_text(child_of_type(fn, "identifier"), source) == "outer"


def test_preceding_block_javadoc():
    source = textwrap.dedent("""\
        /** Greets people. */
        public class Greeter {}
    """).encode()
    tree = Parser(Language(tsj.language())).parse(source)
    cls = child_of_type(tree.root_node, "class_declaration")
    assert preceding_block_javadoc(cls, source) == "Greets people."


def test_preceding_prefix_line_comments():
    source = b"// does work\nfunc Work() {}\n"
    tree = Parser(Language(tsg.language())).parse(source)
    fn = child_of_type(tree.root_node, "function_declaration")
    assert (
        preceding_prefix_line_comments(fn, source, comment_type="comment", prefix="//")
        == "does work"
    )


def test_preceding_triple_slash_csharp_summary():
    source = b"/// <summary> greets </summary>\nclass Greeter {}\n"
    tree = Parser(Language(tscs.language())).parse(source)
    cls = child_of_type(tree.root_node, "class_declaration")
    assert preceding_triple_slash_comments(cls, source, strip_summary=True) == "greets"


def test_preceding_immediate_comment():
    source = b"/* adds */ int add(int a, int b) { return a + b; }\n"
    tree = Parser(Language(tsc.language())).parse(source)
    fn = child_of_type(tree.root_node, "function_definition")
    assert preceding_immediate_comment(fn, source) == "adds"
