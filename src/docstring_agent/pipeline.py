from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .cache import DocstringCache
from .config import Config
from .enricher import Enricher
from .generators.heuristic import HeuristicGenerator
from .generators.llm_gen import LLMGenerator
from .generators.template import TemplateGenerator
from .llm import LLMClient
from .logger import Logger, timed_step
from .models import FileResult, MethodRecord, PipelineSummary, RouteDecision
from .parser import CSTParser
from .walker import FileWalker
from .writer import DocstringWriter


class Pipeline:
    """Pipeline."""
    def __init__(self, repo_path: Path, config: Config) -> None:
        """Initialise Pipeline."""
        self.repo_path = repo_path
        self.config = config
        self.ds_config = config.docstring_gen
        self.logger = Logger.get_instance()
        self.cache = DocstringCache(repo_path) if self.ds_config.use_cache else None

        self.llm_client: Optional[LLMClient] = None
        self.parser = CSTParser(self.ds_config.docstring_style)
        self.enricher = Enricher(config)
        self.template_gen = TemplateGenerator(self.ds_config.docstring_style)
        self.heuristic_gen = HeuristicGenerator(self.ds_config.docstring_style)
        self.llm_gen: Optional[LLMGenerator] = None
        self.writer = DocstringWriter(self.ds_config.dry_run, self.ds_config.docstring_style)

        self.all_records: list[MethodRecord] = []
        self.file_results: list[FileResult] = []
        self.errors: list[str] = []
        self.start_time: float = 0.0

    def set_llm_client(self, llm_client: LLMClient) -> None:
        """Set llm client."""
        self.llm_client = llm_client
        self.llm_gen = LLMGenerator(
            llm_client,
            self.ds_config.docstring_style,
            self.ds_config.llm_batch_size,
        )

    async def run(self) -> PipelineSummary:
        """Run."""
        self.start_time = time.perf_counter()
        await self.step_discover()
        await self.step_parse()
        await self.step_enrich()
        await self.step_generate()
        await self.step_write()
        return self._build_summary()

    async def step_discover(self) -> None:
        """Step discover."""
        with timed_step("Phase 1: File Discovery", self.logger):
            walker = FileWalker(self.repo_path, self.ds_config.skip_directories)
            self.files = walker.collect()
            self.logger.info(f"Processing {len(self.files)} files")

    async def step_parse(self) -> None:
        """Step parse."""
        with timed_step("Phase 2: CST Parsing", self.logger):
            self.all_records = []
            files_to_parse = self.files
            if self.cache:
                fresh = [f for f in files_to_parse if not self.cache.is_fresh(f)]
                cached_count = len(files_to_parse) - len(fresh)
                if cached_count:
                    self.logger.info(f"Skipping {cached_count} cached files")
                files_to_parse = fresh

            with self.logger.progress_bar(
                total=len(files_to_parse), description="Parsing files"
            ) as (p, t):
                for fp in files_to_parse:
                    try:
                        records = self.parser.parse_file(fp)
                        self.all_records.extend(records)
                    except Exception as e:
                        self.errors.append(f"Parse error: {fp}: {e}")
                        self.logger.warning(f"Parse failed for {fp}: {e}")
                    p.advance(t)

            self.logger.info(f"Extracted {len(self.all_records)} MethodRecords")

    async def step_enrich(self) -> None:
        """Step enrich."""
        with timed_step("Phase 3: Enrichment & Routing", self.logger):
            self.all_records = self.enricher.enrich(self.all_records)

    async def step_generate(self) -> None:
        """Step generate."""
        with timed_step("Phase 4: Docstring Generation", self.logger):
            template_records = [r for r in self.all_records if r.route == RouteDecision.TEMPLATE]
            heuristic_records = [r for r in self.all_records if r.route == RouteDecision.HEURISTIC]
            llm_records = [r for r in self.all_records if r.route == RouteDecision.LLM]

            for r in template_records:
                r.generated_docstring = self.template_gen.generate(r)
            for r in heuristic_records:
                r.generated_docstring = self.heuristic_gen.generate(r)

            if llm_records and self.llm_gen:
                await self.llm_gen.generate_batch(llm_records)
            elif llm_records:
                self.logger.warning(
                    f"{len(llm_records)} records routed to LLM but no LLM client available; "
                    "using heuristic fallback"
                )
                for r in llm_records:
                    r.generated_docstring = self.heuristic_gen.generate(r)

    async def step_write(self) -> None:
        """Step write."""
        with timed_step("Phase 5: Write-back", self.logger):
            files_by_path: dict[Path, list[MethodRecord]] = {}
            for r in self.all_records:
                files_by_path.setdefault(r.file_path, []).append(r)

            with self.logger.progress_bar(
                total=len(files_by_path), description="Writing files"
            ) as (p, t):
                for fp, records in files_by_path.items():
                    try:
                        result = self.writer.apply(fp, records)
                        self.file_results.append(result)
                        if result.write_error:
                            self.errors.append(f"Write error: {fp}: {result.write_error}")
                        elif self.cache and not self.ds_config.dry_run:
                            self.cache.mark_processed(fp)
                    except Exception as e:
                        self.errors.append(f"Write error: {fp}: {e}")
                        self.logger.error(f"Write failed for {fp}: {e}")
                    p.advance(t)

            if self.cache and not self.ds_config.dry_run:
                self.cache.save()

    def _build_summary(self) -> PipelineSummary:
        """ build summary."""
        total_methods = len(self.all_records)
        total_added = sum(r.methods_added for r in self.file_results)
        total_improved = sum(r.methods_improved for r in self.file_results)
        total_skipped = sum(r.methods_skipped for r in self.file_results)
        total_llm_tokens = sum(r.llm_tokens_used for r in self.file_results)
        template_count = sum(1 for r in self.all_records if r.route == RouteDecision.TEMPLATE)
        heuristic_count = sum(1 for r in self.all_records if r.route == RouteDecision.HEURISTIC)
        llm_count = sum(1 for r in self.all_records if r.route == RouteDecision.LLM)
        elapsed = time.perf_counter() - self.start_time

        return PipelineSummary(
            total_files=len(self.files),
            total_methods=total_methods,
            methods_added=total_added,
            methods_improved=total_improved,
            methods_skipped=total_skipped,
            template_count=template_count,
            heuristic_count=heuristic_count,
            llm_count=llm_count,
            llm_tokens_used=total_llm_tokens,
            elapsed_seconds=elapsed,
            errors=self.errors,
        )
