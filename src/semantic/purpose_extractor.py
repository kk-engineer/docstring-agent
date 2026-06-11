from __future__ import annotations

import ast
from ast import NodeVisitor

from .purpose_models import PurposeFacts

BOILERPLATE: set[str] = {
    "append", "extend", "insert", "remove", "pop",
    "keys", "values", "items", "get", "setdefault",
    "update", "clear", "copy",
    "len", "str", "repr",
    "print",
    "debug", "info", "warning", "error", "exception",
}

_DB_VERBS: set[str] = {"commit", "rollback", "execute", "save", "delete"}
_FS_VERBS: set[str] = {"write", "write_text", "write_bytes", "unlink", "mkdir"}
_NETWORK_VERBS: set[str] = {"fetch", "send", "post"}
_EVENT_VERBS: set[str] = {"publish", "emit", "notify", "dispatch", "enqueue"}

_SIDE_EFFECT_VERBS: set[str] = _DB_VERBS | _FS_VERBS | _NETWORK_VERBS | _EVENT_VERBS

_OUTCOME_MAP: dict[str, str] = {
    "loads": "parse JSON response",
    "dumps": "serialize to JSON",
    "Path": "create path",
}


class _CallCollector(NodeVisitor):
    """ callcollector."""
    def __init__(self) -> None:
        """Initialise _CallCollector."""
        self.returns: list[tuple[ast.Call, ast.Return]] = []
        self.assignments: list[ast.Call] = []
        self.top_exprs: list[ast.Call] = []
        self.all_calls: list[ast.Call] = []

    def visit_Return(self, node: ast.Return) -> None:
        """    Visit return.

    Args:
        node (ast.Return): Node.
    """
        if isinstance(node.value, ast.Call):
            self.returns.append((node.value, node))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """    Visit assign.

    Args:
        node (ast.Assign): Node.
    """
        if isinstance(node.value, ast.Call):
            self.assignments.append(node.value)
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        """    Visit expr.

    Args:
        node (ast.Expr): Node.
    """
        if isinstance(node.value, ast.Call):
            self.top_exprs.append(node.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """    Visit call.

    Args:
        node (ast.Call): Node.
    """
        self.all_calls.append(node)
        self.generic_visit(node)


class PurposeExtractor:
    """Purposeextractor."""
    def extract(self, body: str) -> PurposeFacts:
        """    Extract.

    Args:
        body (str): Body.

    Returns:
        PurposeFacts: Description.
    """
        try:
            tree = ast.parse(body)
        except SyntaxError:
            return PurposeFacts()

        collector = _CallCollector()
        collector.visit(tree)

        facts = PurposeFacts()

        # Rule 1: Return Outcome
        for call_node, _ in collector.returns:
            name = self._call_name(call_node.func)
            if name and name not in BOILERPLATE:
                verb, obj = self._split_call(name)
                facts.outcomes.append(f"{verb} {obj}".strip() if obj else verb)
                facts.returned_entity = obj

        # Rule 2 + 3: Major steps from assignments and top-level expressions
        processed: list[str] = []
        for call_node in collector.assignments:
            name = self._call_name(call_node.func)
            if name and name not in BOILERPLATE:
                processed.append(name)

        for call_node in collector.top_exprs:
            name = self._call_name(call_node.func)
            if name and name not in BOILERPLATE:
                processed.append(name)

        # Dedup consecutive (Rule 7)
        seen: list[str] = []
        for name in processed:
            if seen and name == seen[-1]:
                continue
            seen.append(name)

        for name in seen:
            verb, obj = self._split_call(name)
            step = f"{verb} {obj}".strip() if obj else verb
            # Rule 4: Side effects
            if verb in _SIDE_EFFECT_VERBS:
                facts.side_effects.append(step)
            facts.major_steps.append(step)

        # Nested calls: detect side effects only (Rule 4), skip as major steps
        processed_ids: set[int] = set()
        for call_node, _ in collector.returns:
            processed_ids.add(id(call_node))
        for call_node in collector.assignments:
            processed_ids.add(id(call_node))
        for call_node in collector.top_exprs:
            processed_ids.add(id(call_node))

        for call_node in collector.all_calls:
            if id(call_node) in processed_ids:
                continue  # already handled as outcome/major_step
            name = self._call_name(call_node.func)
            if not name or name in BOILERPLATE:
                continue
            verb, obj = self._split_call(name)
            step = f"{verb} {obj}".strip() if obj else verb
            if verb in _SIDE_EFFECT_VERBS:
                facts.side_effects.append(step)

        return facts

    def _call_name(self, func: ast.expr) -> str | None:
        """     call name.

    Args:
        func (ast.expr): Func.

    Returns:
        str | None: Description.
    """
        if isinstance(func, ast.Name):
            name = func.id
            if name in _OUTCOME_MAP:
                return name
            return name
        if isinstance(func, ast.Attribute):
            return self._traverse_attribute(func)
        return None

    def _traverse_attribute(self, node: ast.Attribute) -> str | None:
        """     traverse attribute.

    Args:
        node (ast.Attribute): Node.

    Returns:
        str | None: Description.
    """
        parts: list[str] = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if parts:
            return parts[0]
        return None

    def _split_call(self, call: str) -> tuple[str, str | None]:
        """     split call.

    Args:
        call (str): Call.

    Returns:
        tuple[str, str | None]: Description.
    """
        if call in _OUTCOME_MAP:
            mapped = _OUTCOME_MAP[call]
            parts = mapped.split(" ", 1)
            return parts[0], parts[1] if len(parts) > 1 else None
        parts = call.split("_")
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        return parts[0], None
