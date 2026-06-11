from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

COLORS: Dict[str, str] = {
    "step_header": "bold cyan",
    "info": "white",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "debug": "dim magenta",
    "input": "bold blue",
    "output": "bold green",
    "metric": "bold yellow",
    "separator": "dim white",
    "timestamp": "dim white",
    "notice": "bold cyan",
}

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _make_separator(char: str = "\u2500", width: int = 60) -> str:
    """ make separator."""
    return char * width


class Logger:
    """Logger."""
    _instance: Optional["Logger"] = None

    def __init__(self, config) -> None:
        """Initialise Logger."""
        level = config.app.log_level
        log_file = config.app.log_file
        log_json = config.app.log_json

        self._console = Console(
            theme=Theme(COLORS),
            highlight=False,
        )
        self._log_json = log_json

        logging.basicConfig(
            level=_LOG_LEVELS.get(level.upper(), logging.INFO),
            format="%(message)s",
            datefmt="[%H:%M:%S]",
            handlers=[
                RichHandler(
                    console=self._console,
                    show_path=False,
                    omit_repeated_times=False,
                    markup=True,
                )
            ],
        )
        self._logger = logging.getLogger("docstring_gen")

        if log_file:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(str(path), encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "[%(asctime)s] %(levelname)-8s %(message)s",
                datefmt="%H:%M:%S",
            ))
            self._logger.addHandler(fh)

    @classmethod
    def get_instance(cls, config=None) -> "Logger":
        """    Return instance.

    Args:
        config (Any): Description.

    Returns:
        "Logger": Description.
    """
        if cls._instance is None:
            if config is None:
                raise RuntimeError(
                    "Logger not initialized. Call Logger.get_instance(config) first."
                )
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset instance."""
        cls._instance = None

    def _log(self, level: int, message: str, style: Optional[str] = None, **kwargs: Any) -> None:
        """ log."""
        if style:
            self._console.print(Text(message, style=style))
        else:
            self._logger.log(level, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """    Info.

    Args:
        message (str): Description.
    """
        self._log(logging.INFO, message, style="info", **kwargs)

    def success(self, message: str, **kwargs: Any) -> None:
        """    Success.

    Args:
        message (str): Description.
    """
        self._log(logging.INFO, f"  [success]\u2714[/success] {message}", **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """    Warning.

    Args:
        message (str): Description.
    """
        self._log(logging.WARNING, f"  [warning]\u26a0[/warning] {message}", **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """    Error.

    Args:
        message (str): Description.
    """
        self._log(logging.ERROR, f"  [error]\u2717[/error] {message}", **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """    Debug.

    Args:
        message (str): Description.
    """
        self._log(logging.DEBUG, message, style="debug", **kwargs)

    def notice(self, message: str) -> None:
        """    Notice.

    Args:
        message (str): Description.
    """
        self._console.print(Text(message, style="notice"))

    def input_data(self, message: str) -> None:
        """    Input data.

    Args:
        message (str): Description.
    """
        self._console.print(Text(message, style="input"))

    def output_data(self, message: str) -> None:
        """    Output data.

    Args:
        message (str): Description.
    """
        self._console.print(Text(message, style="output"))

    def metric(self, name: str, value: Any) -> None:
        """    Metric.

    Args:
        name (str): Description.
        value (Any): Description.
    """
        self._console.print(Text(f"  {name}: ", style="info") + Text(str(value), style="metric"))

    def step_start(self, step_name: str) -> None:
        """    Step start.

    Args:
        step_name (str): Description.
    """
        line = _make_separator()
        self._console.print(Text(line, style="separator"))
        self._console.print(Text(f"Step: {step_name}", style="step_header"))
        self._console.print(Text(line, style="separator"))

    def step_end(self, step_name: str, elapsed_seconds: float) -> None:
        """    Step end.

    Args:
        step_name (str): Description.
        elapsed_seconds (float): Description.
    """
        self.metric(f"[{step_name}] time_taken_seconds", f"{elapsed_seconds:.3f}s")

    def separator(self) -> None:
        """Separator."""
        self._console.print(Text(_make_separator(), style="separator"))

    def print_panel(self, title: str, content: str) -> None:
        """    Print panel.

    Args:
        title (str): Description.
        content (str): Description.
    """
        from rich.panel import Panel

        self._console.print(Panel(content, title=title, border_style="cyan"))

    def print_table(self, title: str, columns: list[str], rows: list[list[Any]]) -> None:
        """    Print table.

    Args:
        title (str): Description.
        columns (list[str]): Description.
        rows (list[list[Any]]): Description.
    """
        table = Table(title=title, title_style="bold cyan", border_style="dim white")
        for col in columns:
            table.add_column(col, style="info")
        for row in rows:
            table.add_row(*[str(c) for c in row])
        self._console.print(table)

    @contextlib.contextmanager
    def progress_bar(self, total: int, description: str = "Processing", transient: bool = True):
        """    Display a progress bar with the given total and description.

    Args:
      total (int): The total number of steps.
      description (str): The description of the progress bar.
      transient (bool): Whether the progress bar is transient.

    Returns:
      None
    """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TextColumn("\n"),
            console=self._console,
            transient=transient,
        )
        with progress:
            task = progress.add_task(description, total=total)
            yield progress, task

    def get_logger(self) -> logging.Logger:
        """    Get logger.

    Returns:
        logging.Logger: Description.
    """
        return self._logger


@contextlib.contextmanager
def timed_step(step_name: str, logger: Logger) -> Iterator[None]:
    """    Timed step.

    Args:
        step_name (str): Description.
        logger (Logger): Description.

    Returns:
        Iterator[None]: Description.
    """
    logger.step_start(step_name)
    start = time.perf_counter()
    try:
        yield
    except Exception:
        elapsed = time.perf_counter() - start
        logger.step_end(step_name, elapsed)
        raise
    else:
        elapsed = time.perf_counter() - start
        logger.step_end(step_name, elapsed)
