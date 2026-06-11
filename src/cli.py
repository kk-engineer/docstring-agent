from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import click
from rich.console import Console

from .config import Config, RepairConfig
from .logger import Logger
from .pipeline import Pipeline

console = Console()


@click.group(
    context_settings=dict(help_option_names=["-h", "--help"]),
    help="NOLLM-first docstring generator: adds and improves Python docstrings "
    "using static analysis and selective LLM synthesis.",
)
@click.version_option(
    version="0.1.0",
    prog_name="docstring-agent",
    message="%(prog)s version %(version)s",
)
def cli() -> None:
    """Cli."""
    pass


@cli.command(
    "generate",
    help="Generate docstrings for a Python repository. "
    "REPO_PATH: Path to repository root. Default: current directory.",
    epilog="""

Examples:

  docstring-agent generate
  Process the current directory with default settings.

  docstring-agent generate /path/to/project
  Process a specific repository.

  docstring-agent generate --dry-run --show-summary
  Preview changes without writing.

  docstring-agent generate --style numpy
  Use NumPy-style docstrings instead of Google-style.

  docstring-agent generate --no-llm
  Skip LLM synthesis entirely (template + heuristic only).

  docstring-agent generate --llm-only
  Send all methods to LLM, skipping template/heuristic routing.
""",
)
@click.argument(
    "repo_path",
    default=".",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "--config",
    "-c",
    default="config.toml",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to TOML config file.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=None,
    help="Print unified diff, do not write files.",
)
@click.option(
    "--style",
    type=click.Choice(["google", "numpy", "sphinx"]),
    default=None,
    help="Docstring style. Overrides config.",
)
@click.option(
    "--improve / --no-improve",
    default=None,
    help="Improve existing docstrings.",
)
@click.option(
    "--include",
    multiple=True,
    type=click.Path(path_type=Path),
    help="Only process this file or directory (repeatable).",
)
@click.option(
    "--exclude",
    multiple=True,
    type=click.Path(path_type=Path),
    help="Skip this file or directory (repeatable).",
)
@click.option(
    "--llm-only",
    is_flag=True,
    default=False,
    help="Skip template/heuristic, send everything to LLM.",
)
@click.option(
    "--no-llm",
    is_flag=True,
    default=False,
    help="Skip LLM entirely (template + heuristic only).",
)
@click.option(
    "--show-summary",
    is_flag=True,
    default=False,
    help="Print final PipelineSummary table after run.",
)
def generate(
    repo_path: Path,
    config: Path,
    dry_run: bool | None,
    style: str | None,
    improve: bool | None,
    include: tuple[Path, ...],
    exclude: tuple[Path, ...],
    llm_only: bool,
    no_llm: bool,
    show_summary: bool,
) -> None:
    """    Generate.

    Args:
        repo_path (Path): Path to the repo.
        config (Path): Configuration values.
        dry_run (bool | None): Dry run.
        style (str | None): Style.
        improve (bool | None): Improve.
        include (tuple[Path, ...]): Include.
        exclude (tuple[Path, ...]): Exclude.
        llm_only (bool): Llm only.
        no_llm (bool): No llm.
        show_summary (bool): Show summary.
    """
    hf_key = os.environ.get("hf_api_key", "")
    if hf_key:
        os.environ.setdefault("HF_TOKEN", hf_key)

    config_target = Path(config)
    if not config_target.exists():
        console.print(
            f"CRITICAL: Configuration file '{config_target}' not found. "
            "Program execution terminated."
        )
        console.print(
            "Please make sure a valid 'config.toml' file is present "
            "in the target execution directory."
        )
        sys.exit(1)

    try:
        cfg = Config.get_instance(config_target)

        if dry_run is not None:
            cfg.docstring_gen.dry_run = dry_run
        if style is not None:
            cfg.docstring_gen.docstring_style = style
        if improve is not None:
            cfg.docstring_gen.improve_existing = improve
        if llm_only:
            cfg.docstring_gen.complexity_threshold = 0
        if no_llm:
            cfg.docstring_gen.complexity_threshold = 999

        logger = Logger.get_instance(cfg)
        logger.notice(f"Configuration parsed from {config_target}")

        cfg.display_config()

        llm_client = None
        if not no_llm:
            from .llm import LLMClient

            llm_client = LLMClient.get_instance(cfg)

        pipeline = Pipeline(repo_path, cfg)
        if llm_client:
            pipeline.set_llm_client(llm_client)

        summary = asyncio.run(pipeline.run())

        if show_summary:
            _print_summary(summary)

        _print_file_table(pipeline)

        if summary.errors:
            logger.warning(f"Pipeline completed with {len(summary.errors)} errors")
            for err in summary.errors:
                logger.error(err)

    except Exception as err:
        console.print(f"PIPELINE ERROR: {err}")
        sys.exit(1)


