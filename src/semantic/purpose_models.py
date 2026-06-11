from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PurposeFacts:
    """Purposefacts."""
    outcomes: list[str] = field(default_factory=list)
    major_steps: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)
    returned_entity: str | None = None
    confidence: float = 0.0
