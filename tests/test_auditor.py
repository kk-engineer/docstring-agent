from pathlib import Path

from src.audit.auditor import CoverageAuditor
from src.audit.models import CoverageStatus
from src.models import MethodRecord, ParamInfo


def _make_record(
    qualified_name: str = "test_func",
    kind: str = "function",
    params: list | None = None,
    return_annotation: str | None = None,
    existing_docstring: str | None = None,
    full_body: str = "pass",
    start_line: int = 1,
) -> MethodRecord:
    """     make record.

    Args:
        qualified_name (str): Qualified name.
        kind (str): Kind.
        params (list | None): Parameters used by the operation.
        return_annotation (str | None): Return annotation.
        existing_docstring (str | None): Existing docstring.
        full_body (str): Full body.
        start_line (int): Start line.

    Returns:
        MethodRecord: Description.
    """
    return MethodRecord(
        file_path=Path("/fake/file.py"),
        qualified_name=qualified_name,
        kind=kind,
        params=params or [],
        return_annotation=return_annotation,
        start_line=start_line,
        end_line=start_line + 5,
        body_first_200=full_body[:200],
        full_body=full_body,
        existing_docstring=existing_docstring,
    )


def test_missing_docstring() -> None:
    """Test missing docstring."""
    auditor = CoverageAuditor(include_private=False, include_dunders=False)
    record = _make_record(existing_docstring=None)
    assert auditor._classify(record) == CoverageStatus.MISSING


def test_empty_docstring_is_missing() -> None:
    """Test empty docstring is missing."""
    auditor = CoverageAuditor(include_private=False, include_dunders=False)
    record = _make_record(existing_docstring="   ")
    assert auditor._classify(record) == CoverageStatus.MISSING


def test_present_no_params() -> None:
    """Test present no params."""
    auditor = CoverageAuditor(include_private=False, include_dunders=False)
    record = _make_record(
        existing_docstring="Do something useful.",
        params=[],
    )
    assert auditor._classify(record) == CoverageStatus.PRESENT


def test_partial_no_args_section() -> None:
    """Test partial no args section."""
    auditor = CoverageAuditor(include_private=False, include_dunders=False)
    record = _make_record(
        existing_docstring="Do something with parameters.",
        params=[ParamInfo(name="x"), ParamInfo(name="y")],
    )
    assert auditor._classify(record) == CoverageStatus.PARTIAL


def test_partial_no_returns_section() -> None:
    """Test partial no returns section."""
    auditor = CoverageAuditor(include_private=False, include_dunders=False)
    record = _make_record(
        existing_docstring="Do something and return a value.",
        return_annotation="int",
        params=[],
    )
    assert auditor._classify(record) == CoverageStatus.PARTIAL


def test_partial_no_raises_section() -> None:
    """Test partial no raises section."""
    auditor = CoverageAuditor(include_private=False, include_dunders=False)
    record = _make_record(
        existing_docstring="Do something that may raise.",
        full_body="raise ValueError('bad')",
        params=[],
    )
    assert auditor._classify(record) == CoverageStatus.PARTIAL


def test_complete_google_style_docstring() -> None:
    """Test complete google style docstring."""
    auditor = CoverageAuditor(include_private=False, include_dunders=False)
    doc = """Do something useful.

    Args:
        x (int): The first param.
        y (str): The second param.

    Returns:
        bool: True on success.

    Raises:
        ValueError: If x is negative.
    """
    record = _make_record(
        existing_docstring=doc,
        params=[ParamInfo(name="x"), ParamInfo(name="y")],
        return_annotation="bool",
        full_body="if x < 0:\n    raise ValueError('bad')\nreturn True",
    )
    assert auditor._classify(record) == CoverageStatus.PRESENT


def test_private_method_filtered() -> None:
    """Test private method filtered."""
    auditor = CoverageAuditor(include_private=False, include_dunders=False)
    records = [
        _make_record(qualified_name="do_thing"),
        _make_record(qualified_name="_private_method"),
    ]
    coverage_records = auditor.audit(records)
    names = {r.qualified_name for r in coverage_records}
    assert "do_thing" in names
    assert "_private_method" not in names


def test_dunder_method_filtered() -> None:
    """Test dunder method filtered."""
    auditor = CoverageAuditor(include_private=False, include_dunders=False)
    records = [
        _make_record(qualified_name="do_thing"),
        _make_record(qualified_name="__init__"),
    ]
    coverage_records = auditor.audit(records)
    names = {r.qualified_name for r in coverage_records}
    assert "do_thing" in names
    assert "__init__" not in names


def test_has_raise_statements() -> None:
    """Test has raise statements."""
    auditor = CoverageAuditor(include_private=True, include_dunders=True)
    record = _make_record(
        full_body="if x < 0:\n    raise ValueError('bad')\nreturn x"
    )
    assert auditor._has_raise_statements(record.full_body) is True


def test_no_raise_statements() -> None:
    """Test no raise statements."""
    auditor = CoverageAuditor(include_private=True, include_dunders=True)
    record = _make_record(full_body="return x + 1")
    assert auditor._has_raise_statements(record.full_body) is False
