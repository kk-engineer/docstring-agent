from __future__ import annotations

import ast
import re
from typing import Optional

from ..models import MethodRecord


class HeuristicGenerator:
    """Heuristicgenerator."""
    def __init__(self, style: str) -> None:
        """Initialise HeuristicGenerator."""
        self.style = style

    def generate(self, record: MethodRecord) -> str:
        """    Generate.

    Args:
        record (MethodRecord): Record.

    Returns:
        str: Description.
    """
        qname = record.qualified_name
        name = qname.split(".")[-1] if "." in qname else qname

        parts: list[str] = []

        # Summary
        parts.append(self._summary_line(name))

        # Args
        public_params = [
            p for p in record.params
            if p.name not in {"self", "cls"}
        ]

        if public_params:
            self._append_args(parts, public_params)

        # Returns
        ret = record.return_annotation

        if ret and ret.strip().lower() not in {"", "none"}:
            self._append_returns(parts, ret)

        # Raises
        exceptions = self._extract_raises(record.full_body)

        if exceptions:
            self._append_raises(parts, exceptions)

        return "\n".join(parts)

    def _summary_line(self, name: str) -> str:
        """     summary line.

    Args:
        name (str): Name of the entity.

    Returns:
        str: Description.
    """
        rest = self._rest_from_name(name)
        rules = [
            ("parse_", f"Parse {rest} and return the result."),
            ("validate_", f"Validate {rest} and raise on failure."),
            ("fetch_", f"Fetch {rest} from the source."),
            ("compute_", f"Compute {rest}."),
            ("calculate_", f"Compute {rest}."),
            ("build_", f"Build and return a {rest}."),
            ("create_", f"Build and return a {rest}."),
            ("make_", f"Build and return a {rest}."),
            ("load_", f"Load {rest} from storage."),
            ("save_", f"Save {rest} to storage."),
            ("write_", f"Save {rest} to storage."),
            ("dump_", f"Save {rest} to storage."),
            ("is_", f"Return True if {rest}."),
            ("has_", f"Return True if {rest}."),
            ("check_", f"Return True if {rest}."),
            ("get_", f"Return {rest}."),
            ("set_", f"Set {rest}."),
            ("update_", f"Update {rest}."),
            ("delete_", f"Remove {rest}."),
            ("remove_", f"Remove {rest}."),
            ("run_", f"Run the {rest} process."),
            ("execute_", f"Run the {rest} process."),
            ("process_", f"Run the {rest} process."),
            ("handle_", f"Handle {rest} events."),
            ("on_", f"Callback invoked on {rest}."),
        ]
        for prefix, template in rules:
            if name.startswith(prefix):
                return template

        human = name.replace("_", " ").capitalize()
        if not human.endswith("."):
            human += "."
        return human

    def _rest_from_name(self, name: str) -> str:
        """     rest from name.

    Args:
        name (str): Name of the entity.

    Returns:
        str: Description.
    """
        for prefix in [
            "parse_", "validate_", "fetch_", "compute_", "calculate_",
            "build_", "create_", "make_", "load_", "save_", "write_", "dump_",
            "is_", "has_", "check_", "get_", "set_", "update_",
            "delete_", "remove_", "run_", "execute_", "process_", "handle_", "on_",
        ]:
            if name.startswith(prefix):
                rest = name[len(prefix):]
                return rest.replace("_", " ")
        return name.replace("_", " ")

    _PARAM_DESCRIPTIONS: dict[str, str] = {
        "path": "Path to the file.",
        "file_path": "Path to the file.",
        "filepath": "Path to the file.",
        "directory": "Directory path.",
        "dir_path": "Directory path.",
        "config": "Configuration values.",
        "settings": "Configuration values.",
        "options": "Optional configuration values.",
        "kwargs": "Additional keyword arguments.",
        "args": "Additional positional arguments.",
        "user_id": "Unique identifier of the user.",
        "order_id": "Unique identifier of the order.",
        "request": "Incoming request object.",
        "response": "Response object.",
        "data": "Input data to process.",
        "payload": "Payload containing request data.",
        "records": "Collection of records.",
        "items": "Collection of items.",
        "results": "Collection of results.",
        "client": "Client used to communicate with the service.",
        "session": "Session instance.",
        "timeout": "Timeout in seconds.",
        "token": "Authentication token.",
        "logger": "Logger instance.",
        "name": "Name of the entity.",
        "value": "Value associated with the operation.",
        "text": "Input text.",
        "content": "Content to process.",
        "url": "URL of the target resource.",
        "query": "Query string.",
        "params": "Parameters used by the operation.",
    }

    def _describe_param(self, name: str) -> str:
        """     describe param.

    Args:
        name (str): Name of the entity.

    Returns:
        str: Description.
    """
        key = name.lower()

        if key in self._PARAM_DESCRIPTIONS:
            return self._PARAM_DESCRIPTIONS[key]

        if key.endswith("_id"):
            entity = key[:-3].replace("_", " ")
            return f"Unique identifier of the {entity}."

        if key.endswith("_path"):
            entity = key[:-5].replace("_", " ")
            return f"Path to the {entity}."

        if key.startswith("is_"):
            return f"Whether {key[3:].replace('_', ' ')}."

        if key.startswith("has_"):
            return f"Whether {key[4:].replace('_', ' ')}."

        return f"{name.replace('_', ' ').capitalize()}."


    def _append_args(self, parts: list[str], params) -> None:
        """     append args.

    Args:
        parts (list[str]): Parts.
        params (Any): Parameters used by the operation.
    """
        parts.append("")
        if self.style == "google":
            parts.append("Args:")
            for p in params:
                ptype = p.annotation or "Any"
                desc = self._describe_param(p.name)
                parts.append(f"    {p.name} ({ptype}): {desc}")
        elif self.style == "numpy":
            parts.append("Args")
            parts.append("----")
            for p in params:
                ptype = p.annotation or "Any"
                parts.append(f"    {p.name} : {ptype}")
                parts.append("        Description.")
        elif self.style == "sphinx":
            for p in params:
                ptype = p.annotation or "Any"
                parts.append(f":param {p.name}: Description.")
                parts.append(f":type {p.name}: {ptype}")

    def _append_returns(self, parts: list[str], ret: str) -> None:
        """     append returns.

    Args:
        parts (list[str]): Parts.
        ret (str): Ret.
    """
        parts.append("")
        if self.style == "google":
            parts.append("Returns:")
            parts.append(f"    {ret}: Description.")
        elif self.style == "numpy":
            parts.append("Returns")
            parts.append("-------")
            parts.append(f"    {ret}")
            parts.append("        Description.")
        elif self.style == "sphinx":
            parts.append(":returns: Description.")
            parts.append(f":rtype: {ret}")

    def _append_raises(
            self,
            parts: list[str],
            exceptions: list[str],
    ) -> None:
        """     append raises.

    Args:
        parts (list[str]): Parts.
        exceptions (list[str]): Exceptions.
    """
        if not exceptions:
            return

        parts.append("")

        if self.style == "google":
            parts.append("Raises:")

            for exc in sorted(exceptions):
                parts.append(
                    f"    {exc}: Raised when the operation cannot be completed."
                )

        elif self.style == "numpy":
            parts.append("Raises")
            parts.append("------")

            for exc in sorted(exceptions):
                parts.append(f"    {exc}")
                parts.append(
                    "        Raised when the operation cannot be completed."
                )

        elif self.style == "sphinx":
            for exc in sorted(exceptions):
                parts.append(
                    f":raises {exc}: Raised when the operation cannot be completed."
                )

    def _extract_raises(self, body: str) -> list[str]:
        """     extract raises.

    Args:
        body (str): Body.

    Returns:
        list[str]: Description.
    """
        if not body.strip():
            return []

        try:
            tree = ast.parse(body)
        except SyntaxError:
            #
            # Fallback to regex if the extracted body
            # is not valid standalone Python.
            #
            matches = re.findall(
                r"\braise\s+(\w+(?:\.\w+)*)",
                body,
            )

            seen_re: set[str] = set()
            result: list[str] = []

            for match in matches:
                if match not in seen_re:
                    seen_re.add(match)
                    result.append(match)

            return result

        exceptions: list[str] = []
        seen: set[str] = set()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise):
                continue

            exc = node.exc

            if exc is None:
                #
                # Bare "raise"
                #
                name = "Exception"

            elif isinstance(exc, ast.Call):
                #
                # raise ValueError(...)
                #
                func = exc.func

                if isinstance(func, ast.Name):
                    name = func.id

                elif isinstance(func, ast.Attribute):
                    parts = []
                    attr_node: ast.expr = func
                    while isinstance(attr_node, ast.Attribute):
                        parts.append(attr_node.attr)
                        attr_node = attr_node.value
                    if isinstance(attr_node, ast.Name):
                        parts.append(attr_node.id)
                    name = ".".join(reversed(parts))

                else:
                    name = "Exception"

            elif isinstance(exc, ast.Name):
                #
                # raise SomeError
                #
                name = exc.id

            elif isinstance(exc, ast.Attribute):
                parts = []
                exc_node: ast.expr = exc
                while isinstance(exc_node, ast.Attribute):
                    parts.append(exc_node.attr)
                    exc_node = exc_node.value
                if isinstance(exc_node, ast.Name):
                    parts.append(exc_node.id)
                name = ".".join(reversed(parts))

            else:
                name = "Exception"

            if name not in seen:
                seen.add(name)
                exceptions.append(name)

        return exceptions

