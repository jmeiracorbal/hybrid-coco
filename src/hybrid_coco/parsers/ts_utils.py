"""Shared tree-sitter node helpers for symbol parsers."""

from __future__ import annotations

from typing import Optional

from tree_sitter import Node


def node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def child_of_type(node: Node, typ: str) -> Optional[Node]:
    for child in node.children:
        if child.type == typ:
            return child
    return None


def find_descendant(node: Node, typ: str) -> Optional[Node]:
    if node.type == typ:
        return node
    for child in node.children:
        found = find_descendant(child, typ)
        if found is not None:
            return found
    return None


def _sibling_index(node: Node) -> tuple[list[Node], int] | None:
    parent = node.parent
    if parent is None:
        return None
    siblings = list(parent.children)
    idx = next((i for i, c in enumerate(siblings) if c.id == node.id), None)
    if idx is None:
        return None
    return siblings, idx


def preceding_block_javadoc(node: Node, source: bytes) -> Optional[str]:
    located = _sibling_index(node)
    if located is None:
        return None
    siblings, idx = located
    if idx == 0:
        return None
    prev = siblings[idx - 1]
    if prev.type != "block_comment":
        return None
    text = node_text(prev, source).strip()
    if text.startswith("/**") and text.endswith("*/"):
        return text[3:-2].strip()
    return None


def preceding_immediate_comment(node: Node, source: bytes) -> Optional[str]:
    located = _sibling_index(node)
    if located is None:
        return None
    siblings, idx = located
    if idx == 0:
        return None
    prev = siblings[idx - 1]
    if prev.type != "comment":
        return None
    text = node_text(prev, source).strip()
    if text.startswith("/*") and text.endswith("*/"):
        return text[2:-2].strip()
    if text.startswith("//"):
        return text[2:].strip()
    return None


def preceding_prefix_line_comments(
    node: Node,
    source: bytes,
    *,
    comment_type: str,
    prefix: str,
) -> Optional[str]:
    located = _sibling_index(node)
    if located is None:
        return None
    siblings, idx = located
    docs: list[str] = []
    for sibling in reversed(siblings[:idx]):
        if sibling.type != comment_type:
            break
        text = node_text(sibling, source).strip()
        if text.startswith(prefix):
            docs.insert(0, text[len(prefix) :].strip())
            continue
        break
    return " ".join(docs) if docs else None


def preceding_triple_slash_comments(
    node: Node,
    source: bytes,
    *,
    strip_summary: bool = False,
) -> Optional[str]:
    located = _sibling_index(node)
    if located is None:
        return None
    siblings, idx = located
    docs: list[str] = []
    for sibling in reversed(siblings[:idx]):
        if sibling.type != "comment":
            break
        text = node_text(sibling, source).strip()
        if text.startswith("///"):
            docs.insert(0, text[3:].strip())
            continue
        break
    if not docs:
        return None
    joined = " ".join(docs)
    if strip_summary and "<summary>" in joined and "</summary>" in joined:
        start = joined.find("<summary>") + len("<summary>")
        end = joined.find("</summary>")
        if end > start:
            return joined[start:end].strip()
    return joined
