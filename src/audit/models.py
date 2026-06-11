from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class CoverageStatus(str, Enum):
    """Coveragestatus."""
    PRESENT = "present"
    MISSING = "missing"
    PARTIAL = "partial"


@dataclass
class ScoreDimension:
    """Scoredimension."""
    name: str
    score: float
    weight: float
    reason: str


@dataclass
class QualityScore:
    """Qualityscore."""
    composite: float
    dimensions: list[ScoreDimension]
    below_threshold: bool
    threshold: float


@dataclass
class CoverageRecord:
    """Coveragerecord."""
    file_path: Path
    qualified_name: str
    kind: str
    start_line: int

    status: CoverageStatus
    existing_docstring: Optional[str]

    quality: Optional[QualityScore]

    cyclomatic_complexity: int = 1
    param_count: int = 0
    has_return_annotation: bool = False
    has_raise_statements: bool = False


@dataclass
class FileAuditResult:
    """Fileauditresult."""
    file_path: Path
    records: list[CoverageRecord] = field(default_factory=list)
    parse_error: Optional[str] = None

    @property
    def total(self) -> int:
        """    Total.

        Returns:
            int: The total value.
    """
        return len(self.records)

    @property
    def coverage_count(self) -> int:
        """    Coverage count.

        Returns:
            int: Description.
    """
        return sum(1 for r in self.records if r.status == CoverageStatus.PRESENT)

    @property
    def missing_count(self) -> int:
        """    Missing count.

        Returns:
            int: Description.
    """
        return sum(1 for r in self.records if r.status == CoverageStatus.MISSING)

    @property
    def partial_count(self) -> int:
        """    Partial count.

        Returns:
            int: Description.
    """
        return sum(1 for r in self.records if r.status == CoverageStatus.PARTIAL)

    @property
    def coverage_pct(self) -> float:
        """    Coverage pct.

        Returns:
            float: Description.
    """
        return self.coverage_count / self.total if self.total else 1.0

    @property
    def mean_quality(self) -> Optional[float]:
        """    Mean quality.

        Returns:
            Optional[float]: Description.
    """
        scored = [r.quality.composite for r in self.records if r.quality]
        return sum(scored) / len(scored) if scored else None


@dataclass
class AuditReport:
    """Auditreport."""
    repo_path: Path
    file_results: list[FileAuditResult]
    quality_threshold: float
    coverage_threshold: float
    elapsed_seconds: float

    total_methods: int = 0
    total_files: int = 0
    coverage_count: int = 0
    missing_count: int = 0
    partial_count: int = 0
    overall_coverage_pct: float = 0.0
    overall_mean_quality: float = 0.0
    flagged_quality: list[CoverageRecord] = field(default_factory=list)
    missing_methods: list[CoverageRecord] = field(default_factory=list)
    partial_methods: list[CoverageRecord] = field(default_factory=list)
    passes_coverage_gate: bool = True
    passes_quality_gate: bool = True
