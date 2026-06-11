from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

from ..audit.models import CoverageRecord, CoverageStatus, QualityScore
from ..audit.scorer import QualityScorer
from ..config import Config
from ..generators.heuristic import HeuristicGenerator
from ..logger import Logger
from ..models import MethodRecord
from ..parser import CSTParser
from .models import RepairResult, RepairStrategy, RepairSummary, RepairWorkItem


class RepairVerifier:
    """Repairverifier."""
    def __init__(self, config: Config) -> None:
        """Initialise RepairVerifier."""
        self.config = config
        self.logger = Logger.get_instance()
        self.scorer = QualityScorer(0.65)
        self.parser = CSTParser(config.docstring_gen.docstring_style)

    def verify_results(
        self,
        results: list[RepairResult],
        work_items: Optional[list[RepairWorkItem]] = None,
    ) -> list[RepairResult]:
        """    Verify results.

    Args:
        results (list[RepairResult]): Collection of results.
        work_items (Optional[list[RepairWorkItem]]): Work items.

    Returns:
        list[RepairResult]: Description.
    """
        work_by_qname: dict[str, RepairWorkItem] = {}
        if work_items:
            for w in work_items:
                work_by_qname[w.method_record.qualified_name] = w

        by_file: dict[Path, list[RepairResult]] = defaultdict(list)
        for r in results:
            by_file[r.file_path].append(r)

        for file_path, file_results in by_file.items():
            records = self._reparse_file(file_path)
            for r in file_results:
                mr = self._find_record(records, r.qualified_name)
                if mr is None:
                    continue
                if r.strategy_used == RepairStrategy.SKIP:
                    continue
                new_doc = r.new_docstring or mr.existing_docstring or ""
                cr = self._build_coverage_record(mr, new_doc)
                quality = self.scorer.score(cr)
                r.score_after = quality.composite

        return results

    def verify(self, summary: RepairSummary) -> RepairSummary:
        """    Verify.

    Args:
        summary (RepairSummary): Summary.

    Returns:
        RepairSummary: Description.
    """
        self.verify_results(summary.results)
        deltas = [
            r.score_after - r.score_before
            for r in summary.results
            if r.score_before is not None and r.score_after is not None
        ]
        summary.score_delta_mean = sum(deltas) / len(deltas) if deltas else None
        summary.methods_still_below = sum(
            1
            for r in summary.results
            if r.score_after is not None and r.score_after < 0.65
        )
        scored = sum(1 for r in summary.results if r.score_after is not None)
        self.logger.info(
            f"Verified {scored} repaired docstrings; "
            f"mean delta {summary.score_delta_mean:+.3f}, "
            f"{summary.methods_still_below} still below threshold"
        )
        return summary

    def _reparse_file(self, file_path: Path) -> list[MethodRecord]:
        """     reparse file.

    Args:
        file_path (Path): Path to the file.

    Returns:
        list[MethodRecord]: Description.
    """
        try:
            return self.parser.parse_file(file_path)
        except Exception:
            return []

    def _find_record(
        self, records: list[MethodRecord], qualified_name: str
    ) -> Optional[MethodRecord]:
        """     find record.

    Args:
        records (list[MethodRecord]): Collection of records.
        qualified_name (str): Qualified name.

    Returns:
        Optional[MethodRecord]: Description.
    """
        for r in records:
            if r.qualified_name == qualified_name:
                return r
        return None

    def _build_coverage_record(
        self, mr: MethodRecord, docstring: str
    ) -> CoverageRecord:
        """     build coverage record.

    Args:
        mr (MethodRecord): Mr.
        docstring (str): Docstring.

    Returns:
        CoverageRecord: Description.
    """
        return CoverageRecord(
            file_path=mr.file_path,
            qualified_name=mr.qualified_name,
            kind=mr.kind,
            start_line=mr.start_line,
            status=CoverageStatus.PRESENT,
            existing_docstring=docstring,
            quality=None,
            cyclomatic_complexity=mr.cyclomatic_complexity,
            param_count=len(mr.params),
            has_return_annotation=bool(
                mr.return_annotation
                and mr.return_annotation.strip().lower() not in ("none", "")
            ),
            has_raise_statements=bool(
                HeuristicGenerator(self.config.docstring_gen.docstring_style)
                ._extract_raises(mr.full_body)
            ),
        )
