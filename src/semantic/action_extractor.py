from __future__ import annotations

import ast
from ast import NodeVisitor

from .models import Action

BOILERPLATE: set[str] = {
    "append",
    "extend",
    "insert",
    "remove",
    "pop",
    "keys",
    "values",
    "items",
    "get",
    "setdefault",
    "update",
    "clear",
    "copy",
    "len",
    "str",
    "repr",
    "print",
    "debug",
    "info",
    "warning",
    "error",
    "exception",
}


class _CallCollector(NodeVisitor):
    """ callcollector."""
    def __init__(self) -> None:
        """Initialise _CallCollector."""
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:
        """    Visit call.

    Args:
        node (ast.Call): Node.
    """
        self.calls.append(node)
        self.generic_visit(node)


class SemanticActionExtractor:
    """Semanticactionextractor."""
    def extract(self, body: str) -> list[Action]:
        """    Extract.

    Args:
        body (str): Body.

    Returns:
        list[Action]: Description.
    """
        try:
            tree = ast.parse(body)
        except SyntaxError:
            return []
        calls = self._collect_calls(tree)
        return self._build_actions(calls)

    def _collect_calls(self, tree: ast.AST) -> list[str]:
        """     collect calls.

    Args:
        tree (ast.AST): Tree.

    Returns:
        list[str]: Description.
    """
        collector = _CallCollector()
        collector.visit(tree)
        names: list[str] = []
        for call_node in collector.calls:
            name = self._call_name(call_node.func)
            if name and name not in BOILERPLATE:
                names.append(name)
        return names

    def _call_name(self, func: ast.expr) -> str | None:
        """     call name.

    Args:
        func (ast.expr): Func.

    Returns:
        str | None: Description.
    """
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return self._traverse_attribute(func)
        return None

    def _traverse_attribute(self, node: ast.Attribute) -> str:
        """     traverse attribute.

    Args:
        node (ast.Attribute): Node.

    Returns:
        str: Description.
    """
        parts: list[str] = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        return parts[0]

    def _build_actions(self, calls: list[str]) -> list[Action]:
        """     build actions.

    Args:
        calls (list[str]): Calls.

    Returns:
        list[Action]: Description.
    """
        seen: list[str] = []
        for call in calls:
            if seen and call == seen[-1]:
                continue
            seen.append(call)

        candidates: list[tuple[Action, int]] = []
        for i, call in enumerate(seen):
            verb, obj = self._split_call(call)
            confidence = self._score(verb, obj)
            candidates.append((
                Action(
                    verb=verb,
                    obj=obj,
                    source=call,
                    confidence=confidence,
                ),
                i,
            ))

        candidates.sort(key=lambda t: (-t[0].confidence, t[1]))
        top = candidates[:5]
        top.sort(key=lambda t: t[1])
        return [a for a, _ in top]

    def _split_call(self, call: str) -> tuple[str, str | None]:
        """     split call.

    Args:
        call (str): Call.

    Returns:
        tuple[str, str | None]: Description.
    """
        parts = call.split("_")
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        return parts[0], None

    def _score(self, verb: str, obj: str | None) -> float:
        """     score.

    Args:
        verb (str): Verb.
        obj (str | None): Obj.

    Returns:
        float: Description.
    """
        if verb and obj:
            return 0.95
        if verb:
            return 0.60
        return 0.30
