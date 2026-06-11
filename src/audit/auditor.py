from __future__ import annotations

import re
from typing import Optional

from radon.complexity import cc_visit

from ..logger import Logger, timed_step
from ..models import MethodRecord
from .models import CoverageRecord, CoverageStatus


class CoverageAuditor:
    """Coverageauditor."""
    def __init__(self, include_private: bool, include_dunders: bool) -> None:
        """Initialise CoverageAuditor."""
        self.include_private = include_private
        self.include_dunders = include_dunders
        self.logger = Logger.get_instance()

    def audit(self, records: list[MethodRecord]) -> list[CoverageRecord]:
        """    Audit.

    Args:
        records (list[MethodRecord]): Description.

    Returns:
        list[CoverageRecord]: Description.
    """
        total_before = len(records)
        with timed_step("Coverage Audit", self.logger):
            filtered = self._apply_filters(records)
            result: list[CoverageRecord] = []
            for record in filtered:
                cr = self._to_coverage_record(record)
                result.append(cr)

            present = sum(1 for r in result if r.status == CoverageStatus.PRESENT)
            missing = sum(1 for r in result if r.status == CoverageStatus.MISSING)
            partial = sum(1 for r in result if r.status == CoverageStatus.PARTIAL)
            total = len(result)

            self.logger.info(
                f"Total records before filter: {total_before}, after filter: {total}"
            )
            rows = [
                ["Present", str(present), f"{present / total * 100:.1f}" if total else "0"],
                ["Missing", str(missing), f"{missing / total * 100:.1f}" if total else "0"],
                ["Partial", str(partial), f"{partial / total * 100:.1f}" if total else "0"],
            ]
            self.logger.print_table("Coverage Summary", ["Status", "Count", "%"], rows)

            for cr in result:
                self.logger.debug(
                    f"{cr.file_path.name}: {cr.qualified_name}: {cr.status.value}"
                )

            return result

    def _apply_filters(self, records: list[MethodRecord]) -> list[MethodRecord]:
        """     apply filters.

    Args:
        records (list[MethodRecord]): Description.

    Returns:
        list[MethodRecord]: Description.
    """
        private = 0
        dunder = 0
        filtered: list[MethodRecord] = []
        for r in records:
            name = r.qualified_name.split(".")[-1]
            if not self.include_private and name.startswith("_") and not name.startswith("__"):
                private += 1
                continue
            if not self.include_dunders and name.startswith("__") and name.endswith("__"):
                dunder += 1
                continue
            filtered.append(r)
        self.logger.debug(
            f"{len(records) - len(filtered)} records excluded by filter "
            f"({private} private, {dunder} dunders)"
        )
        return filtered

    def _to_coverage_record(self, record: MethodRecord) -> CoverageRecord:
        """     to coverage record.

    Args:
        record (MethodRecord): Description.

    Returns:
        CoverageRecord: Description.
    """
        doc = record.existing_docstring
        status = self._classify(record)
        complexity = self._compute_complexity(record)
        has_raises = self._has_raise_statements(record.full_body)

        return CoverageRecord(
            file_path=record.file_path,
            qualified_name=record.qualified_name,
            kind=record.kind,
            start_line=record.start_line,
            status=status,
            existing_docstring=doc,
            quality=None,
            cyclomatic_complexity=complexity,
            param_count=self._count_params(record),
            has_return_annotation=record.return_annotation is not None
            and record.return_annotation.strip().lower() not in ("none", ""),
            has_raise_statements=has_raises,
        )

    def _classify(self, record: MethodRecord) -> CoverageStatus:
        """     classify.

    Args:
        record (MethodRecord): Description.

    Returns:
        CoverageStatus: Description.
    """
        doc = record.existing_docstring
        if doc is None:
            return CoverageStatus.MISSING
        stripped = doc.strip()
        if not stripped:
            return CoverageStatus.MISSING
        summary = self._get_summary_line(stripped)
        if not summary:
            return CoverageStatus.MISSING

        param_count = self._count_params(record)
        ret_ann = record.return_annotation
        has_ret = ret_ann is not None and ret_ann.strip().lower() not in ("none", "")
        has_raises = self._has_raise_statements(record.full_body)

        is_partial = False

        if param_count > 0 and not self._has_section(
            doc, [r"^\s*(Args|Arguments|Parameters):"]
        ):
            is_partial = True

        if has_ret and not self._has_section(
            doc, [r"^\s*(Returns|Return):"]
        ):
            is_partial = True

        if has_raises and not self._has_section(
            doc, [r"^\s*(Raises|Raise):"]
        ):
            is_partial = True

        return CoverageStatus.PARTIAL if is_partial else CoverageStatus.PRESENT

    def _get_summary_line(self, doc: str) -> str:
        """     get summary line.

    Args:
        doc (str): Description.

    Returns:
        str: Description.
    """
        for line in doc.splitlines():
            line = line.strip()
            if line:
                return line
        return ""

    def _has_section(self, docstring: str, patterns: list[str]) -> bool:
        """     has section.

    Args:
        docstring (str): Description.
        patterns (list[str]): Description.

    Returns:
        bool: Description.
    """
        for pattern in patterns:
            if re.search(pattern, docstring, re.MULTILINE):
                return True
        return False

    def _count_params(self, record: MethodRecord) -> int:
        """     count params.

    Args:
        record (MethodRecord): Description.

    Returns:
        int: Description.
    """
        return len(record.params)

    def _has_raise_statements(self, body: str) -> bool:
        """     has raise statements.

    Args:
        body (str): Description.

    Returns:
        bool: Description.
    """
        return bool(re.search(r"^\s*raise\s", body, re.MULTILINE))

    def _compute_complexity(self, record: MethodRecord) -> int:
        """     compute complexity.

    Args:
        record (MethodRecord): Description.

    Returns:
        int: Description.
    """
        try:
            blocks = cc_visit(record.full_body)
            if blocks:
                return max(b.complexity for b in blocks)
            return 1
        except Exception:
            return 1
