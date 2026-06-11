from __future__ import annotations

import asyncio
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Optional

from ..config import Config
from ..generators.heuristic import HeuristicGenerator, HeuristicPatcher
from ..generators.llm_gen import LLMGenerator
from ..llm import LLMClient
from ..logger import Logger, timed_step
from ..models import MethodRecord
from ..writer import DocstringWriter
from .models import (
    RepairResult,
    RepairStrategy,
    RepairWorkItem,
)
from .prompt_builder import PromptBuilder


class RepairExecutor:
    """Repairexecutor."""
    def __init__(
        self,
        config: Config,
        llm: Optional[LLMClient],
        logger: Logger,
        dry_run: bool,
    ) -> None:
        self.config = config
        self.llm = llm
        self.logger = logger
        self.dry_run = dry_run
        self.style = config.docstring_gen.docstring_style
        self.repair_cfg = getattr(config, "repair", None)
        self.patcher = HeuristicPatcher(self.style)
        self.prompt_builder = PromptBuilder(self.style)
        self.heuristic_gen = HeuristicGenerator(self.style)
        self.writer = DocstringWriter(dry_run, self.style)
        self.backup_originals = (
            self.repair_cfg.backup_originals if self.repair_cfg else True
        )
        self._backup_done: set[Path] = set()

    async def execute(self, items: list[RepairWorkItem]) -> list[RepairResult]:
        """    Execute.

    Args:
        items (list[RepairWorkItem]): Description.

    Returns:
        list[RepairResult]: Description.
    """
        with timed_step("Execute Repairs", self.logger):
            results: list[RepairResult] = []

            by_file: dict[Path, list[RepairWorkItem]] = defaultdict(list)
            for item in items:
                if item.strategy != RepairStrategy.SKIP:
                    by_file[item.method_record.file_path].append(item)

            for file_path, file_items in by_file.items():
                file_results = await self._execute_file(file_path, file_items)
                results.extend(file_results)

                h_count = sum(
                    1 for r in file_results if r.strategy_used == RepairStrategy.HEURISTIC_PATCH
                )
                s_count = sum(
                    1 for r in file_results if r.strategy_used == RepairStrategy.SURGICAL_LLM
                )
                f_count = sum(
                    1 for r in file_results if r.strategy_used == RepairStrategy.FULL_GENERATION
                )
                self.logger.info(
                    f"{file_path.name}: {h_count} heuristic, "
                    f"{s_count} LLM, {f_count} full-gen repairs"
                )

            return results

    async def _execute_file(
        self,
        file_path: Path,
        items: list[RepairWorkItem],
    ) -> list[RepairResult]:
        heuristic_items = [i for i in items if i.strategy == RepairStrategy.HEURISTIC_PATCH]
        surgical_items = [i for i in items if i.strategy == RepairStrategy.SURGICAL_LLM]
        fullgen_items = [i for i in items if i.strategy == RepairStrategy.FULL_GENERATION]

        results: list[RepairResult] = []

        if heuristic_items:
            results.extend(await self._execute_heuristic_patch(file_path, heuristic_items))

        if surgical_items and self.llm:
            results.extend(await self._execute_llm_batch(file_path, surgical_items, "surgical"))
        elif surgical_items and not self.llm:
            results.extend(
                await self._execute_heuristic_patch(file_path, surgical_items)
            )

        if fullgen_items and self.llm:
            results.extend(
                await self._execute_llm_batch(file_path, fullgen_items, "fullgen")
            )
        elif fullgen_items and not self.llm:
            results.extend(
                await self._execute_heuristic_patch(file_path, fullgen_items)
            )

        if not self.dry_run and self.backup_originals and file_path not in self._backup_done:
            backup_path = file_path.with_suffix(".py.bak")
            if not backup_path.exists():
                shutil.copy2(file_path, backup_path)
                self.logger.debug(f"Backup created: {backup_path}")
            self._backup_done.add(file_path)

        all_records: list[MethodRecord] = [i.method_record for i in items]
        write_result = self.writer.apply(file_path, all_records)
        if write_result.write_error:
            self.logger.error(f"Write failed for {file_path}: {write_result.write_error}")
            for r in results:
                r.success = False
                r.error = write_result.write_error

        return results

    async def _execute_heuristic_patch(
        self,
        file_path: Path,
        items: list[RepairWorkItem],
    ) -> list[RepairResult]:
        results: list[RepairResult] = []
        for item in items:
            mr = item.method_record
            cr = item.coverage_record
            old_doc = mr.existing_docstring or ""

            if item.strategy == RepairStrategy.FULL_GENERATION:
                if not self.llm:
                    new_doc = self.heuristic_gen.generate(mr)
                else:
                    new_doc = self.heuristic_gen.generate(mr)
            else:
                failing_names = [i.dimension for i in item.instructions]
                new_doc = self.patcher.apply_patches(old_doc, mr, failing_names)

            mr.generated_docstring = new_doc
            results.append(
                RepairResult(
                    file_path=file_path,
                    qualified_name=mr.qualified_name,
                    strategy_used=RepairStrategy.HEURISTIC_PATCH,
                    old_docstring=old_doc or None,
                    new_docstring=new_doc,
                    score_before=cr.quality.composite if cr.quality else None,
                    tokens_used=0,
                    success=True,
                )
            )
        return results

    async def _execute_llm_batch(
        self,
        file_path: Path,
        items: list[RepairWorkItem],
        mode: str,
    ) -> list[RepairResult]:
        if not self.llm:
            return await self._execute_heuristic_patch(file_path, items)

        if mode == "surgical":
            prompt = self.prompt_builder.build_repair_batch(items)
        else:
            prompt = self.prompt_builder.build_full_generation_batch(items)

        response: str
        try:
            response = await self.llm.complete(prompt)
        except Exception as e:
            self.logger.warning(
                f"LLM batch failed for {file_path.name}: {e}, using heuristic fallback"
            )
            return await self._execute_heuristic_patch(file_path, items)

        parsed = self._parse_llm_response(response, items)
        if parsed is None:
            self.logger.warning(
                f"LLM JSON parse failed for {file_path.name}, using heuristic fallback"
            )
            return await self._execute_heuristic_patch(file_path, items)

        results: list[RepairResult] = []
        name_to_item = {i.method_record.qualified_name: i for i in items}
        for entry in parsed:
            qname = entry.get("qualified_name")
            docstring = entry.get("docstring")
            if qname and docstring and qname in name_to_item:
                item = name_to_item[qname]
                mr = item.method_record
                cr = item.coverage_record
                old_doc = mr.existing_docstring or ""

                if mode == "surgical":
                    guard_ok = self._check_guards(item, docstring)
                else:
                    guard_ok = True

                if not guard_ok:
                    self.logger.error(
                        f"Guard violation for {qname}: LLM modified guarded content, "
                        f"falling back to heuristic"
                    )
                    if item.strategy == RepairStrategy.FULL_GENERATION:
                        docstring = self.heuristic_gen.generate(mr)
                    else:
                        failing_names = [i.dimension for i in item.instructions]
                        docstring = self.patcher.apply_patches(old_doc, mr, failing_names)

                mr.generated_docstring = docstring
                strategy = (
                    RepairStrategy.SURGICAL_LLM
                    if mode == "surgical"
                    else RepairStrategy.FULL_GENERATION
                )
                results.append(
                    RepairResult(
                        file_path=file_path,
                        qualified_name=qname,
                        strategy_used=strategy,
                        old_docstring=old_doc or None,
                        new_docstring=docstring,
                        score_before=cr.quality.composite if cr.quality else None,
                        tokens_used=0,
                        success=True,
                    )
                )

        for item in items:
            if item.method_record.generated_docstring is None:
                mr = item.method_record
                cr = item.coverage_record
                old_doc = mr.existing_docstring or ""
                self.logger.debug(f"LLM fallback for {mr.qualified_name}")
                new_doc = self.heuristic_gen.generate(mr)
                mr.generated_docstring = new_doc
                results.append(
                    RepairResult(
                        file_path=file_path,
                        qualified_name=mr.qualified_name,
                        strategy_used=RepairStrategy.HEURISTIC_PATCH,
                        old_docstring=old_doc or None,
                        new_docstring=new_doc,
                        score_before=cr.quality.composite if cr.quality else None,
                        tokens_used=0,
                        success=True,
                    )
                )

        return results

    def _parse_llm_response(
        self, response: str, items: list[RepairWorkItem]
    ) -> Optional[list[dict]]:
        content = response.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
            return None
        except json.JSONDecodeError:
            return None

    def _check_guards(self, item: RepairWorkItem, new_docstring: str) -> bool:
        if not item.guards:
            return True
        old_doc = item.method_record.existing_docstring or ""
        for guard in item.guards:
            if guard.dimension == "summary":
                old_summary = self._get_summary_line(old_doc)
                new_summary = self._get_summary_line(new_docstring)
                if old_summary and old_summary not in new_summary:
                    return False
            if guard.dimension in ("args_coverage", "returns", "raises"):
                section_text = self._extract_section_text(old_doc, guard.dimension)
                if section_text and section_text not in new_docstring:
                    return False
        return True

    def _get_summary_line(self, doc: str) -> str:
        for line in doc.splitlines():
            line = line.strip()
            if line:
                return line
        return ""

    def _extract_section_text(self, doc: str, dimension: str) -> str:
        import re

        headers = {
            "args_coverage": r"^\s*(Args|Arguments|Parameters):",
            "returns": r"^\s*(Returns|Return):",
            "raises": r"^\s*(Raises|Raise):",
        }
        pattern = headers.get(dimension)
        if not pattern:
            return ""
        lines = doc.splitlines()
        start = -1
        for i, line in enumerate(lines):
            if re.match(pattern, line):
                start = i
                break
        if start == -1:
            return ""
        result = [lines[start]]
        for i in range(start + 1, len(lines)):
            stripped = lines[i].strip()
            if not stripped:
                continue
            if re.match(r"^\s*(Args|Arguments|Parameters|Returns|Return|Raises|Raise|Note|Example):", stripped):
                break
            result.append(lines[i])
        return "\n".join(result)
