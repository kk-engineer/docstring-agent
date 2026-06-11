from __future__ import annotations

from ..audit.models import CoverageStatus
from ..config import Config
from ..logger import Logger, timed_step
from .models import PreserveGuard, RepairInstruction, RepairStrategy, RepairWorkItem


class RepairPlanner:
    """Repairplanner."""

    FAIL_THRESHOLD = 0.6
    SUMMARY_CRITICAL = 0.5
    DEFAULT_TOKEN_BUDGET = 50_000

    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = Logger.get_instance()
        self.repair_cfg = getattr(config, "repair", None)
        self.token_budget = (
            self.repair_cfg.token_budget if self.repair_cfg else self.DEFAULT_TOKEN_BUDGET
        )

    def plan(self, items: list[RepairWorkItem]) -> list[RepairWorkItem]:
        """    Plan.

    Args:
        items (list[RepairWorkItem]): Description.

    Returns:
        list[RepairWorkItem]: Description.
    """
        with timed_step("Plan Repairs", self.logger):
            for item in items:
                strategy = self._assign_strategy(item)
                item.strategy = strategy
                if strategy != RepairStrategy.SKIP:
                    self._build_instructions(item)
                    if strategy == RepairStrategy.SURGICAL_LLM:
                        self._build_guards(item)

            self._apply_budget_constraints(items)

            rows = []
            for item in items:
                if item.strategy == RepairStrategy.SKIP:
                    continue
                est = self._estimate_tokens(item)
                instr_count = len(item.instructions)
                rows.append([
                    item.method_record.file_path.name,
                    item.method_record.qualified_name,
                    item.strategy.value,
                    str(instr_count),
                    str(est),
                ])
            if rows:
                self.logger.print_table(
                    "Repair Plan",
                    ["File", "Method", "Strategy", "Instructions", "Est. Tokens"],
                    rows,
                )
            return items

    def _assign_strategy(self, item: RepairWorkItem) -> RepairStrategy:
        cr = item.coverage_record
        q = cr.quality

        if cr.status == CoverageStatus.PRESENT and (q is None or not q.below_threshold):
            return RepairStrategy.SKIP

        if cr.status == CoverageStatus.MISSING:
            return RepairStrategy.FULL_GENERATION

        if q is None:
            return RepairStrategy.HEURISTIC_PATCH

        summary_score = self._dim_score(q, "summary")
        args_score = self._dim_score(q, "args_coverage")
        specificity_score = self._dim_score(q, "specificity")

        failing_dims = self._failing_dimensions(q)
        failing_names = {d.dimension for d in failing_dims}
        structural = {"args_coverage", "returns", "raises"}
        only_structural = failing_names and failing_names.issubset(structural)

        if only_structural and summary_score >= 0.8 and specificity_score >= 0.65:
            return RepairStrategy.HEURISTIC_PATCH

        if summary_score < self.FAIL_THRESHOLD or specificity_score < self.FAIL_THRESHOLD:
            return RepairStrategy.SURGICAL_LLM

        if args_score < 0.5:
            return RepairStrategy.SURGICAL_LLM

        return RepairStrategy.HEURISTIC_PATCH

    def _build_instructions(self, item: RepairWorkItem) -> None:
        q = item.coverage_record.quality
        if q is None:
            return
        for d in q.dimensions:
            if d.score >= self.FAIL_THRESHOLD:
                continue
            severity = self._severity(d.score)
            action = self._action_text(d, item)
            item.instructions.append(
                RepairInstruction(dimension=d.name, action=action, severity=severity)
            )

    def _build_guards(self, item: RepairWorkItem) -> None:
        q = item.coverage_record.quality
        if q is None:
            return
        passed = [d for d in q.dimensions if d.score >= self.FAIL_THRESHOLD]
        templates = {
            "summary": "The summary line is good — preserve it exactly.",
            "args_coverage": "The Args section is complete — preserve all entries.",
            "returns": "The Returns section is correct — preserve it exactly.",
            "specificity": (
                "The description length and detail are appropriate — "
                "do not shorten or genericise."
            ),
            "raises": "The Raises section is accurate — preserve it exactly.",
        }
        for d in passed:
            text = templates.get(d.name, f"The {d.name} dimension is OK — preserve it.")
            item.guards.append(PreserveGuard(dimension=d.name, instruction=text))

    def _failing_dimensions(self, q) -> list[RepairInstruction]:
        result: list[RepairInstruction] = []
        for d in q.dimensions:
            if d.score < self.FAIL_THRESHOLD:
                result.append(
                    RepairInstruction(
                        dimension=d.name,
                        action=d.reason,
                        severity=self._severity(d.score),
                    )
                )
        return result

    def _dim_score(self, q, name: str) -> float:
        for d in q.dimensions:
            if d.name == name:
                return d.score
        return 1.0

    def _severity(self, score: float) -> str:
        if score < 0.3:
            return "critical"
        if score < self.FAIL_THRESHOLD:
            return "major"
        return "minor"

    def _action_text(self, dim, item) -> str:
        mr = item.method_record
        if dim.name == "summary":
            if dim.score < 0.3:
                return (
                    f"Rewrite the summary completely. Current issue: {dim.reason}. "
                    f"Write a precise one-sentence description of what this method "
                    f"does and why."
                )
            return (
                f"Improve the summary. Current issue: {dim.reason}. "
                f"Keep it concise but make it more informative."
            )
        if dim.name == "args_coverage":
            documented = self._count_documented(dim)
            return (
                f"Add documentation for the undocumented parameters. "
                f"Use the signature type annotations. Current issue: {dim.reason}."
            )
        if dim.name == "returns":
            ret = mr.return_annotation or "unknown"
            return (
                f"Add a Returns section documenting the return value. "
                f"The return annotation is: {ret}. Issue: {dim.reason}."
            )
        if dim.name == "specificity":
            if dim.score < 0.3:
                return (
                    f"The docstring is too sparse relative to this method's complexity "
                    f"(cyclomatic={mr.cyclomatic_complexity}). Expand the description "
                    f"with concrete details about the algorithm, key decisions, or edge "
                    f"cases visible in the code. Issue: {dim.reason}."
                )
            return (
                f"The docstring lacks specificity. Remove generic phrases and add "
                f"concrete details. Issue: {dim.reason}."
            )
        if dim.name == "raises":
            return (
                f"Add a Raises section. The method body contains raise statements. "
                f"Document each exception type that can be raised. Issue: {dim.reason}."
            )
        return f"Fix the {dim.name} section. Issue: {dim.reason}."

    def _count_documented(self, dim) -> int:
        try:
            parts = dim.reason.split("/")
            return int(parts[0])
        except (ValueError, IndexError):
            return 0

    def _apply_budget_constraints(self, items: list[RepairWorkItem]) -> None:
        surgical = [i for i in items if i.strategy == RepairStrategy.SURGICAL_LLM]
        total_est = sum(self._estimate_tokens(i) for i in surgical)

        if total_est <= self.token_budget:
            return

        surgical.sort(
            key=lambda x: (
                -x.method_record.cyclomatic_complexity,
                x.coverage_record.quality.composite if x.coverage_record.quality else 0,
            ),
            reverse=True,
        )

        downgraded = 0
        for item in surgical:
            if total_est <= self.token_budget:
                break
            item.strategy = RepairStrategy.HEURISTIC_PATCH
            total_est -= self._estimate_tokens(item)
            downgraded += 1

        if downgraded:
            self.logger.warning(
                f"Token budget ({self.token_budget}) exceeded: downgraded "
                f"{downgraded} methods from SURGICAL_LLM to HEURISTIC_PATCH."
            )

    def _estimate_tokens(self, item: RepairWorkItem) -> int:
        body_len = len(item.method_record.full_body)
        return body_len // 3 + 300
