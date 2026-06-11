from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from ..config import Config
from ..logger import Logger, timed_step
from ..models import MethodRecord
from ..parser import CSTParser
from ..walker import FileWalker
from .auditor import CoverageAuditor
from .models import AuditReport, CoverageRecord, FileAuditResult
from .report import ReportFormatter
from .scorer import QualityScorer


class AuditPipeline:
    """Auditpipeline."""
    def __init__(self, repo_path: Path, config: Config) -> None:
        """Initialise AuditPipeline."""
        self.repo_path = repo_path
        self.config = config
        self.logger = Logger.get_instance()
        self.audit_config = getattr(config, "audit", None)

        self.files: list[Path] = []
        self.file_results: list[FileAuditResult] = []
        self.parser = CSTParser(config.docstring_gen.docstring_style)
        self.start_time: float = 0.0

    async def run(self) -> AuditReport:
        """Run."""
        self.start_time = time.perf_counter()
        await self._step_discover()
        file_results = await self._step_audit()
        await self._step_score(file_results)

        formatter = ReportFormatter(self.config, self.logger)
        report = formatter.build(
            file_results,
            time.perf_counter() - self.start_time,
            repo_path=self.repo_path,
        )
        return report

    async def _step_discover(self) -> None:
        """ step discover."""
        with timed_step("File Discovery", self.logger):
            skip_dirs = self.config.docstring_gen.skip_directories
            walker = FileWalker(self.repo_path, skip_dirs)
            self.files = walker.collect()
            self.logger.info(f"Auditing {len(self.files)} Python files in {self.repo_path}")

    async def _step_audit(self) -> list[FileAuditResult]:
        """ step audit."""
        include_private = self.audit_config.include_private if self.audit_config else False
        include_dunders = self.audit_config.include_dunders if self.audit_config else False
        auditor = CoverageAuditor(include_private, include_dunders)

        all_records: list[MethodRecord] = []
        file_results: list[FileAuditResult] = []

        for fp in self.files:
            try:
                records = self.parser.parse_file(fp)
            except Exception as e:
                file_results.append(
                    FileAuditResult(file_path=fp, parse_error=str(e))
                )
                continue

            if records:
                coverage_records = auditor.audit(records)
                file_results.append(
                    FileAuditResult(file_path=fp, records=coverage_records)
                )
            else:
                file_results.append(FileAuditResult(file_path=fp))

            all_records.extend(records)

        total_methods = sum(f.total for f in file_results)
        self.logger.info(f"{total_methods} methods found across {len(self.files)} files")
        self.file_results = file_results
        return file_results

    async def _step_score(
        self, file_results: list[FileAuditResult]
    ) -> None:
        """     step score.

    Args:
        file_results (list[FileAuditResult]): File results.
    """
        quality_threshold = (
            self.audit_config.quality_threshold if self.audit_config else 0.65
        )
        scorer = QualityScorer(quality_threshold)

        scorable: list[CoverageRecord] = []
        for f in file_results:
            scorable.extend(f.records)

        scorer.score_batch(scorable)