@cli.command(
    "audit",
    help="Audit docstring coverage and quality for a Python repository (read-only). "
    "REPO_PATH: Repository root to audit. Default: current directory.",
    epilog="""

Examples:

  docstring-agent audit
  Audit the current directory.

  docstring-agent audit /path/to/project --format json --output report.json
  Write JSON report to file.

  docstring-agent audit --format console --format json
  Output both console and JSON report.

  docstring-agent audit --fail-under 0.8
  Exit with code 1 if mean quality below 0.8.

  docstring-agent audit --include-private --include-dunders
  Include private and dunder methods.
""",
)
@click.argument(
    "repo_path",
    default=".",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "--config",
    "-c",
    default="config.toml",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to TOML config file.",
)
@click.option(
    "--format",
    "formats",
    multiple=True,
    type=click.Choice(["console", "json", "markdown"]),
    help="Output format(s). Repeatable. Default: console.",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write report to file (instead of stdout).",
)
@click.option(
    "--threshold",
    type=click.FloatRange(0.0, 1.0),
    default=None,
    help="Quality score threshold 0.0-1.0. Overrides config. Default: 0.65.",
)
@click.option(
    "--min-coverage",
    type=click.FloatRange(0.0, 1.0),
    default=None,
    help="Coverage threshold 0.0-1.0. Exit code 1 if not met. Default: 1.0.",
)
@click.option(
    "--include-private",
    is_flag=True,
    default=False,
    help="Include methods whose names start with _.",
)
@click.option(
    "--include-dunders",
    is_flag=True,
    default=False,
    help="Include dunder methods (__init__ etc).",
)
@click.option(
    "--sort-by",
    type=click.Choice(["score", "name", "file", "complexity"]),
    default=None,
    help="Sort flagged methods. Default: score (worst first).",
)
@click.option(
    "--fail-under",
    type=click.FloatRange(0.0, 1.0),
    default=None,
    help="Exit with code 1 if overall quality mean < threshold.",
)
def audit(
    repo_path: Path,
    config: Path,
    formats: tuple[str, ...],
    output: Path | None,
    threshold: float | None,
    min_coverage: float | None,
    include_private: bool,
    include_dunders: bool,
    sort_by: str | None,
    fail_under: float | None,
) -> None:
    """    Audit.

    Args:
        repo_path (Path): Path to the repo.
        config (Path): Configuration values.
        formats (tuple[str, ...]): Formats.
        output (Path | None): Output.
        threshold (float | None): Threshold.
        min_coverage (float | None): Min coverage.
        include_private (bool): Include private.
        include_dunders (bool): Include dunders.
        sort_by (str | None): Sort by.
        fail_under (float | None): Fail under.
    """
    config_target = Path(config)
    if not config_target.exists():
        console.print(
            f"CRITICAL: Configuration file '{config_target}' not found. "
            "Program execution terminated."
        )
        sys.exit(1)

    try:
        cfg = Config.get_instance(config_target)
        logger = Logger.get_instance(cfg)

        audit_cfg = getattr(cfg, "audit", None)

        if threshold is not None and audit_cfg is not None:
            audit_cfg.quality_threshold = threshold
        if min_coverage is not None and audit_cfg is not None:
            audit_cfg.min_coverage = min_coverage
        if include_private and audit_cfg is not None:
            audit_cfg.include_private = True
        if include_dunders and audit_cfg is not None:
            audit_cfg.include_dunders = True
        if sort_by is not None and audit_cfg is not None:
            audit_cfg.sort_by = sort_by
        if fail_under is not None and audit_cfg is not None:
            audit_cfg.fail_under = fail_under

        if not formats:
            if audit_cfg:
                formats = tuple(audit_cfg.default_formats)
            else:
                formats = ("console",)

        from .audit.pipeline import AuditPipeline
        from .audit.report import ReportFormatter

        pipeline = AuditPipeline(repo_path, cfg)
        report = asyncio.run(pipeline.run())

        formatter = ReportFormatter(cfg, logger)

        renderers = {
            "console": formatter.render_console,
            "json": formatter.render_json,
            "markdown": formatter.render_markdown,
        }

        for fmt in formats:
            if fmt == "console":
                renderers[fmt](report)
            else:
                content = renderers[fmt](report)
                if output and len(formats) == 1:
                    output_path = Path(output)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(content, encoding="utf-8")
                    logger.info(f"Report written to {output_path}")
                else:
                    console.print(content)

        if output and len(formats) > 1:
            for fmt in formats:
                if fmt == "console":
                    continue
                content = renderers[fmt](report)
                suffix = fmt
                out_path = Path(str(output) + f".{suffix}")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(content, encoding="utf-8")
                logger.info(f"Report written to {out_path}")

        effective_fail_under = fail_under
        if effective_fail_under is None and audit_cfg is not None:
            effective_fail_under = getattr(audit_cfg, "fail_under", None)
        if effective_fail_under is not None:
            if report.overall_mean_quality < effective_fail_under:
                console.print(
                    f"FAIL: Mean quality {report.overall_mean_quality:.2f} "
                    f"below threshold {effective_fail_under:.2f}"
                )
                sys.exit(1)

        if not report.passes_coverage_gate:
            console.print(
                f"FAIL: Coverage {report.overall_coverage_pct:.1%} "
                f"below threshold {report.coverage_threshold:.1%}"
            )
            sys.exit(1)

    except Exception as err:
        console.print(f"AUDIT ERROR: {err}")
        sys.exit(1)


