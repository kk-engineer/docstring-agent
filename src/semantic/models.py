from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Action:
    """Action."""
    verb: str
    obj: str | None
    source: str
    confidence: float
