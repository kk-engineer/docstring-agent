from __future__ import annotations

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
        record (MethodRecord): Description.

    Returns:
        str: Description.
    """
        qname = record.qualified_name
        name = qname.split(".")[-1] if "." in qname else qname
        return self._summary_line(name)

    def _summary_line(self, name: str) -> str:
        """ summary line."""
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
        """ rest from name."""
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

    def _append_args(self, parts: list[str], params) -> None:
        """ append args."""
        parts.append("")
        if self.style == "google":
            parts.append("Args:")
            for p in params:
                ptype = p.annotation or "Any"
                parts.append(f"    {p.name} ({ptype}): Description.")
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
        """ append returns."""
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


class HeuristicPatcher:
    """Generate individual docstring sections (not full docstrings)."""

    def __init__(self, style: str) -> None:
        self.style = style

    def patch_args_section(self, record: MethodRecord) -> str:
        """    Patch args section.

    Args:
        record (MethodRecord): Description.

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
                parts.append(f"    {p.name} ({ptype}): Description.")
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
        record (MethodRecord): Description.

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
        record (MethodRecord): Description.

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
        matches = re.findall(r"\braise\s+(\w+(?:\.\w+)*)", body)
        seen: set[str] = set()
        result: list[str] = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                result.append(m)
        return result

    def _has_section(self, docstring: str, patterns: list[str]) -> bool:
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
        existing_docstring (str): Description.
        record (MethodRecord): Description.
        failing_dims (list[str]): Description.

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
