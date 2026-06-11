from __future__ import annotations

from ..models import MethodRecord


class TemplateGenerator:
    """Templategenerator."""
    def __init__(self, style: str) -> None:
        """Initialise TemplateGenerator."""
        self.style = style

    def generate(self, record: MethodRecord) -> str:
        """    Generate.

    Args:
        record (MethodRecord): Description.

    Returns:
        str: Description.
    """
        name = record.qualified_name.split(".")[-1]
        return self._summary(name, record)

    def _summary(self, name: str, record: MethodRecord) -> str:
        """ summary."""
        if name == "__init__":
            class_name = record.qualified_name.split(".")[0] if "." in record.qualified_name else ""
            return f"Initialise {class_name}." if class_name else "Initialise."
        if name in ("__str__", "__repr__"):
            return "Return a string representation."
        if name == "__len__":
            return "Return the length."
        if name == "__eq__":
            return "Return True if equal."
        if name == "__hash__":
            return "Return a hash value."
        if name == "__enter__":
            return "Enter the runtime context."
        if name == "__exit__":
            return "Exit the runtime context."
        if name == "__iter__":
            return "Return an iterator."
        if name == "__next__":
            return "Return the next item."

        human = name.replace("_", " ").capitalize()
        if not human.endswith("."):
            human += "."
        return human
