from __future__ import annotations

from radon.complexity import cc_visit

from .config import Config
from .logger import Logger
from .models import MethodRecord, RouteDecision


class Enricher:
    """Enricher."""
    def __init__(self, config: Config) -> None:
        """Initialise Enricher."""
        self.config = config
        self.ds_config = config.docstring_gen
        self.logger = Logger.get_instance()

    def enrich(self, records: list[MethodRecord]) -> list[MethodRecord]:
        """Enrich."""
        for record in records:
            self._compute_complexity(record)
            record.route = self._route(record)
            self.logger.debug(f"{record.qualified_name}: {record.route}")

        # Print routing summary table
        counts: dict[str, int] = {r.value: 0 for r in RouteDecision}
        for rec in records:
            counts[rec.route.value] += 1
        total = len(records)
        rows = []
        for route in RouteDecision:
            c = counts[route.value]
            pct = f"{c / total * 100:.1f}" if total else "0.0"
            rows.append([route.value, str(c), f"{pct}%"])
        self.logger.print_table("Routing Summary", ["Route", "Count", "% of total"], rows)

        return records

    def _compute_complexity(self, record: MethodRecord) -> None:
        """ compute complexity."""
        try:
            blocks = cc_visit(record.full_body)
            if blocks:
                record.cyclomatic_complexity = max(b.complexity for b in blocks)
            else:
                record.cyclomatic_complexity = 1
        except Exception:
            record.cyclomatic_complexity = 1

    def _route(self, record: MethodRecord) -> RouteDecision:
        """ route."""
        ds = self.ds_config
        qname = record.qualified_name
        name = qname.split(".")[-1] if "." in qname else qname

        # 1. SKIP: existing docstring and not improving
        if record.existing_docstring is not None and not ds.improve_existing:
            return RouteDecision.SKIP

        # 2. TEMPLATE: dunder methods
        if record.kind in ("method", "function") and name in ds.trivial_dunders:
            return RouteDecision.TEMPLATE

        # 3. TEMPLATE: trivial body
        body_lines = [line for line in record.full_body.splitlines() if line.strip()]
        if len(body_lines) <= 2 and record.cyclomatic_complexity == 1 and len(record.params) == 0:
            return RouteDecision.TEMPLATE

        # 4. HEURISTIC: trivial prefix
        for prefix in ds.trivial_prefixes:
            if name.startswith(prefix) and record.cyclomatic_complexity <= 2:
                return RouteDecision.HEURISTIC

        # 5. HEURISTIC: low complexity with good signature
        if (record.cyclomatic_complexity <= ds.complexity_threshold
                and len(record.params) <= 3
                and record.return_annotation is not None):
            return RouteDecision.HEURISTIC

        # 6. LLM: everything else
        return RouteDecision.LLM
