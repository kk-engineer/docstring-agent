from pathlib import Path
from unittest.mock import patch

import pytest

from docstring_agent.config import Config, DocstringGenConfig
from docstring_agent.enricher import Enricher
from docstring_agent.models import MethodRecord, ParamInfo, RouteDecision


def _make_config(
    improve_existing: bool = True,
    complexity_threshold: int = 4,
) -> Config:
    """ make config."""
    cfg = Config.__new__(Config)
    cfg.app = None
    cfg.llm = None
    cfg.docstring_gen = DocstringGenConfig(
        skip_directories=[],
        docstring_style="google",
        complexity_threshold=complexity_threshold,
        trivial_prefixes=["get_", "set_", "is_", "has_"],
        trivial_dunders=["__init__", "__str__", "__repr__"],
        llm_batch_size=10,
        dry_run=False,
        improve_existing=improve_existing,
        use_cache=False,
    )
    return cfg


def _record(
    name: str,
    kind: str = "method",
    params: list | None = None,
    return_ann: str | None = None,
    existing: str | None = None,
    complexity: int = 1,
    body: str = "pass\n",
) -> MethodRecord:
    """ record."""
    return MethodRecord(
        file_path=Path("test.py"),
        qualified_name=name,
        kind=kind,
        params=params or [],
        return_annotation=return_ann,
        start_line=1,
        end_line=5,
        body_first_200=body[:200],
        full_body=body,
        existing_docstring=existing,
        cyclomatic_complexity=complexity,
    )


def test_route_skip_existing_no_improve() -> None:
    """Test route skip existing no improve."""
    cfg = _make_config(improve_existing=False)
    enricher = Enricher(cfg)
    r = _record("my_func", existing="Old docstring.")
    result = enricher._route(r)
    assert result == RouteDecision.SKIP


def test_route_template_dunder() -> None:
    """Test route template dunder."""
    cfg = _make_config()
    enricher = Enricher(cfg)
    r = _record("__init__", kind="method")
    result = enricher._route(r)
    assert result == RouteDecision.TEMPLATE


def test_route_template_trivial_body() -> None:
    """Test route template trivial body."""
    cfg = _make_config()
    enricher = Enricher(cfg)
    r = _record("some_func", kind="function", body="pass\n")
    result = enricher._route(r)
    assert result == RouteDecision.TEMPLATE


def test_route_heuristic_trivial_prefix() -> None:
    """Test route heuristic trivial prefix."""
    cfg = _make_config()
    enricher = Enricher(cfg)
    # Must have a param to avoid rule 3 (trivial body with no params)
    r = _record("get_value", kind="method", complexity=1,
                params=[ParamInfo(name="key", annotation="str")],
                body="return self._data.get(key, None)\n")
    result = enricher._route(r)
    assert result == RouteDecision.HEURISTIC


def test_route_heuristic_low_complexity() -> None:
    """Test route heuristic low complexity."""
    cfg = _make_config(complexity_threshold=4)
    enricher = Enricher(cfg)
    r = _record(
        "process_data",
        kind="method",
        params=[ParamInfo(name="x", annotation="int")],
        return_ann="str",
        complexity=2,
        body="x = 1\ny = 2\nreturn str(x + y)\n",
    )
    result = enricher._route(r)
    assert result == RouteDecision.HEURISTIC


def test_route_llm_high_complexity() -> None:
    """Test route llm high complexity."""
    cfg = _make_config(complexity_threshold=4)
    enricher = Enricher(cfg)
    r = _record(
        "complex_fn",
        kind="function",
        params=[ParamInfo(name="items", annotation="list")],
        return_ann="dict",
        complexity=10,
        body="if x:\n    for y in z:\n        while True:\n            break\n",
    )
    result = enricher._route(r)
    assert result == RouteDecision.LLM


@patch("docstring_agent.enricher.cc_visit")
def test_complexity_computation(mock_cc_visit) -> None:
    """Test complexity computation."""
    from collections import namedtuple
    FakeBlock = namedtuple("FakeBlock", ["complexity"])
    mock_cc_visit.return_value = [FakeBlock(complexity=7)]
    cfg = _make_config()
    enricher = Enricher(cfg)
    r = _record("my_func", body="if x:\n    pass\n")
    enricher._compute_complexity(r)
    assert r.cyclomatic_complexity == 7


def test_enrich_sets_route() -> None:
    """Test enrich sets route."""
    cfg = _make_config()
    enricher = Enricher(cfg)
    records = [
        _record("__init__", kind="method"),
        _record("get_x", kind="method", complexity=1,
                params=[ParamInfo(name="key", annotation="str")],
                body="return self._data.get(key, None)\n"),
        _record("complex", kind="function", complexity=10,
                body="if a:\n    for b in c:\n        pass\n"),
    ]
    results = enricher.enrich(records)
    assert results[0].route == RouteDecision.TEMPLATE
    assert results[1].route == RouteDecision.HEURISTIC
    assert results[2].route == RouteDecision.LLM
