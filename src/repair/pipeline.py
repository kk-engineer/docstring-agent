from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from ..audit.models import AuditReport, CoverageRecord
from ..audit.pipeline import AuditPipeline
from ..config import Config
from ..llm import LLMClient
from ..logger import Logger, timed_step
from ..models import MethodRecord
from ..parser import CSTParser
from .executor import RepairExecutor
from .models import RepairResult, RepairStrategy, RepairSummary, RepairWorkItem
from .planner import RepairPlanner
from .reader import AuditReportReader


class RepairPipeline:
    """Repairpipeline."""
    def __init__(
        self,
        repo_path: Path,
        config: Config,
        llm: Optional[LLMClient] = None,
        dry_run: bool = False,
    ) -> None:
        """Initialise RepairPipeline."""
        self.repo_path = repo_path
        self.config = config
        self.llm = llm
        self.dry_run = dry_run
        self.logger = Logger.get_instance()
        self.repair_cfg = getattr(config, "repair", None)
        self.parser = CSTParser(config.docstring_gen.docstring_style)

    async def run(self, report_path: Optional[Path] = None) -> RepairSummary:
        """    Run.

    Args:
        report_path (Optional[Path]): Description.

    Returns:
        RepairSummary: Description.
    """
        start = time.perf_counter()

        if report_path:
            items = await self._step_load_report(report_path)
        else:
            items = await self._step_audit()

        items = await self._step_plan(items)
        results = await self._step_execute(items)
        summary = self._build_summary(results, start)

        return summary

    async def _step_load_report(self, report_path: Path) -> list[RepairWorkItem]:
        """     step load report.

    Args:
        report_path (Path): Description.

    Returns:
        list[RepairWorkItem]: Description.
    """
        with timed_step("Load Audit Report", self.logger):
            reader = AuditReportReader(self.repo_path, self.logger)
            items = reader.load(report_path)
            self.logger.info(
                f"Loaded {len(items)} methods from {report_path.name}"
            )
            return items

    async def _step_audit(self) -> list[RepairWorkItem]:
        """ step audit."""
        with timed_step("Run Audit", self.logger):
            pipeline = AuditPipeline(self.repo_path, self.config)
            report: AuditReport = await pipeline.run()
            items: list[RepairWorkItem] = []
            skipped = 0
            for fa in report.file_results:
                for cr in fa.records:
                    mr = self._find_method_record(cr)
                    if mr is None:
                        skipped += 1
                        continue
                    items.append(
                        RepairWorkItem(
                            coverage_record=cr,
                            method_record=mr,
                            strategy=RepairStrategy.SKIP,
                        )
                    )
            self.logger.info(
                f"Audited {len(items)} methods across {len(report.file_results)} files"
                + (f", {skipped} skipped (could not re-parse)" if skipped else "")
            )
            return items

    def _find_method_record(self, cr: CoverageRecord) -> Optional[MethodRecord]:
        """     find method record.

    Args:
        cr (CoverageRecord): Description.

    Returns:
        Optional[MethodRecord]: Description.
    """
        try:
            records = self.parser.parse_file(cr.file_path)
        except Exception:
            return None
        for r in records:
            if r.qualified_name == cr.qualified_name:
                return r
        return None

    async def _step_plan(self, items: list[RepairWorkItem]) -> list[RepairWorkItem]:
        """     step plan.

    Args:
        items (list[RepairWorkItem]): Description.

    Returns:
        list[RepairWorkItem]: Description.
    """
        planner = RepairPlanner(self.config)
        return planner.plan(items)

    async def _step_execute(
        self, items: list[RepairWorkItem]
    ) -> list[RepairResult]:
        """     step execute.

    Args:
        items (list[RepairWorkItem]): Description.

    Returns:
        list[RepairResult]: Description.
    """
        executor = RepairExecutor(self.config, self.llm, self.logger, self.dry_run)
        return await executor.execute(items)

    def _build_summary(
        self, results: list[RepairResult], start: float
    ) -> RepairSummary:
        """     build summary.

    Args:
        results (list[RepairResult]): Description.
        start (float): Description.

    Returns:
        RepairSummary: Description.
    """
        elapsed = time.perf_counter() - start
        total = len(results)
        repaired = sum(1 for r in results if r.success and r.new_docstring is not None)
        skipped = sum(1 for r in results if r.strategy_used == RepairStrategy.SKIP)
        failed = sum(1 for r in results if not r.success)
        strategy_breakdown: dict[str, int] = {}
        for r in results:
            strategy_breakdown[r.strategy_used.value] = (
                strategy_breakdown.get(r.strategy_used.value, 0) + 1
            )
        total_tokens = sum(r.tokens_used for r in results)

        deltas = [
            r.score_after - r.score_before
            for r in results
            if r.score_before is not None and r.score_after is not None
        ]
        score_delta_mean = sum(deltas) / len(deltas) if deltas else None

        still_below = sum(
            1
            for r in results
            if r.score_after is not None and r.score_after < 0.65
        )

        self.logger.info(
            f"Repair complete: {repaired} repaired, {skipped} skipped, "
            f"{failed} failed ({elapsed:.1f}s)"
        )

        return RepairSummary(
            repo_path=self.repo_path,
            total_flagged=total,
            repaired=repaired,
            skipped=skipped,
            failed=failed,
            strategy_breakdown=strategy_breakdown,
            total_tokens_used=total_tokens,
            score_delta_mean=score_delta_mean,
            methods_still_below=still_below,
            elapsed_seconds=elapsed,
            results=results,
        )
