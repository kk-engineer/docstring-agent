from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

from .logger import Logger, timed_step
from .models import MethodRecord, ParamInfo


def _get_kind(node: cst.FunctionDef, in_class: bool) -> str:
    """ get kind."""
    if not in_class:
        return "function"
    for dec in node.decorators:
        d = dec.decorator
        if isinstance(d, cst.Name) and d.value == "classmethod":
            return "classmethod"
        if isinstance(d, cst.Name) and d.value == "staticmethod":
            return "staticmethod"
    return "method"


def _annotation_str(module: cst.Module, annotation: Optional[cst.BaseExpression]) -> Optional[str]:
    """ annotation str."""
    if annotation is None:
        return None
    return module.code_for_node(annotation)


def _extract_docstring(node: cst.FunctionDef | cst.ClassDef) -> Optional[str]:
    """ extract docstring."""
    body = node.body
    stmts = body.body
    if not stmts:
        return None
    first = stmts[0]
    if not isinstance(first, cst.SimpleStatementLine):
        return None
    for stmt in first.body:
        if isinstance(stmt, cst.Expr):
            val = stmt.value
            if isinstance(val, (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString)):
                raw = getattr(val, "raw_value", None) or getattr(val, "evaluated_value", None)  # type: ignore[union-attr]
                if raw is not None:
                    return str(raw).strip()
    return None


def _body_source(source_lines: list[str], node: cst.FunctionDef | cst.ClassDef, pos: tuple) -> str:
    """ body source."""
    start_line, start_col = pos[0]
    end_line, end_col = pos[1]
    body_start = start_line  # line of the `:` or body opening
    # The body starts after the `:` — we look for the indented block
    lines = source_lines[body_start - 1 : end_line]
    # Join and strip
    body = "".join(lines)
    # Find the first non-empty line that's indented
    body_lines = body.splitlines(True)
    # Find where the actual body content starts (first indented line)
    content_lines = [line for line in body_lines if line.strip()]
    if not content_lines:
        return ""
    body_text = "".join(body_lines)
    return body_text


def _body_first_200(source_lines: list[str], node: cst.FunctionDef | cst.ClassDef) -> str:
    """ body first 200."""
    full = _get_body_text(source_lines, node)
    if not full:
        return ""
    stripped = full.strip()
    return stripped[:200]


def _get_body_text(source_lines: list[str],
                   node: "cst.FunctionDef | cst.ClassDef") -> str:
    """ get body text."""
    body = node.body
    if isinstance(body, cst.IndentedBlock):
        first_stmt = body.body[0] if body.body else None
        start = getattr(first_stmt, "lineno", getattr(node, "lineno", 1))
        last_stmt = body.body[-1] if body.body else None
        if last_stmt is not None:
            end_line = getattr(last_stmt, "end_lineno",
                               getattr(last_stmt, "lineno",
                                       getattr(node, "end_lineno",
                                               getattr(node, "lineno", 1))))
        else:
            end_line = getattr(node, "end_lineno",
                               getattr(node, "lineno", 1))
    elif isinstance(body, cst.SimpleStatementSuite):
        start = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno",
                           getattr(node, "lineno", 1))
    else:
        start = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno",
                           getattr(node, "lineno", 1))

    lines = source_lines[start - 1 : end_line]
    return "".join(lines)


def _get_node_end_line(node: cst.CSTNode, source_lines: list[str]) -> int:
    """ get node end line."""
    val = getattr(node, "end_lineno", None)
    if val is not None:
        return val
    return getattr(node, "lineno", 1)


def _pos_for_node(node: cst.CSTNode):
    """    Get the position of the given node.

    Args:
      node (cst.CSTNode): The node to get the position for.

    Returns:
      The position of the node.
    """
    lineno = getattr(node, "lineno", 1)
    col = getattr(node, "col_offset", 0)
    end_lineno = getattr(node, "end_lineno", lineno)
    end_col = getattr(node, "end_col_offset", 0)
    return ((lineno, col), (end_lineno, end_col))


