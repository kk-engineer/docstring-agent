from __future__ import annotations

import asyncio
import json

from ..llm import LLMClient
from ..logger import Logger
from ..models import MethodRecord
from ..prompts import DOCSTRING_BATCH_PROMPT
from .heuristic import HeuristicGenerator


class LLMGenerator:
    """Llmgenerator."""
    def __init__(self, llm: LLMClient, style: str, batch_size: int) -> None:
        """Initialise LLMGenerator."""
        self.llm = llm
        self.style = style
        self.batch_size = batch_size
        self.logger = Logger.get_instance()
        self._fallback_gen = HeuristicGenerator(style)

    async def generate_batch(self, records: list[MethodRecord]) -> list[MethodRecord]:
        """    Generate batch.

    Args:
        records (list[MethodRecord]): Description.

    Returns:
        list[MethodRecord]: Description.
    """
        n_batches = (len(records) + self.batch_size - 1) // self.batch_size
        for i in range(n_batches):
            start = i * self.batch_size
            end = start + self.batch_size
            batch = records[start:end]
            self.logger.notice(f"LLM batch {i + 1}/{n_batches}: {len(batch)} methods")
            await self._generate_one_batch(i, batch)
        return records

    async def _generate_one_batch(self, batch_idx: int, batch: list[MethodRecord]) -> None:
        """ generate one batch."""
        methods_json = []
        for r in batch:
            obj = {
                "qualified_name": r.qualified_name,
                "kind": r.kind,
                "params": [{"name": p.name, "annotation": p.annotation} for p in r.params],
                "return_annotation": r.return_annotation,
                "body": r.body_first_200[:800],
                "existing_docstring": r.existing_docstring,
            }
            methods_json.append(obj)

        prompt = DOCSTRING_BATCH_PROMPT.format(
            style=self.style,
            methods_json=json.dumps(methods_json, indent=2),
        )

        try:
            response = await self.llm.complete(prompt)
        except Exception as e:
            self.logger.warning(f"LLM batch {batch_idx} failed: {e}, using heuristic fallback")
            self._fallback(batch)
            return

        parsed = self._parse_response(response, batch)
        if parsed is None:
            self.logger.warning(f"Batch {batch_idx} JSON parse failed, using heuristic fallback")
            self._fallback(batch)
            return

        name_to_record = {r.qualified_name: r for r in batch}
        for entry in parsed:
            qname = entry.get("qualified_name")
            docstring = entry.get("docstring")
            if qname and docstring and qname in name_to_record:
                name_to_record[qname].generated_docstring = docstring

        for r in batch:
            if r.generated_docstring is None:
                self.logger.debug(
                    f"LLM fallback for {r.qualified_name}"
                )
                r.generated_docstring = self._fallback_gen.generate(r)

    def _parse_response(self, response: str, batch: list[MethodRecord]) -> list[dict] | None:
        """ parse response."""
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

    def _fallback(self, batch: list[MethodRecord]) -> None:
        """ fallback."""
        for r in batch:
            r.generated_docstring = self._fallback_gen.generate(r)

    def generate_sync(self, records: list[MethodRecord]) -> list[MethodRecord]:
        """    Generate sync.

    Args:
        records (list[MethodRecord]): Description.

    Returns:
        list[MethodRecord]: Description.
    """
        return asyncio.run(self.generate_batch(records))
