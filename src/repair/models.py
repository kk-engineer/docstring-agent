from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ..audit.models import CoverageRecord, CoverageStatus  # noqa: F401
from ..models import MethodRecord  # noqa: F401


class RepairStrategy(str, Enum):
    """Repairstrategy."""
    HEURISTIC_PATCH = "heuristic_patch"
    SURGICAL_LLM = "surgical_llm"
    FULL_GENERATION = "full_generation"
    SKIP = "skip"


@dataclass
class RepairInstruction:
    """Repairinstruction."""
    dimension: str
    action: str
    severity: str  # "critical" | "major" | "minor"


@dataclass
class PreserveGuard:
    """Preserveguard."""
    dimension: str
    instruction: str


@dataclass
class RepairWorkItem:
    """Repairworkitem."""
    coverage_record: CoverageRecord
    method_record: MethodRecord
    strategy: RepairStrategy
    instructions: list[RepairInstruction] = field(default_factory=list)
    guards: list[PreserveGuard] = field(default_factory=list)
    priority: int = 0


@dataclass
class RepairResult:
    """Repairresult."""
    file_path: Path
    qualified_name: str
    strategy_used: RepairStrategy
    old_docstring: Optional[str]
    new_docstring: Optional[str]
    score_before: Optional[float]
    score_after: Optional[float] = None
    tokens_used: int = 0
    success: bool = False
    error: Optional[str] = None


@dataclass
class RepairSummary:
    """Repairsummary."""
    repo_path: Path
    total_flagged: int
    repaired: int
    skipped: int
    failed: int
    strategy_breakdown: dict[str, int] = field(default_factory=dict)
    total_tokens_used: int = 0
    score_delta_mean: Optional[float] = None
    methods_still_below: int = 0
    elapsed_seconds: float = 0.0
    results: list[RepairResult] = field(default_factory=list)