class _RecordCollector(cst.CSTVisitor):
    """ recordcollector."""
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self, module: cst.Module, source: str,
        source_lines: list[str], file_path: Path,
    ) -> None:
        """Initialise _RecordCollector."""
        self.module = module
        self.source = source
        self.source_lines = source_lines
        self.file_path = file_path
        self.records: list[MethodRecord] = []
        self._class_stack: list[str] = []

    def _qualified(self, name: str) -> str:
        """ qualified."""
        if self._class_stack:
            return f"{'.'.join(self._class_stack)}.{name}"
        return name

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:  # noqa: N802
        """Visit classdef."""
        name = node.name.value
        qualified = self._qualified(name)
        self._class_stack.append(name)

        params: list[ParamInfo] = []
        existing = _extract_docstring(node)
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)

        body_text = _get_body_text(self.source_lines, node)
        first_200 = body_text.strip()[:200] if body_text else ""

        record = MethodRecord(
            file_path=self.file_path,
            qualified_name=qualified,
            kind="class",
            params=params,
            return_annotation=None,
            start_line=start_line,
            end_line=end_line,
            body_first_200=first_200,
            full_body=body_text,
            existing_docstring=existing,
        )
        self.records.append(record)
        return True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:  # noqa: N802
        """Leave classdef."""
        self._class_stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:  # noqa: N802
        """Visit functiondef."""
        name = node.name.value
        qualified = self._qualified(name)
        in_class = bool(self._class_stack)
        kind = _get_kind(node, in_class)

        params: list[ParamInfo] = []
        for p in node.params.params:
            pname = p.name.value if isinstance(p.name, cst.Name) else str(p.name)
            if pname in ("self", "cls"):
                continue
            p_ann = p.annotation.annotation if p.annotation else None
            annotation = _annotation_str(self.module, p_ann) if p_ann else None  # type: ignore[arg-type]
            params.append(ParamInfo(name=pname, annotation=annotation))

        ret = getattr(node.returns, "annotation", node.returns) if node.returns else None
        return_ann = _annotation_str(self.module, ret) if ret else None  # type: ignore[arg-type]

        existing = _extract_docstring(node)
        start_line = getattr(node, "lineno", 1)  # type: ignore[attr-defined]
        end_line = getattr(node, "end_lineno", start_line)  # type: ignore[attr-defined]

        body_text = _get_body_text(self.source_lines, node)
        first_200 = body_text.strip()[:200] if body_text else ""

        record = MethodRecord(
            file_path=self.file_path,
            qualified_name=qualified,
            kind=kind,
            params=params,
            return_annotation=return_ann,
            start_line=start_line,
            end_line=end_line,
            body_first_200=first_200,
            full_body=body_text,
            existing_docstring=existing,
        )
        self.records.append(record)
        return False  # don't visit nested functions inside functions

    def visit_ClassDef_body(self, node: cst.ClassDef) -> None:  # noqa: N802
        """Visit classdef body."""
        pass


class CSTParser:
    """Cstparser."""
    def __init__(self, docstring_style: str) -> None:
        """Initialise CSTParser."""
        self.docstring_style = docstring_style
        self.logger = Logger.get_instance()

    def parse_file(self, file_path: Path) -> list[MethodRecord]:
        """Parse file and return the result."""
        filename = file_path.name
        with timed_step(f"CST Parsing: {filename}", self.logger):
            try:
                source = file_path.read_text(encoding="utf-8")
            except Exception as e:
                self.logger.warning(f"CST parse failed for {file_path}: {e}")
                return []

            try:
                module = cst.parse_module(source)
            except Exception as e:
                self.logger.warning(f"CST parse failed for {file_path}: {e}")
                return []

            source_lines = source.splitlines(True)
            wrapper = MetadataWrapper(module)
            collector = _RecordCollector(module, source, source_lines, file_path)
            wrapper.visit(collector)

            self.logger.debug(f"Parsed {len(collector.records)} methods from {filename}")
            return collector.records

    def _is_trivial_body(self, body_source: str) -> bool:
        """ is trivial body."""
        stripped = body_source.strip()
        if not stripped:
            return True
        if stripped in ("pass", "...", "pass\n", "...\n"):
            return True
        lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
        if len(lines) <= 1:
            pattern = (r"^(return\s+\w+|return\s+\d+|return\s+['\"]|"
+                       r"return\s+True|return\s+False|return\s+None)\s*$")
            if re.match(pattern, lines[0]) if lines else False:
                return True
            if re.match(r"^raise\s+\w+", lines[0]) if lines else False:
                return False
            if len(lines) == 1:
                return True
        return False
