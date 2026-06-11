from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli
from dataclasses import dataclass, field

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme

_console = Console(
    theme=Theme({"heading": "bold cyan", "key": "yellow", "value": "white", "dim": "dim white"}),
    highlight=False,
)


@dataclass
class AppConfig:
    """Appconfig."""
    name: str
    version: str
    log_level: str = "INFO"
    log_file: Optional[str] = None
    log_json: bool = False


@dataclass
class LLMConfig:
    """Llmconfig."""
    provider: str
    model: str
    base_url: str
    max_tokens: int = 1024
    temperature: float = 0.2
    timeout_seconds: int = 30
    max_retries: int = 3
    reachability_check_prompt: str = "Say OK"


@dataclass
class DocstringGenConfig:
    """Docstringgenconfig."""
    skip_directories: list[str] = field(default_factory=lambda: [
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        "dist", "build", ".pytest_cache", ".mypy_cache", "migrations",
    ])
    docstring_style: str = "google"
    complexity_threshold: int = 4
    trivial_prefixes: list[str] = field(default_factory=lambda: [
        "get_", "set_", "is_", "has_",
    ])
    trivial_dunders: list[str] = field(default_factory=lambda: [
        "__init__", "__str__", "__repr__", "__len__", "__eq__",
        "__hash__", "__enter__", "__exit__", "__iter__", "__next__",
    ])
    llm_batch_size: int = 10
    dry_run: bool = False
    improve_existing: bool = True
    use_cache: bool = True


CRITICAL_KEYS: set[str] = {
    "app.name",
    "app.log_level",
    "llm.model",
    "llm.base_url",
}


_config_instance: Optional["Config"] = None