@cli.command(
    "repair",
    help="Repair low-quality docstrings in a Python repository. "
    "REPO_PATH: Repository root to repair. Default: current directory.",
    epilog="""

Examples:

  docstring-agent repair
  Audit the current directory and repair flagged methods.

  docstring-agent repair /path/to/project --report report.json
  Load a pre-existing audit report and repair flagged methods.

  docstring-agent repair --dry-run
  Preview repairs without writing files.

  docstring-agent repair --no-llm
  Use heuristic patching only, skip LLM.

  docstring-agent repair --token-budget 100000
  Increase the LLM token budget for surgical repairs.
""",
)
@click.argument(
    "repo_path",
    default=".",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "--config",
    "-c",
    default="config.toml",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Path to TOML config file.",
)
@click.option(
    "--report",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to audit report JSON to load instead of running audit inline.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print unified diff, do not write files.",
)
@click.option(
    "--no-llm",
    is_flag=True,
    default=False,
    help="Skip LLM entirely (heuristic patching only).",
)
@click.option(
    "--token-budget",
    type=int,
    default=None,
    help="Override LLM token budget for surgical repairs.",
)
@click.option(
    "--no-backup",
    is_flag=True,
    default=False,
    help="Do not create .bak backup files before writing.",
)
@click.option(
    "--show-summary",
    is_flag=True,
    default=False,
    help="Print RepairSummary table after run.",
)
def repair(
    repo_path: Path,
    config: Path,
    report: Path | None,
    dry_run: bool,
    no_llm: bool,
    token_budget: int | None,
    no_backup: bool,
    show_summary: bool,
) -> None:
    """    Repair.

    Args:
        repo_path (Path): Path to the repo.
        config (Path): Configuration values.
        report (Path | None): Report.
        dry_run (bool): Dry run.
        no_llm (bool): No llm.
        token_budget (int | None): Token budget.
        no_backup (bool): No backup.
        show_summary (bool): Show summary.
    """
    config_target = Path(config)
    if not config_target.exists():
        console.print(
            f"CRITICAL: Configuration file '{config_target}' not found. "
            "Program execution terminated."
        )
        sys.exit(1)

    try:
        cfg = Config.get_instance(config_target)
        logger = Logger.get_instance(cfg)

        if dry_run:
            cfg.docstring_gen.dry_run = True

        if cfg.repair is None:
            cfg.repair = RepairConfig()

        if token_budget is not None:
            cfg.repair.token_budget = token_budget
        if no_backup:
            cfg.repair.backup_originals = False

        logger.notice(f"Configuration parsed from {config_target}")

        llm_client = None
        if not no_llm:
            from .llm import LLMClient

            llm_client = LLMClient.get_instance(cfg)

        from .repair.pipeline import RepairPipeline

        pipeline = RepairPipeline(repo_path, cfg, llm=llm_client, dry_run=dry_run)
        summary = asyncio.run(pipeline.run(report_path=report))

        if show_summary:
            _print_repair_summary(summary)

        logger.info(
            f"Repair complete: {summary.repaired} repaired, "
            f"{summary.skipped} skipped, {summary.failed} failed"
        )

        if summary.score_delta_mean is not None:
            logger.metric("mean_score_delta", f"{summary.score_delta_mean:+.3f}")
        logger.metric("strategies", str(summary.strategy_breakdown))
        logger.metric("elapsed_seconds", f"{summary.elapsed_seconds:.2f}")

        if summary.methods_still_below:
            logger.warning(
                f"{summary.methods_still_below} methods still below quality threshold"
            )

    except Exception as err:
        console.print(f"REPAIR ERROR: {err}")
        sys.exit(1)


