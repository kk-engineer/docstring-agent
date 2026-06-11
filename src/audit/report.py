from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config import Config
from ..logger import Logger
from .models import (
    AuditReport,
    CoverageRecord,
    CoverageStatus,
    FileAuditResult,
    QualityScore,
    ScoreDimension,
)


class ReportFormatter:
    """Reportformatter."""
    def __init__(self, config: Config, logger: Logger) -> None:
        """Initialise ReportFormatter."""
        self.config = config
        self.logger = logger
        self._console = logger._console
        self._audit_config = getattr(config, "audit", None)

    def build(
        self,
        file_results: list[FileAuditResult],
        elapsed: float,
        repo_path: Optional[Path] = None,
    ) -> AuditReport:
        """    Build.

    Args:
        file_results (list[FileAuditResult]): Description.
        elapsed (float): Description.
        repo_path (Optional[Path]): Description.

    Returns:
        AuditReport: Description.
    """
        repo_path = repo_path.resolve() if repo_path else Path(".").resolve()
        audit_cfg = getattr(self.config, "audit", None)
        quality_threshold = (
            audit_cfg.quality_threshold if audit_cfg else 0.65
        )
        coverage_threshold = (
            audit_cfg.min_coverage if audit_cfg else 1.0
        )

        report = AuditReport(
            repo_path=repo_path,
            file_results=file_results,
            quality_threshold=quality_threshold,
            coverage_threshold=coverage_threshold,
            elapsed_seconds=elapsed,
        )

        self._aggregate(report)
        return report

    def _aggregate(self, report: AuditReport) -> None:
        """     aggregate.

    Args:
        report (AuditReport): Description.
    """
        report.total_files = len(report.file_results)
        report.total_methods = sum(f.total for f in report.file_results)
        report.coverage_count = sum(f.coverage_count for f in report.file_results)
        report.missing_count = sum(f.missing_count for f in report.file_results)
        report.partial_count = sum(f.partial_count for f in report.file_results)

        total = report.total_methods
        report.overall_coverage_pct = (
            report.coverage_count / total if total else 1.0
        )

        scored_qualities = []
        for f in report.file_results:
            for r in f.records:
                if r.quality is not None:
                    scored_qualities.append(r.quality.composite)
        report.overall_mean_quality = (
            sum(scored_qualities) / len(scored_qualities) if scored_qualities else 0.0
        )

        report.missing_methods = sorted(
            [
                r for f in report.file_results for r in f.records
                if r.status == CoverageStatus.MISSING
            ],
            key=lambda r: (r.file_path, r.start_line),
        )

        report.partial_methods = sorted(
            [
                r for f in report.file_results for r in f.records
                if r.status == CoverageStatus.PARTIAL
            ],
            key=lambda r: (r.file_path, r.start_line),
        )

        flagged = [
            r for f in report.file_results for r in f.records
            if r.quality and r.quality.below_threshold
        ]
        report.flagged_quality = sorted(
            flagged, key=lambda r: r.quality.composite if r.quality else 0.0
        )

        report.passes_coverage_gate = (
            report.overall_coverage_pct >= report.coverage_threshold
        )
        report.passes_quality_gate = (
            report.overall_mean_quality >= report.quality_threshold
        )

    def render_console(self, report: AuditReport) -> None:
        """    Render console.

    Args:
        report (AuditReport): Description.
    """
        self._render_header(report)
        self._render_coverage_table(report)
        if report.missing_methods:
            self._render_missing_list(report)
        if report.partial_methods:
            self._render_partial_list(report)
        if report.flagged_quality:
            self._render_quality_table(report)
        self._render_gate_summary(report)

    def _render_header(self, report: AuditReport) -> None:
        """     render header.

    Args:
        report (AuditReport): Description.
    """
        header = Panel(
            Text(
                f"{report.repo_path.name}  |  {report.total_files} files  |  "
                f"{report.total_methods} methods  |  {report.elapsed_seconds:.1f}s",
                style="white",
            ),
            title=f"[bold cyan]Docstring Coverage & Quality Audit - "
            f"{report.repo_path.name}[/]",
            border_style="dim white",
        )
        self._console.print(header)

    def _render_coverage_table(self, report: AuditReport) -> None:
        """     render coverage table.

    Args:
        report (AuditReport): Description.
    """
        table = Table(
            title="Coverage by File",
            title_style="bold cyan",
            border_style="dim white",
        )
        table.add_column("File", style="yellow", no_wrap=True)
        table.add_column("Methods", justify="right")
        table.add_column("Present", justify="right")
        table.add_column("Missing", justify="right")
        table.add_column("Partial", justify="right")
        table.add_column("Coverage %", justify="right")

        sorted_files = sorted(
            report.file_results, key=lambda f: f.coverage_pct
        )

        for f in sorted_files:
            pct = f.coverage_pct * 100
            pct_str = f"{pct:.1f}%"
            if pct >= 100:
                style = "green"
            elif pct >= 80:
                style = "yellow"
            else:
                style = "red"
            table.add_row(
                str(f.file_path.relative_to(report.repo_path) if f.file_path.is_absolute() else f.file_path),
                str(f.total),
                str(f.coverage_count),
                str(f.missing_count),
                str(f.partial_count),
                Text(pct_str, style=style),
            )

        total = report.total_methods
        overall_pct_str = f"{report.overall_coverage_pct * 100:.1f}%"
        overall_style = (
            "green"
            if report.overall_coverage_pct >= 1.0
            else "yellow" if report.overall_coverage_pct >= 0.8
            else "red"
        )
        table.add_row(
            Text("TOTAL", style="bold"),
            str(total),
            str(report.coverage_count),
            str(report.missing_count),
            str(report.partial_count),
            Text(overall_pct_str, style=f"bold {overall_style}"),
        )
        self._console.print(table)

    def _render_missing_list(self, report: AuditReport) -> None:
        """     render missing list.

    Args:
        report (AuditReport): Description.
    """
        self._console.print()
        self._console.print(
            Text(
                f"Methods with no docstring ({report.missing_count})",
                style="bold red",
            )
        )
        current_file: Optional[Path] = None
        for r in report.missing_methods:
            if r.file_path != current_file:
                current_file = r.file_path
                rel = (
                    current_file.relative_to(report.repo_path)
                    if current_file.is_absolute()
                    else current_file
                )
                self._console.print(Text(f"  {rel}", style="yellow"))
            self._console.print(
                f"    {r.start_line:>5}  {r.kind:<12}  {r.qualified_name}"
            )

    def _render_partial_list(self, report: AuditReport) -> None:
        """     render partial list.

    Args:
        report (AuditReport): Description.
    """
        self._console.print()
        self._console.print(
            Text(
                f"Methods with incomplete docstrings ({report.partial_count})",
                style="bold yellow",
            )
        )
        current_file: Optional[Path] = None
        for r in report.partial_methods:
            if r.file_path != current_file:
                current_file = r.file_path
                rel = (
                    current_file.relative_to(report.repo_path)
                    if current_file.is_absolute()
                    else current_file
                )
                self._console.print(Text(f"  {rel}", style="yellow"))
            missing_secs = []
            doc = r.existing_docstring or ""
            import re
            if r.param_count > 0 and not re.search(
                r"^\s*(Args|Arguments|Parameters):", doc, re.MULTILINE
            ):
                missing_secs.append("Args")
            if r.has_return_annotation and not re.search(
                r"^\s*(Returns|Return):", doc, re.MULTILINE
            ):
                missing_secs.append("Returns")
            if r.has_raise_statements and not re.search(
                r"^\s*(Raises|Raise):", doc, re.MULTILINE
            ):
                missing_secs.append("Raises")
            missing_str = ", ".join(missing_secs) if missing_secs else "?"
            self._console.print(
                f"    {r.start_line:>5}  {r.kind:<12}  {r.qualified_name}  "
                f"[yellow]Missing: {missing_str}[/]"
            )

    def _render_quality_table(self, report: AuditReport) -> None:
        """     render quality table.

    Args:
        report (AuditReport): Description.
    """
        self._console.print()
        table = Table(
            title=f"Quality Flags (below threshold {report.quality_threshold})",
            title_style="bold cyan",
            border_style="dim white",
        )
        table.add_column("File", style="yellow", no_wrap=True)
        table.add_column("Method")
        table.add_column("Score", justify="right")
        table.add_column("Summary", justify="center")
        table.add_column("Args", justify="center")
        table.add_column("Returns", justify="center")
        table.add_column("Specificity", justify="center")
        table.add_column("Raises", justify="center")

        shown = report.flagged_quality[:50]
        for r in shown:
            q = r.quality
            if q is None:
                continue
            score = q.composite
            if score >= 0.8:
                score_style = "green"
            elif score >= q.threshold:
                score_style = "yellow"
            else:
                score_style = "red"

            dims = {d.name: d.score for d in q.dimensions}
            rel = (
                r.file_path.relative_to(report.repo_path)
                if r.file_path.is_absolute()
                else r.file_path
            )
            table.add_row(
                str(rel),
                r.qualified_name,
                Text(f"{score:.2f}", style=score_style),
                f"{dims.get('summary', 0):.1f}",
                f"{dims.get('args_coverage', 0):.1f}",
                f"{dims.get('returns', 0):.1f}",
                f"{dims.get('specificity', 0):.1f}",
                f"{dims.get('raises', 0):.1f}",
            )

        remaining = len(report.flagged_quality) - 50
        if remaining > 0:
            table.add_row(
                "", f"... and {remaining} more flagged methods", "", "", "", "", "", ""
            )
        self._console.print(table)

    def _render_gate_summary(self, report: AuditReport) -> None:
        """     render gate summary.

    Args:
        report (AuditReport): Description.
    """
        self._console.print()
        cov_gate = report.passes_coverage_gate
        qual_gate = report.passes_quality_gate

        cov_text = Text()
        cov_text.append("Coverage gate: ")
        if cov_gate:
            cov_text.append("PASS", style="bold green")
        else:
            cov_text.append("FAIL", style="bold red")
        cov_text.append(
            f"  ({report.overall_coverage_pct:.1%} <= {report.coverage_threshold:.1%})"
        )
        self._console.print(cov_text)

        qual_text = Text()
        qual_text.append("Quality gate:  ")
        if qual_gate:
            qual_text.append("PASS", style="bold green")
        else:
            qual_text.append("FAIL", style="bold red")
        operator = ">=" if qual_gate else "<"

        qual_text.append(
            f"  (mean {report.overall_mean_quality:.2f} "
            f"{operator} "
            f"{report.quality_threshold:.2f})"
        )
        self._console.print(qual_text)

    def render_json(self, report: AuditReport) -> str:
        """    Render json.

    Args:
        report (AuditReport): Description.

    Returns:
        str: Description.
    """
        def _dim_to_dict(d: ScoreDimension) -> dict[str, Any]:
            return {
                "name": d.name,
                "score": d.score,
                "weight": d.weight,
                "reason": d.reason,
            }

        def _quality_to_dict(
            q: Optional[QualityScore],
        ) -> Optional[dict[str, Any]]:
            if q is None:
                return None
            return {
                "composite": q.composite,
                "below_threshold": q.below_threshold,
                "dimensions": [_dim_to_dict(d) for d in q.dimensions],
            }

        def _rel_path(p: Path) -> str:
            try:
                return str(p.relative_to(report.repo_path))
            except ValueError:
                return str(p)

        data: dict[str, Any] = {
            "meta": {
                "repo": str(report.repo_path),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": report.elapsed_seconds,
                "thresholds": {
                    "coverage": report.coverage_threshold,
                    "quality": report.quality_threshold,
                },
            },
            "summary": {
                "total_files": report.total_files,
                "total_methods": report.total_methods,
                "coverage_pct": report.overall_coverage_pct,
                "mean_quality": report.overall_mean_quality,
                "missing_count": report.missing_count,
                "partial_count": report.partial_count,
                "passes_coverage_gate": report.passes_coverage_gate,
                "passes_quality_gate": report.passes_quality_gate,
            },
            "files": [],
            "flagged": {
                "missing": [],
                "partial": [],
                "quality": [],
            },
        }

        for f in report.file_results:
            file_data: dict[str, Any] = {
                "path": _rel_path(f.file_path),
                "total": f.total,
                "coverage_pct": f.coverage_pct,
                "mean_quality": f.mean_quality,
                "parse_error": f.parse_error,
                "methods": [],
            }
            for r in f.records:
                method_data: dict[str, Any] = {
                    "qualified_name": r.qualified_name,
                    "kind": r.kind,
                    "line": r.start_line,
                    "status": r.status.value,
                    "quality": _quality_to_dict(r.quality),
                }
                file_data["methods"].append(method_data)
            data["files"].append(file_data)

        for r in report.missing_methods:
            data["flagged"]["missing"].append(
                {
                    "file": _rel_path(r.file_path),
                    "line": r.start_line,
                    "qualified_name": r.qualified_name,
                    "kind": r.kind,
                }
            )

        for r in report.partial_methods:
            doc = r.existing_docstring or ""
            missing_secs = []
            import re
            if r.param_count > 0 and not re.search(
                r"^\s*(Args|Arguments|Parameters):", doc, re.MULTILINE
            ):
                missing_secs.append("Args")
            if r.has_return_annotation and not re.search(
                r"^\s*(Returns|Return):", doc, re.MULTILINE
            ):
                missing_secs.append("Returns")
            if r.has_raise_statements and not re.search(
                r"^\s*(Raises|Raise):", doc, re.MULTILINE
            ):
                missing_secs.append("Raises")
            data["flagged"]["partial"].append(
                {
                    "file": _rel_path(r.file_path),
                    "line": r.start_line,
                    "qualified_name": r.qualified_name,
                    "kind": r.kind,
                    "missing_sections": missing_secs,
                }
            )

        for r in report.flagged_quality:
            if r.quality is None:
                continue
            entry: dict[str, Any] = {
                "file": _rel_path(r.file_path),
                "line": r.start_line,
                "qualified_name": r.qualified_name,
                "score": r.quality.composite,
                "dimensions": [_dim_to_dict(d) for d in r.quality.dimensions],
            }
            data["flagged"]["quality"].append(entry)

        return json.dumps(data, indent=2)

    def render_markdown(self, report: AuditReport) -> str:
        """    Render markdown.

    Args:
        report (AuditReport): Description.

    Returns:
        str: Description.
    """
        lines: list[str] = []
        repo_name = report.repo_path.name
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"# Docstring audit: {repo_name}")
        lines.append("")
        lines.append(
            f"> Generated: {ts}  |  {report.elapsed_seconds:.1f}s  |  "
            f"{report.total_files} files"
        )
        lines.append("")

        lines.append("## Coverage summary")
        lines.append("")
        lines.append("| Status | Count | % |")
        lines.append("|--------|-------|---|")
        total = report.total_methods or 1
        present_pct = report.coverage_count / total * 100
        missing_pct = report.missing_count / total * 100
        partial_pct = report.partial_count / total * 100
        lines.append(
            f"| Present | {report.coverage_count} | {present_pct:.1f}% |"
        )
        lines.append(
            f"| Partial | {report.partial_count} | {partial_pct:.1f}% |"
        )
        lines.append(
            f"| Missing | {report.missing_count} | {missing_pct:.1f}% |"
        )
        lines.append(
            f"| **Total** | {report.total_methods} | "
            f"**{report.overall_coverage_pct * 100:.1f}%** |"
        )
        lines.append("")
        cov_badge = "[PASS]" if report.passes_coverage_gate else "[FAIL]"
        qual_badge = "[PASS]" if report.passes_quality_gate else "[FAIL]"
        lines.append(f"Coverage gate: {cov_badge}")
        lines.append(f"Quality gate:  {qual_badge}")
        lines.append("")

        if report.missing_methods:
            lines.append("## Missing docstrings")
            lines.append("")
            current_file: Optional[Path] = None
            file_methods: list[list[CoverageRecord]] = []
            file_paths: list[Path] = []
            for r in report.missing_methods:
                if r.file_path != current_file:
                    file_paths.append(r.file_path)
                    file_methods.append([])
                    current_file = r.file_path
                file_methods[-1].append(r)

            for fp, meths in zip(file_paths, file_methods):
                rel = (
                    str(fp.relative_to(report.repo_path))
                    if fp.is_absolute()
                    else str(fp)
                )
                lines.append(f"<details>")
                lines.append(
                    f"<summary>{rel} — {len(meths)} missing</summary>"
                )
                lines.append("")
                lines.append("| Line | Kind | Method |")
                lines.append("|------|------|--------|")
                for m in meths:
                    lines.append(
                        f"| {m.start_line} | {m.kind} | {m.qualified_name} |"
                    )
                lines.append("")
                lines.append("</details>")
                lines.append("")

        if report.flagged_quality:
            lines.append(
                f"## Quality flags (below threshold {report.quality_threshold})"
            )
            lines.append("")
            current_file = None
            for r in report.flagged_quality:
                q = r.quality
                if q is None:
                    continue
                if r.file_path != current_file:
                    current_file = r.file_path
                    rel = (
                        str(current_file.relative_to(report.repo_path))
                        if current_file.is_absolute()
                        else str(current_file)
                    )
                    lines.append(f"### {rel}")
                    lines.append("")
                    lines.append(
                        "| Method | Score | Summary | Args | Returns | Specificity | Raises |"
                    )
                    lines.append(
                        "|--------|-------|---------|------|---------|-------------|--------|"
                    )

                score_bar = self._score_bar(q.composite)
                dims = {d.name: f"{d.score:.1f}" for d in q.dimensions}
                lines.append(
                    f"| {r.qualified_name} | {score_bar} {q.composite:.2f} | "
                    f"{dims.get('summary', '-')} | "
                    f"{dims.get('args_coverage', '-')} | "
                    f"{dims.get('returns', '-')} | "
                    f"{dims.get('specificity', '-')} | "
                    f"{dims.get('raises', '-')} |"
                )
            lines.append("")

        lines.append("## Per-file breakdown")
        lines.append("")
        lines.append("| File | Methods | Coverage | Mean quality |")
        lines.append("|------|---------|----------|--------------|")
        for f in sorted(report.file_results, key=lambda x: x.file_path):
            rel = (
                str(f.file_path.relative_to(report.repo_path))
                if f.file_path.is_absolute()
                else str(f.file_path)
            )
            mq = f"{f.mean_quality:.2f}" if f.mean_quality is not None else "-"
            lines.append(
                f"| {rel} | {f.total} | {f.coverage_pct * 100:.1f}% | {mq} |"
            )
        lines.append("")

        return "\n".join(lines)

    def _score_bar(self, score: float) -> str:
        """     score bar.

    Args:
        score (float): Description.

    Returns:
        str: Description.
    """
        filled = max(0, min(8, round(score * 8)))
        empty = 8 - filled
        return "\u2588" * filled + "\u2591" * empty
