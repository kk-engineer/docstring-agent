from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class RouteDecision(str, Enum):
    """Routedecision."""
    SKIP = "skip"
    TEMPLATE = "template"
    HEURISTIC = "heuristic"
    LLM = "llm"


@dataclass
class ParamInfo:
    """Paraminfo."""
    name: str
    annotation: Optional[str] = None


@dataclass
class MethodRecord:
    """Methodrecord."""
    file_path: Path
    qualified_name: str
    kind: str  # "function" | "method" | "classmethod" | "staticmethod" | "class"

    params: list[ParamInfo]
    return_annotation: Optional[str]

    start_line: int
    end_line: int

    body_first_200: str
    full_body: str

    existing_docstring: Optional[str]
    cyclomatic_complexity: int = 1

    route: RouteDecision = RouteDecision.HEURISTIC
    generated_docstring: Optional[str] = None


@dataclass
class FileResult:
    """Fileresult."""
    file_path: Path
    records: list[MethodRecord] = field(default_factory=list)
    parse_error: Optional[str] = None
    write_error: Optional[str] = None
    methods_added: int = 0
    methods_improved: int = 0
    methods_skipped: int = 0
    llm_tokens_used: int = 0
    elapsed_seconds: float = 0.0


@dataclass
class PipelineSummary:
    """Pipelinesummary."""
    total_files: int
    total_methods: int
    methods_added: int
    methods_improved: int
    methods_skipped: int
    template_count: int
    heuristic_count: int
    llm_count: int
    llm_tokens_used: int
    elapsed_seconds: float
    errors: list[str]
