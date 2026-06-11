from pathlib import Path

import pytest

from docstring_agent.walker import FileWalker


def test_walker_skip_dirs(tmp_path: Path) -> None:
    """    Test walker skip dirs.

    Args:
        tmp_path (Path): Description.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cache.pyc").write_text("")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "index.js").write_text("")

    walker = FileWalker(tmp_path, [".git", "__pycache__", "node_modules"])
    files = walker.collect()
    assert len(files) == 1
    assert files[0].name == "main.py"


def test_walker_only_py(tmp_path: Path) -> None:
    """    Test walker only py.

    Args:
        tmp_path (Path): Description.
    """
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.js").write_text("")
    (tmp_path / "c.py").write_text("")

    walker = FileWalker(tmp_path, [])
    files = walker.collect()
    assert len(files) == 2
    assert all(f.suffix == ".py" for f in files)


def test_walker_size_limit(tmp_path: Path) -> None:
    """    Test walker size limit.

    Args:
        tmp_path (Path): Description.
    """
    (tmp_path / "small.py").write_text("x = 1\n")
    large = tmp_path / "large.py"
    large.write_text("x = 1\n" * 100000)
    size = large.stat().st_size
    assert size > 500 * 1024, f"File size {size} is not > 500KB"

    walker = FileWalker(tmp_path, [])
    files = walker.collect()
    names = [f.name for f in files]
    assert "small.py" in names
    assert "large.py" not in names


def test_walker_no_files(tmp_path: Path) -> None:
    """    Test walker no files.

    Args:
        tmp_path (Path): Description.
    """
    walker = FileWalker(tmp_path, [])
    files = walker.collect()
    assert files == []