class HeuristicPatcher:
    """Heuristicpatcher."""

    def __init__(self, style: str) -> None:
        """Initialise HeuristicPatcher."""
        self.style = style
        self.generator = HeuristicGenerator(style)

    def patch_args_section(self, record: MethodRecord) -> str:
        """    Patch args section.

    Args:
        record (MethodRecord): Record.

    Returns:
        str: Description.
    """
        if not record.params:
            return ""
        parts: list[str] = []
        if self.style == "google":
            parts.append("Args:")
            for p in record.params:
                ptype = p.annotation or "Any"
                desc = (
                    self.generator._describe_param(p.name)
                    if hasattr(self, "generator")
                    else "Description."
                )
                parts.append(f"    {p.name} ({ptype}): {desc}")
        elif self.style == "numpy":
            parts.append("Args")
            parts.append("----")
            for p in record.params:
                ptype = p.annotation or "Any"
                parts.append(f"    {p.name} : {ptype}")
                parts.append("        Description.")
        elif self.style == "sphinx":
            for p in record.params:
                ptype = p.annotation or "Any"
                parts.append(f":param {p.name}: Description.")
                parts.append(f":type {p.name}: {ptype}")
        return "\n".join(parts)

    def patch_returns_section(self, record: MethodRecord) -> str:
        """    Patch returns section.

    Args:
        record (MethodRecord): Record.

    Returns:
        str: Description.
    """
        ret = record.return_annotation
        if ret is None or ret.strip().lower() in ("none", ""):
            return ""
        parts: list[str] = []
        if self.style == "google":
            parts.append("Returns:")
            parts.append(f"    {ret}: Description.")
        elif self.style == "numpy":
            parts.append("Returns")
            parts.append("-------")
            parts.append(f"    {ret}")
            parts.append("        Description.")
        elif self.style == "sphinx":
            parts.append(":returns: Description.")
            parts.append(f":rtype: {ret}")
        return "\n".join(parts)

    def patch_raises_section(self, record: MethodRecord) -> str:
        """    Patch raises section.

    Args:
        record (MethodRecord): Record.

    Returns:
        str: Description.
    """
        exceptions = self._extract_raises(record.full_body)
        if not exceptions:
            return ""
        parts: list[str] = []
        if self.style == "google":
            parts.append("Raises:")
            for exc in sorted(exceptions):
                parts.append(f"    {exc}: Description.")
        elif self.style == "numpy":
            parts.append("Raises")
            parts.append("------")
            for exc in sorted(exceptions):
                parts.append(f"    {exc}")
                parts.append("        Description.")
        elif self.style == "sphinx":
            for exc in sorted(exceptions):
                parts.append(f":raises {exc}: Description.")
        return "\n".join(parts)

    def _extract_raises(self, body: str) -> list[str]:
        """     extract raises.

    Args:
        body (str): Body.

    Returns:
        list[str]: Description.
    """
        matches = re.findall(r"\braise\s+(\w+(?:\.\w+)*)", body)
        seen: set[str] = set()
        result: list[str] = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                result.append(m)
        return result

    def _has_section(self, docstring: str, patterns: list[str]) -> bool:
        """     has section.

    Args:
        docstring (str): Docstring.
        patterns (list[str]): Patterns.

    Returns:
        bool: Description.
    """
        for pattern in patterns:
            if re.search(pattern, docstring, re.MULTILINE):
                return True
        return False

    def apply_patches(
        self,
        existing_docstring: str,
        record: MethodRecord,
        failing_dims: list[str],
    ) -> str:
        """    Apply patches.

    Args:
        existing_docstring (str): Existing docstring.
        record (MethodRecord): Record.
        failing_dims (list[str]): Failing dims.

    Returns:
        str: Description.
    """
        parts = [existing_docstring.rstrip()]
        if "args_coverage" in failing_dims and not self._has_section(
            existing_docstring, [r"^\s*(Args|Arguments|Parameters):"]
        ):
            section = self.patch_args_section(record)
            if section:
                parts.append("")
                parts.append(section)
        if "returns" in failing_dims and not self._has_section(
            existing_docstring, [r"^\s*(Returns|Return):"]
        ):
            section = self.patch_returns_section(record)
            if section:
                parts.append("")
                parts.append(section)
        if "raises" in failing_dims and not self._has_section(
            existing_docstring, [r"^\s*(Raises|Raise):"]
        ):
            section = self.patch_raises_section(record)
            if section:
                parts.append("")
                parts.append(section)
        return "\n".join(parts)
