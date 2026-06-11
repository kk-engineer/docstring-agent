from __future__ import annotations

import json

from ..prompts import DOCSTRING_BATCH_PROMPT, DOCSTRING_REPAIR_PROMPT
from .models import RepairStrategy, RepairWorkItem


class PromptBuilder:
    """Promptbuilder."""
    def __init__(self, style: str) -> None:
        """Initialise PromptBuilder."""
        self.style = style

    def build_repair_batch(self, items: list[RepairWorkItem]) -> str:
        """    Build and return a repair batch.

    Args:
        items (list[RepairWorkItem]): Description.

    Returns:
        str: Description.
    """
        specs = []
        for item in items:
            mr = item.method_record
            params = [
                {"name": p.name, "annotation": p.annotation} for p in mr.params
            ]
            instructions = [
                {
                    "severity": instr.severity,
                    "action": instr.action,
                }
                for instr in item.instructions
            ]
            guards = [
                {"instruction": g.instruction} for g in item.guards
            ]
            spec = {
                "qualified_name": mr.qualified_name,
                "existing_docstring": mr.existing_docstring or "",
                "signature": {
                    "params": params,
                    "return_annotation": mr.return_annotation,
                },
                "body_excerpt": mr.body_first_200[:600],
                "cyclomatic_complexity": mr.cyclomatic_complexity,
                "instructions": instructions,
                "guards": guards,
            }
            specs.append(spec)
        methods_json = json.dumps(specs, indent=2)
        return DOCSTRING_REPAIR_PROMPT.format(
            style=self.style,
            methods_json=methods_json,
            JSON_SAFETY_RULES="",
        )

    def build_full_generation_batch(self, items: list[RepairWorkItem]) -> str:
        """    Build and return a full generation batch.

    Args:
        items (list[RepairWorkItem]): Description.

    Returns:
        str: Description.
    """
        specs = []
        for item in items:
            mr = item.method_record
            spec = {
                "qualified_name": mr.qualified_name,
                "kind": mr.kind,
                "params": [
                    {"name": p.name, "annotation": p.annotation}
                    for p in mr.params
                ],
                "return_annotation": mr.return_annotation,
                "body": mr.body_first_200[:800],
                "existing_docstring": mr.existing_docstring,
            }
            specs.append(spec)
        methods_json = json.dumps(specs, indent=2)
        return DOCSTRING_BATCH_PROMPT.format(
            style=self.style,
            methods_json=methods_json,
        )
