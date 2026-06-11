from __future__ import annotations

from ..models import MethodRecord


class HeuristicGenerator:
    """Heuristicgenerator."""
    def __init__(self, style: str) -> None:
        """Initialise HeuristicGenerator."""
        self.style = style

    def generate(self, record: MethodRecord) -> str:
        """Generate."""
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