def _print_file_table(pipeline) -> None:
    """     print file table.

    Args:
        pipeline (Any): Pipeline.
    """
    from .logger import Logger
    logger = Logger.get_instance()
    rows = []
    for fr in pipeline.file_results:
        rows.append([
            fr.file_path.name,
            str(fr.methods_added),
            str(fr.methods_improved),
            str(fr.methods_skipped),
            str(fr.llm_tokens_used),
            f"{fr.elapsed_seconds:.2f}",
        ])
    if rows:
        logger.print_table(
            "Per-File Results",
            ["File", "Added", "Improved", "Skipped", "LLM tokens", "Time (s)"],
            rows,
        )


def _print_summary(summary) -> None:
    """     print summary.

    Args:
        summary (Any): Summary.
    """
    from .logger import Logger

    logger = Logger.get_instance()

    logger.print_table(
        "Pipeline Summary",
        ["Metric", "Value"],
        [
            ["Total files", str(summary.total_files)],
            ["Total methods", str(summary.total_methods)],
            ["Docstrings added", str(summary.methods_added)],
            ["Docstrings improved", str(summary.methods_improved)],
            ["Docstrings skipped", str(summary.methods_skipped)],
            ["Template generated", str(summary.template_count)],
            ["Heuristic generated", str(summary.heuristic_count)],
            ["LLM generated", str(summary.llm_count)],
            ["LLM tokens used", str(summary.llm_tokens_used)],
            ["Elapsed (s)", f"{summary.elapsed_seconds:.2f}"],
        ],
    )


def _print_repair_summary(summary) -> None:
    """     print repair summary.

    Args:
        summary (Any): Summary.
    """
    from .logger import Logger

    logger = Logger.get_instance()

    strategy_rows = [
        [strategy, str(count)]
        for strategy, count in sorted(summary.strategy_breakdown.items())
    ]
    logger.print_table(
        "Repair Summary",
        ["Metric", "Value"],
        [
            ["Total flagged", str(summary.total_flagged)],
            ["Repaired", str(summary.repaired)],
            ["Skipped", str(summary.skipped)],
            ["Failed", str(summary.failed)],
            ["Strategy breakdown", ", ".join(
                f"{k}={v}" for k, v in sorted(summary.strategy_breakdown.items())
            )],
            ["Total tokens used", str(summary.total_tokens_used)],
            ["Mean score delta",
             f"{summary.score_delta_mean:+.3f}" if summary.score_delta_mean is not None else "N/A"],
            ["Still below threshold", str(summary.methods_still_below)],
            ["Elapsed (s)", f"{summary.elapsed_seconds:.2f}"],
        ],
    )


if __name__ == "__main__":
    cli()
