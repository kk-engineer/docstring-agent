from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from ..audit.models import (
    CoverageRecord,
    CoverageStatus,
    FileAuditResult,
    QualityScore,
    ScoreDimension,
)
from ..logger import Logger, timed_step
from ..models import MethodRecord
from ..parser import CSTParser
from .models import RepairStrategy, RepairWorkItem


class AuditReportSchemaError(Exception):
    """Auditreportschemaerror."""
    pass


class AuditReportReader:
    """Auditreportreader."""
    def __init__(self, repo_path: Path, logger: Logger) -> None:
        self.repo_path = repo_path
        self.logger = logger
        self.parser = CSTParser("google")

    def load(self, report_path: Path) -> list[RepairWorkItem]:
        """    Load.

    Args:
        report_path (Path): Description.

    Returns:
        list[RepairWorkItem]: Description.
    """
        with timed_step("Load Audit Report", self.logger):
            if not report_path.exists():
                raise FileNotFoundError(f"Audit report not found: {report_path}")

            data = json.loads(report_path.read_text(encoding="utf-8"))
            self._validate_schema(data)
            quality_threshold = data.get("meta", {}).get("thresholds", {}).get("quality", 0.65)

            items: list[RepairWorkItem] = []
            missing_count = 0
            partial_count = 0
            quality_flagged_count = 0

            for file_entry in data.get("files", []):
                rel_path = file_entry["path"]
                abs_path = (self.repo_path / rel_path).resolve()
                methods_data = file_entry.get("methods", [])

                all_records = self._reparse_file(abs_path)

                for m in methods_data:
                    qname = m["qualified_name"]
                    status_str = m["status"]
                    quality_data = m.get("quality")
                    line = m.get("line", 1)

                    cr = self._build_coverage_record(
                        abs_path, qname, status_str, quality_data, line
                    )
                    mr = self._find_method_record(all_records, qname, line)

                    is_flagged = False
                    if status_str == "missing":
                        is_flagged = True
                        missing_count += 1
                    elif status_str == "partial":
                        is_flagged = True
                        partial_count += 1
                    elif quality_data and quality_data.get("below_threshold", False):
                        is_flagged = True
                        quality_flagged_count += 1

                    if mr is None:
                        self.logger.warning(
                            f"Could not re-parse method {qname} in {abs_path}, skipping"
                        )
                        continue

                    if not is_flagged:
                        items.append(
                            RepairWorkItem(
                                coverage_record=cr,
                                method_record=mr,
                                strategy=RepairStrategy.SKIP,
                            )
                        )
                        continue

                    items.append(
                        RepairWorkItem(
                            coverage_record=cr,
                            method_record=mr,
                            strategy=RepairStrategy.SKIP,
                            priority=mr.cyclomatic_complexity,
                        )
                    )

            self.logger.info(
                f"{len(items)} methods loaded from audit report "
                f"({missing_count} missing, {partial_count} partial, "
                f"{quality_flagged_count} quality-flagged)"
            )
            items.sort(key=lambda x: (x.method_record.file_path, x.method_record.start_line))
            return items

    def _validate_schema(self, data: dict[str, Any]) -> None:
        if "files" not in data:
            raise AuditReportSchemaError("Missing 'files' key in audit report")
        if "meta" not in data:
            raise AuditReportSchemaError("Missing 'meta' key in audit report")
        for fe in data.get("files", []):
            if "path" not in fe:
                raise AuditReportSchemaError("File entry missing 'path'")
            if "methods" not in fe:
                raise AuditReportSchemaError(f"File entry {fe.get('path')} missing 'methods'")

    def _reparse_file(self, abs_path: Path) -> list[MethodRecord]:
        if not abs_path.exists():
            self.logger.warning(f"Source file not found: {abs_path}")
            return []
        try:
            return self.parser.parse_file(abs_path)
        except Exception as e:
            self.logger.warning(f"Failed to parse {abs_path}: {e}")
            return []

    def _find_method_record(
        self, records: list[MethodRecord], qualified_name: str, start_line: int
    ) -> Optional[MethodRecord]:
        candidates = [r for r in records if r.qualified_name == qualified_name]
        if len(candidates) == 1:
            self.logger.debug(f"  Re-parsed {qualified_name}")
            return candidates[0]
        for c in candidates:
            if c.start_line == start_line:
                self.logger.debug(f"  Re-parsed {qualified_name} (by line match)")
                return c
        return None

    def _build_coverage_record(
        self,
        file_path: Path,
        qualified_name: str,
        status_str: str,
        quality_data: Optional[dict[str, Any]],
        start_line: int,
    ) -> CoverageRecord:
        status = CoverageStatus(status_str)
        quality: Optional[QualityScore] = None
        if quality_data:
            dims = []
            for d in quality_data.get("dimensions", []):
                dims.append(
                    ScoreDimension(
                        name=d["name"],
                        score=d["score"],
                        weight=d.get("weight", 0.0),
                        reason=d.get("reason", ""),
                    )
                )
            quality = QualityScore(
                composite=quality_data.get("composite", 0.0),
                dimensions=dims,
                below_threshold=quality_data.get("below_threshold", False),
                threshold=quality_data.get("threshold", 0.65),
            )
        return CoverageRecord(
            file_path=file_path,
            qualified_name=qualified_name,
            kind="",
            start_line=start_line,
            status=status,
            existing_docstring=None,
            quality=quality,
        )
