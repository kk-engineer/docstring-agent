from __future__ import annotations

import json
from pathlib import Path

CACHE_FILENAME = ".docstring_gen_cache.json"


class DocstringCache:
    """Docstringcache."""
    def __init__(self, repo_path: Path) -> None:
        """Initialise DocstringCache."""
        self.cache_path = repo_path / CACHE_FILENAME
        self._data: dict[str, float] = {}
        if self.cache_path.exists():
            try:
                raw = self.cache_path.read_text(encoding="utf-8")
                self._data = json.loads(raw)
            except Exception:
                self._data = {}

    def is_fresh(self, file_path: Path) -> bool:
        """    Return True if fresh.

    Args:
        file_path (Path): Description.

    Returns:
        bool: Description.
    """
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            return False
        cached_mtime = self._data.get(str(file_path))
        if cached_mtime is None:
            return False
        return abs(mtime - cached_mtime) < 0.01

    def mark_processed(self, file_path: Path) -> None:
        """    Mark processed.

    Args:
        file_path (Path): Description.
    """
        try:
            mtime = file_path.stat().st_mtime
            self._data[str(file_path)] = mtime
        except OSError:
            pass

    def save(self) -> None:
        """Save."""
        try:
            self.cache_path.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
