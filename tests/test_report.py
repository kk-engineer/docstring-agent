import asyncio
import json
from pathlib import Path

from src.audit.models import AuditReport
from src.audit.pipeline import AuditPipeline
from src.config import AppConfig, AuditConfig, Config, DocstringGenConfig, LLMConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_shared_config: Config | None = None


def _get_config() -> Config:
    global _shared_config
    if _shared_config is None:
        _shared_config = Config(
            app=AppConfig(name="test", version="0.1.0", log_level="CRITICAL"),
            llm=LLMConfig(
                provider="test", model="test", base_url="http://localhost",
            ),
            docstring_gen=DocstringGenConfig(),
            audit=AuditConfig(
                quality_threshold=0.65,
                min_coverage=0.0,
                include_private=True,
                include_dunders=True,
                sort_by="score",
            ),
        )
    return _shared_config


def test_pipeline_runs_and_produces_report() -> None:
    """Test pipeline runs and produces report."""
    cfg = _get_config()
    pipeline = AuditPipeline(FIXTURES_DIR, cfg)
    report = asyncio.run(pipeline.run())

    assert isinstance(report, AuditReport)
    assert report.total_methods > 0
    assert report.total_files > 0
    assert report.elapsed_seconds > 0


def test_report_aggregates_are_consistent() -> None:
    """Test report aggregates are consistent."""
    cfg = _get_config()
    pipeline = AuditPipeline(FIXTURES_DIR, cfg)
    report = asyncio.run(pipeline.run())

    assert report.coverage_count + report.missing_count + report.partial_count == report.total_methods
    total_from_files = sum(f.total for f in report.file_results)
    assert total_from_files == report.total_methods


def test_json_output_is_valid() -> None:
    """Test json output is valid."""
    cfg = _get_config()
    pipeline = AuditPipeline(FIXTURES_DIR, cfg)
    report = asyncio.run(pipeline.run())

    from src.audit.report import ReportFormatter
    from src.logger import Logger

    logger = Logger.get_instance()
    formatter = ReportFormatter(cfg, logger)
    json_str = formatter.render_json(report)

    parsed = json.loads(json_str)
    assert "meta" in parsed
    assert "summary" in parsed
    assert "files" in parsed
    assert "flagged" in parsed
    assert parsed["summary"]["total_methods"] > 0
    assert "generated_at" in parsed["meta"]


def test_markdown_output_contains_header() -> None:
    """Test markdown output contains header."""
    cfg = _get_config()
    pipeline = AuditPipeline(FIXTURES_DIR, cfg)
    report = asyncio.run(pipeline.run())

    from src.audit.report import ReportFormatter
    from src.logger import Logger

    logger = Logger.get_instance()
    formatter = ReportFormatter(cfg, logger)
    md = formatter.render_markdown(report)

    assert "# Docstring audit" in md
    assert "## Coverage summary" in md
    assert "## Per-file breakdown" in md


def test_coverage_gate_fails_when_below_threshold() -> None:
    """Test coverage gate fails when below threshold."""
    cfg = _get_config()
    pipeline = AuditPipeline(FIXTURES_DIR, cfg)
    report = asyncio.run(pipeline.run())
    report.coverage_threshold = 1.0
    report.passes_coverage_gate = report.overall_coverage_pct >= report.coverage_threshold
    # Fixtures have incomplete docs, so coverage should be < 1.0
    assert report.passes_coverage_gate is False


def test_coverage_uses_filtered_denominator() -> None:
    """Test coverage uses filtered denominator."""
    cfg = _get_config()
    pipeline = AuditPipeline(FIXTURES_DIR, cfg)
    report = asyncio.run(pipeline.run())

    total_filtered = sum(f.total for f in report.file_results)
    assert report.total_methods == total_filtered
