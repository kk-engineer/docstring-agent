from pathlib import Path

from src.models import MethodRecord, ParamInfo
from src.writer import DocstringWriter
from tests.conftest import SAMPLE_NO_DOCS


def _make_record(name: str, docstring: str, kind: str = "method", start: int = 1, end: int = 5) -> MethodRecord:
    """    Create a method record with the given name, docstring, kind, start, and end.

    Args:
      name (str): The name of the method.
      docstring (str): The docstring of the method.
      kind (str): The kind of the method.
      start (int): The start of the method.
      end (int): The end of the method.

    Returns:
      A method record.
    """
    return MethodRecord(
        file_path=SAMPLE_NO_DOCS,
        qualified_name=name,
        kind=kind,
        params=[],
        return_annotation=None,
        start_line=start,
        end_line=end,
        body_first_200="pass",
        full_body="pass\n",
        existing_docstring=None,
        generated_docstring=docstring,
    )


def test_writer_dry_run(tmp_path: Path) -> None:
    """    Test writer dry run.

    Args:
        tmp_path (Path): Description.
    """
    src = tmp_path / "test.py"
    src.write_text("def foo():\n    pass\n")
    writer = DocstringWriter(dry_run=True, style="google")
    record = _make_record("foo", "Do foo.", start=1, end=2)
    record.file_path = src
    result = writer.apply(src, [record])
    assert result.methods_added == 1
    assert src.read_text() == "def foo():\n    pass\n"


def test_writer_insert_docstring(tmp_path: Path) -> None:
    """    Test writer insert docstring.

    Args:
        tmp_path (Path): Description.
    """
    src = tmp_path / "test.py"
    src.write_text("def foo():\n    pass\n")
    writer = DocstringWriter(dry_run=False, style="google")
    record = _make_record("foo", "Do foo.", start=1, end=2)
    record.file_path = src
    result = writer.apply(src, [record])
    assert result.methods_added == 1
    content = src.read_text()
    assert '"""Do foo."""' in content


def test_writer_replace_docstring(tmp_path: Path) -> None:
    """    Test writer replace docstring.

    Args:
        tmp_path (Path): Description.
    """
    src = tmp_path / "test.py"
    src.write_text('def foo():\n    """Old doc."""\n    pass\n')
    writer = DocstringWriter(dry_run=False, style="google")
    record = _make_record("foo", "New doc.", start=1, end=3)
    record.file_path = src
    record.existing_docstring = "Old doc."
    result = writer.apply(src, [record])
    assert result.methods_improved == 1
    content = src.read_text()
    assert '"""New doc."""' in content
    assert '"Old doc."' not in content


def test_writer_no_records_no_changes(tmp_path: Path) -> None:
    """    Test writer no records no changes.

    Args:
        tmp_path (Path): Description.
    """
    src = tmp_path / "test.py"
    src.write_text("def foo():\n    pass\n")
    writer = DocstringWriter(dry_run=False, style="google")
    result = writer.apply(src, [])
    assert result.methods_added == 0
    assert result.methods_improved == 0
    assert src.read_text() == "def foo():\n    pass\n"


def test_writer_multiline_docstring(tmp_path: Path) -> None:
    """    Test writer multiline docstring.

    Args:
        tmp_path (Path): Description.
    """
    src = tmp_path / "test.py"
    src.write_text("def foo():\n    pass\n")
    writer = DocstringWriter(dry_run=False, style="google")
    doc = "Do foo.\n\nArgs:\n    x (int): Description."
    record = _make_record("foo", doc, start=1, end=2)
    record.file_path = src
    writer.apply(src, [record])
    content = src.read_text()
    assert '"""' in content
    assert "Do foo." in content
    assert "Args:" in content


def test_writer_preserves_rest_of_file(tmp_path: Path) -> None:
    """    Test writer preserves rest of file.

    Args:
        tmp_path (Path): Description.
    """
    src = tmp_path / "test.py"
    src.write_text("import os\n\n\ndef foo():\n    pass\n\n\ndef bar():\n    return 1\n")
    writer = DocstringWriter(dry_run=False, style="google")
    r1 = _make_record("foo", "Do foo.", start=3, end=5)
    r2 = _make_record("bar", "Return 1.", start=7, end=8)
    r1.file_path = src
    r2.file_path = src
    writer.apply(src, [r1, r2])
    content = src.read_text()
    assert "import os" in content
    assert '"""Do foo."""' in content
    assert '"""Return 1."""' in content
    assert "def bar():" in content