class Config:
    """Config."""
    def __init__(self, app: AppConfig, llm: LLMConfig, docstring_gen: DocstringGenConfig) -> None:
        """Initialise Config."""
        self.app = app
        self.llm = llm
        self.docstring_gen = docstring_gen

    @classmethod
    def get_instance(cls, config_path: Optional[str | Path] = None) -> "Config":
        """Return instance."""
        global _config_instance
        if _config_instance is None:
            load_dotenv()
            _config_instance = cls._load(config_path or "config.toml")
        return _config_instance

    @classmethod
    def _load(cls, config_path: str | Path) -> "Config":
        """ load."""
        path = Path(config_path)
        if not path.exists():
            print(f"ERROR: Config file not found: {path.resolve()}", file=sys.stderr)
            sys.exit(1)

        with path.open("rb") as f:
            raw: dict[str, Any] = tomli.load(f)

        missing = set()
        for key in CRITICAL_KEYS:
            parts = key.split(".")
            obj = raw
            for part in parts:
                if isinstance(obj, dict):
                    obj = obj.get(part, {})
                else:
                    obj = {}
            if obj == {} or obj is None:
                missing.add(key)

        if missing:
            print(
                f"ERROR: Missing critical config keys: {', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            sys.exit(1)

        app_data = raw.get("app", {})
        llm_data = raw.get("llm", {})
        docstring_data = raw.get("docstring_gen", {})

        app = AppConfig(
            name=app_data.get("name", "docstring-agent"),
            version=app_data.get("version", "0.1.0"),
            log_level=app_data.get("log_level", "INFO"),
            log_file=app_data.get("log_file"),
            log_json=app_data.get("log_json", False),
        )
        llm = LLMConfig(
            provider=llm_data.get("provider", "nvidia"),
            model=llm_data.get("model", "meta/llama-3.1-8b-instruct"),
            base_url=llm_data.get("base_url", ""),
            max_tokens=llm_data.get("max_tokens", 1024),
            temperature=llm_data.get("temperature", 0.2),
            timeout_seconds=llm_data.get("timeout_seconds", 30),
            max_retries=llm_data.get("max_retries", 3),
            reachability_check_prompt=llm_data.get("reachability_check_prompt", "Say OK"),
        )
        defaults = DocstringGenConfig()
        docstring_gen = DocstringGenConfig(
            skip_directories=docstring_data.get("skip_directories", defaults.skip_directories),
            docstring_style=docstring_data.get("docstring_style", "google"),
            complexity_threshold=docstring_data.get("complexity_threshold", 4),
            trivial_prefixes=docstring_data.get("trivial_prefixes", defaults.trivial_prefixes),
            trivial_dunders=docstring_data.get("trivial_dunders", defaults.trivial_dunders),
            llm_batch_size=docstring_data.get("llm_batch_size", 10),
            dry_run=docstring_data.get("dry_run", False),
            improve_existing=docstring_data.get("improve_existing", True),
            use_cache=docstring_data.get("use_cache", True),
        )

        return cls(app=app, llm=llm, docstring_gen=docstring_gen)

    def _section_table(self, title: str, items: list[tuple[str, str]]) -> Panel:
        """ section table."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("key", style="yellow", no_wrap=True)
        table.add_column("value", style="white")
        for k, v in items:
            table.add_row(k, str(v))
        return Panel(table, title=f"[bold cyan]{title}[/]", border_style="dim white")

    def display_config(self) -> None:
        """Display config."""
        app_table = self._section_table("App", [
            ("name", self.app.name),
            ("version", self.app.version),
            ("log_level", self.app.log_level),
            ("log_file", self.app.log_file or "(none)"),
            ("log_json", str(self.app.log_json)),
        ])

        llm_table = self._section_table("LLM", [
            ("provider", self.llm.provider),
            ("model", self.llm.model),
            ("base_url", self.llm.base_url),
            ("max_tokens", str(self.llm.max_tokens)),
            ("temperature", str(self.llm.temperature)),
            ("timeout_seconds", str(self.llm.timeout_seconds)),
            ("max_retries", str(self.llm.max_retries)),
        ])

        ds = self.docstring_gen
        skip_dirs = ds.skip_directories
        skip_str = ", ".join(skip_dirs[:4])
        if len(skip_dirs) > 4:
            skip_str += f" ... (+{len(skip_dirs) - 4} more)"

        ds_table = self._section_table("DocstringGen", [
            ("docstring_style", ds.docstring_style),
            ("complexity_threshold", str(ds.complexity_threshold)),
            ("trivial_prefixes", ", ".join(ds.trivial_prefixes)),
            ("trivial_dunders",
             ", ".join(ds.trivial_dunders[:4]) + (" ..." if len(ds.trivial_dunders) > 4 else "")),
            ("llm_batch_size", str(ds.llm_batch_size)),
            ("dry_run", str(ds.dry_run)),
            ("improve_existing", str(ds.improve_existing)),
            ("use_cache", str(ds.use_cache)),
            ("skip_directories", skip_str),
        ])

        _console.print()
        _console.print(app_table)
        _console.print(llm_table)
        _console.print(ds_table)
        _console.print()

    def to_dict(self, mask_secrets: bool = False) -> dict[str, Any]:
        """To dict."""
        return {
            "app": {
                "name": self.app.name,
                "version": self.app.version,
                "log_level": self.app.log_level,
                "log_file": self.app.log_file,
                "log_json": self.app.log_json,
            },
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "base_url": self.llm.base_url,
                "max_tokens": self.llm.max_tokens,
                "temperature": self.llm.temperature,
                "timeout_seconds": self.llm.timeout_seconds,
                "max_retries": self.llm.max_retries,
            },
            "docstring_gen": {
                "skip_directories": self.docstring_gen.skip_directories,
                "docstring_style": self.docstring_gen.docstring_style,
                "complexity_threshold": self.docstring_gen.complexity_threshold,
                "trivial_prefixes": self.docstring_gen.trivial_prefixes,
                "trivial_dunders": self.docstring_gen.trivial_dunders,
                "llm_batch_size": self.docstring_gen.llm_batch_size,
                "dry_run": self.docstring_gen.dry_run,
                "improve_existing": self.docstring_gen.improve_existing,
                "use_cache": self.docstring_gen.use_cache,
            },
        }
