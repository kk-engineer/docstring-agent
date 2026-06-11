from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import click
from rich.console import Console

from .config import Config
from .logger import Logger
from .pipeline import Pipeline

console = Console()


@click.command(
    context_settings=dict(help_option_names=["-h", "--help"]),
    help="NOLLM-first docstring generator: adds and improves Python docstrings "
         "using static analysis and selective LLM synthesis.",
    epilog="""

Examples:

  docstring-agent
  Process the current directory with default settings.

  docstring-agent /path/to/project
  Process a specific repository.

  docstring-agent --dry-run --show-summary
  Preview changes without writing.

  docstring-agent --style numpy
  Use NumPy-style docstrings instead of Google-style.

  docstring-agent --no-llm
  Skip LLM synthesis entirely (template + heuristic only).

  docstring-agent --llm-only
  Send all methods to LLM, skipping template/heuristic routing.
""",
)
@click.version_option(
    version="0.1.0",
    prog_name="docstring-agent",
    message="%(prog)s version %(version)s",
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
    help="Print final summary table after run.",
)
def main(
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
    """    Run the main function with the given arguments.

    Args:
      repo_path (Path): The path to the repository.
      config (Path): The path to the configuration file.
      dry_run (bool | None): Whether to perform a dry run.
      style (str | None): The style to use.
      improve (bool | None): Whether to improve the code.
      include (tuple[Path, ...]): The paths to include.
      exclude (tuple[Path, ...]): The paths to exclude.
      llm_only (bool): Whether to use the LLM only.
      no_llm (bool): Whether to not use the LLM.
      show_summary (bool): Whether to show the summary.

    Returns:
      None
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

        # Apply CLI overrides
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

        if summary.errors:
            logger.warning(f"Pipeline completed with {len(summary.errors)} errors")
            for err in summary.errors:
                logger.error(err)

    except Exception as err:
        console.print(f"PIPELINE ERROR: {err}")
        sys.exit(1)


def _print_summary(summary) -> None:
    """ print summary."""
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


if __name__ == "__main__":
    main()
