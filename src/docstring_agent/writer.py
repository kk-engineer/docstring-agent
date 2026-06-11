from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Optional

import libcst as cst

from .logger import Logger, timed_step
from .models import FileResult, MethodRecord


class _DocstringInserter(cst.CSTTransformer):
    """ docstringinserter."""
    def __init__(self, records: list[MethodRecord]) -> None:
        """Initialise _DocstringInserter."""
        self.records_by_qname: dict[str, MethodRecord] = {
            r.qualified_name: r for r in records if r.generated_docstring
        }
        self._class_stack: list[str] = []

    def _qualified(self, name: str) -> str:
        """ qualified."""
        if self._class_stack:
            return f"{'.'.join(self._class_stack)}.{name}"
        return name

    def _get_body_indent(self, original_body: cst.BaseSuite) -> str:
        """ get body indent."""
        if isinstance(original_body, cst.IndentedBlock):
            header = original_body.header
            if header:
                indent_str = getattr(header, "indent", None)
                if indent_str:
                    return indent_str
            return "    "
        return "    "

    def _make_docstring_stmt(self, text: str, indent: str) -> cst.SimpleStatementLine:
        """ make docstring stmt."""
        lines = text.split("\n")
        single = len(lines) == 1 and len(text) <= 72
        if single:
            value = f'"""{text}"""'
        else:
            inner = "\n".join(
                f"{indent}{line}" if line else "" for line in lines
            )
            value = f'"""{inner}\n{indent}"""'
        return cst.SimpleStatementLine(
            body=[cst.Expr(value=cst.SimpleString(value=value))]
        )

    def _has_docstring(self, body: cst.BaseSuite) -> bool:
        """ has docstring."""
        if isinstance(body, cst.IndentedBlock):
            stmts = body.body
            if stmts:
                first = stmts[0]
                if isinstance(first, cst.SimpleStatementLine):
                    for stmt in first.body:
                        if isinstance(stmt, cst.Expr):
                            val = stmt.value
                            if isinstance(val, (cst.SimpleString,)):
                                raw = (
                            val.raw_value
                            if hasattr(val, "raw_value")
                            else val.evaluated_value
                        )
                                if raw is not None:
                                    return True
        return False

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:  # noqa: N802
        """    Visit classdef.

    Args:
        node (cst.ClassDef): Description.

    Returns:
        Optional[bool]: Description.
    """
        self._class_stack.append(node.name.value)
        return True

    def leave_ClassDef(  # type: ignore[override]  # noqa: N802
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.CSTNode:
        """    Leave classdef.

    Args:
        original_node (cst.ClassDef): Description.
        updated_node (cst.ClassDef): Description.

    Returns:
        cst.CSTNode: Description.
    """
        self._class_stack.pop()
        qname = self._qualified(original_node.name.value)
        record = self.records_by_qname.get(qname)
        if record is None or record.generated_docstring is None:
            return updated_node
        body = updated_node.body
        indent = self._get_body_indent(body)
        return updated_node.with_changes(
            body=self._insert_docstring(body, record.generated_docstring, indent)
        )

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:  # noqa: N802
        """    Visit functiondef.

    Args:
        node (cst.FunctionDef): Description.

    Returns:
        Optional[bool]: Description.
    """
        return True

    def leave_FunctionDef(  # type: ignore[override]  # noqa: N802
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.CSTNode:
        """    Leave functiondef.

    Args:
        original_node (cst.FunctionDef): Description.
        updated_node (cst.FunctionDef): Description.

    Returns:
        cst.CSTNode: Description.
    """
        qname = self._qualified(original_node.name.value)
        record = self.records_by_qname.get(qname)
        if record is None or record.generated_docstring is None:
            return updated_node
        body = updated_node.body
        indent = self._get_body_indent(body)
        return updated_node.with_changes(
            body=self._insert_docstring(body, record.generated_docstring, indent)
        )

    def _insert_docstring(
        self, body: cst.BaseSuite, docstring: str, indent: str
    ) -> cst.BaseSuite:
        """ insert docstring."""
        new_stmt = self._make_docstring_stmt(docstring, indent)

        if isinstance(body, cst.IndentedBlock):
            stmts = list(body.body)
            if self._has_docstring(body):
                stmts[0] = new_stmt
            else:
                stmts.insert(0, new_stmt)
            return body.with_changes(body=stmts)  # type: ignore[arg-type]
        elif isinstance(body, cst.SimpleStatementSuite):
            new_block = cst.IndentedBlock(
                body=[new_stmt, body],  # type: ignore[list-item]
                header=cst.TrailingWhitespace(),
            )
            return new_block
        return body


class DocstringWriter:
    """Docstringwriter."""
    def __init__(self, dry_run: bool, style: str) -> None:
        """Initialise DocstringWriter."""
        self.dry_run = dry_run
        self.style = style
        self.logger = Logger.get_instance()

    def apply(self, file_path: Path, records: list[MethodRecord]) -> FileResult:
        """    Apply.

    Args:
        file_path (Path): Description.
        records (list[MethodRecord]): Description.

    Returns:
        FileResult: Description.
    """
        filename = file_path.name
        with timed_step(f"Writing: {filename}", self.logger):
            result = FileResult(file_path=file_path, records=records)

            to_write = [r for r in records if r.generated_docstring]
            if not to_write:
                return result

            try:
                source = file_path.read_text(encoding="utf-8")
            except Exception as e:
                result.write_error = str(e)
                self.logger.error(f"Failed to read {file_path}: {e}")
                return result

            try:
                module = cst.parse_module(source)
            except Exception as e:
                result.write_error = str(e)
                self.logger.error(f"Failed to parse {file_path}: {e}")
                return result

            transformer = _DocstringInserter(to_write)
            modified = module.visit(transformer)
            new_source = modified.code

            if new_source == source:
                return result

            if self.dry_run:
                self._print_diff(file_path, source, new_source)
            else:
                self._atomic_write(file_path, new_source)

            # Count changes
            for r in to_write:
                if r.existing_docstring:
                    result.methods_improved += 1
                    self.logger.debug(f"Improved docstring for {r.qualified_name}")
                else:
                    result.methods_added += 1
                    self.logger.debug(f"Inserted docstring for {r.qualified_name}")

            self.logger.info(
                f"{filename}: +{result.methods_added} added, "
                f"~{result.methods_improved} improved, "
                f"={result.methods_skipped} skipped"
            )
            return result

    def _print_diff(self, file_path: Path, source: str, new_source: str) -> None:
        """ print diff."""
        diff = difflib.unified_diff(
            source.splitlines(keepends=True),
            new_source.splitlines(keepends=True),
            fromfile=str(file_path),
            tofile=str(file_path),
        )
        diff_text = "".join(diff)
        if diff_text.strip():
            self.logger.output_data(f"Diff for {file_path}:\n{diff_text}")

    def _atomic_write(self, file_path: Path, new_source: str) -> None:
        """ atomic write."""
        tmp_path = file_path.with_suffix(".py.tmp")
        try:
            tmp_path.write_text(new_source, encoding="utf-8")
            os.replace(tmp_path, file_path)
        except Exception as e:
            self.logger.error(f"Failed to write {file_path}: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
            raise
