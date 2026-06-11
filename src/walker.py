import os
from pathlib import Path

from .logger import Logger, timed_step


class FileWalker:
    """Filewalker."""
    def __init__(self, repo_path: Path, skip_dirs: list[str]) -> None:
        """Initialise FileWalker."""
        self.repo_path = repo_path
        self.skip_dirs = set(skip_dirs)
        self.logger = Logger.get_instance()

    def collect(self) -> list[Path]:
        """Collect."""
        with timed_step("File Discovery", self.logger):
            files: list[Path] = []
            total_kb = 0.0

            if self.repo_path.is_file():
                candidates = [self.repo_path]
            else:
                candidates = []
                for root, dirs, names in os.walk(self.repo_path):
                    dirs[:] = [d for d in dirs if d not in self.skip_dirs]
                    for skipped in self.skip_dirs & set(dirs):
                        self.logger.debug(f"Skipping dir: {skipped}")
                    candidates.extend(Path(root) / n for n in names)

            for fp in candidates:
                if not fp.name.endswith(".py"):
                    continue
                try:
                    size = fp.stat().st_size
                except OSError:
                    continue
                if size > 500 * 1024:
                    continue
                total_kb += size / 1024
                files.append(fp.resolve())

            files.sort()
            self.logger.info(
                f"Discovered {len(files)} Python files ({total_kb:.1f} KB)"
            )
            return files
