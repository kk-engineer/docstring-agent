from __future__ import annotations

import re
from typing import Optional

from ..logger import Logger, timed_step
from .models import CoverageRecord, CoverageStatus, QualityScore, ScoreDimension


class QualityScorer:

    WEIGHTS = {
        "summary": 0.25,
        "args_coverage": 0.25,
        "returns": 0.20,
        "specificity": 0.15,
        "raises": 0.15,
    }

    PLACEHOLDER_PATTERNS = [
        r"^TODO",
        r"^FIXME",
        r"^TBD",
        r"^placeholder",
        r"^This method",
        r"^This function",
        r"^This class",
        r"^\w+\.",
    ]

    def __init__(self, quality_threshold: float) -> None:
        self.quality_threshold = quality_threshold
        self.logger = Logger.get_instance()

    def score(self, record: CoverageRecord) -> QualityScore:
        doc = record.existing_docstring or ""
        dims: list[ScoreDimension] = [
            self._score_summary(doc, record),
            self._score_args_coverage(doc, record),
            self._score_returns(doc, record),
            self._score_specificity(doc, record),
            self._score_raises(doc, record),
        ]
        composite = sum(d.score * d.weight for d in dims)
        return QualityScore(
            composite=round(composite, 4),
            dimensions=dims,
            below_threshold=composite < self.quality_threshold,
            threshold=self.quality_threshold,
        )

    def score_batch(
        self, records: list[CoverageRecord]
    ) -> list[CoverageRecord]:
        with timed_step("Quality Scoring", self.logger):
            scorable = [r for r in records if r.status in (
                CoverageStatus.PRESENT, CoverageStatus.PARTIAL
            )]
            self.logger.info(f"Scoring {len(scorable)} documented methods")
            for record in scorable:
                record.quality = self.score(record)

            scored = [r for r in scorable if r.quality is not None]
            if scored:
                ranges = {"0.0-0.4": 0, "0.4-0.65": 0, "0.65-0.8": 0, "0.8-1.0": 0}
                for r in scored:
                    c = r.quality.composite  # type: ignore[union-attr]
                    if c < 0.4:
                        ranges["0.0-0.4"] += 1
                    elif c < 0.65:
                        ranges["0.4-0.65"] += 1
                    elif c < 0.8:
                        ranges["0.65-0.8"] += 1
                    else:
                        ranges["0.8-1.0"] += 1
                total_scored = len(scored)
                rows = []
                for rng, cnt in ranges.items():
                    pct = f"{cnt / total_scored * 100:.1f}" if total_scored else "0"
                    rows.append([rng, str(cnt), f"{pct}%"])
                self.logger.print_table(
                    "Score Distribution", ["Score range", "Count", "% of scored methods"], rows
                )

            flagged = [r for r in scored if r.quality and r.quality.below_threshold]
            self.logger.info(
                f"{len(flagged)} methods flagged below threshold {self.quality_threshold}"
            )

            for r in scored:
                if r.quality:
                    dim_scores = ",".join(
                        f"{d.name}={d.score:.2f}" for d in r.quality.dimensions
                    )
                    self.logger.debug(
                        f"{r.qualified_name}: score={r.quality.composite:.2f} [{dim_scores}]"
                    )

            return records

    def _score_summary(
        self, doc: str, record: CoverageRecord
    ) -> ScoreDimension:
        summary = self._get_summary_line(doc)
        if not summary:
            return ScoreDimension(
                name="summary", score=0.0, weight=self.WEIGHTS["summary"],
                reason="No summary line",
            )

        slen = len(summary)
        name = record.qualified_name.split(".")[-1]

        if slen < 10:
            return ScoreDimension(
                name="summary", score=0.5, weight=self.WEIGHTS["summary"],
                reason=f"Too short ({slen} chars)",
            )

        if re.match(r"^" + re.escape(name) + r"\s*\.?\s*$", summary):
            return ScoreDimension(
                name="summary", score=0.0, weight=self.WEIGHTS["summary"],
                reason="Name echo detected",
            )

        for pat in self.PLACEHOLDER_PATTERNS[:3]:
            if re.match(pat, summary):
                return ScoreDimension(
                    name="summary", score=0.0, weight=self.WEIGHTS["summary"],
                    reason="Placeholder text",
                )

        for pat in self.PLACEHOLDER_PATTERNS[3:6]:
            if re.match(pat, summary):
                return ScoreDimension(
                    name="summary", score=0.5, weight=self.WEIGHTS["summary"],
                    reason=f"Name echo openers",
                )

        if not summary.endswith((".", "!", "?")):
            return ScoreDimension(
                name="summary", score=0.5, weight=self.WEIGHTS["summary"],
                reason="No terminal punctuation",
            )

        return ScoreDimension(
            name="summary", score=1.0, weight=self.WEIGHTS["summary"],
            reason=f"Good summary ({slen} chars)",
        )

    def _score_args_coverage(
        self, doc: str, record: CoverageRecord
    ) -> ScoreDimension:
        if record.param_count == 0:
            return ScoreDimension(
                name="args_coverage", score=1.0, weight=self.WEIGHTS["args_coverage"],
                reason="No params - N/A",
            )

        has_section = bool(
            re.search(r"^\s*(Args|Arguments|Parameters):", doc, re.MULTILINE)
        )
        if not has_section:
            return ScoreDimension(
                name="args_coverage", score=0.0, weight=self.WEIGHTS["args_coverage"],
                reason=f"0/{record.param_count} params: no Args section",
            )

        documented = self._count_documented_params(doc)
        score = min(1.0, documented / record.param_count) if record.param_count > 0 else 1.0
        missing_count = record.param_count - documented
        if missing_count > 0:
            reason = (
                f"{documented}/{record.param_count} params documented "
                f"(missing: {missing_count})"
            )
        else:
            reason = f"{documented}/{record.param_count} params documented"
        return ScoreDimension(
            name="args_coverage", score=round(score, 4), weight=self.WEIGHTS["args_coverage"],
            reason=reason,
        )

    def _count_documented_params(self, doc: str) -> int:
        count = 0
        for line in doc.splitlines():
            stripped = line.strip()
            if re.match(r":param\s+\w+:", stripped):
                count += 1
            elif re.match(r"\w+\s*\([^)]*\):\s*", stripped):
                count += 1
        return count

    def _score_returns(
        self, doc: str, record: CoverageRecord
    ) -> ScoreDimension:
        if not record.has_return_annotation:
            return ScoreDimension(
                name="returns", score=1.0, weight=self.WEIGHTS["returns"],
                reason="No return annotation - N/A",
            )

        has_section = bool(
            re.search(r"^\s*(Returns|Return):", doc, re.MULTILINE)
        )
        if has_section:
            return ScoreDimension(
                name="returns", score=1.0, weight=self.WEIGHTS["returns"],
                reason="Returns section present",
            )
        return ScoreDimension(
            name="returns", score=0.0, weight=self.WEIGHTS["returns"],
            reason="Missing Returns section",
        )

    def _score_specificity(
        self, doc: str, record: CoverageRecord
    ) -> ScoreDimension:
        stripped = doc.strip()
        doc_len = len(stripped)
        complexity = record.cyclomatic_complexity
        expected_min = max(30, complexity * 15)
        ratio = min(1.0, doc_len / expected_min)
        score_A = ratio

        matches = 0
        for line in stripped.splitlines():
            for pat in self.PLACEHOLDER_PATTERNS:
                if re.match(pat, line.strip()):
                    matches += 1
                    break
        score_B = max(0.0, 1.0 - (matches * 0.25))

        final = (score_A + score_B) / 2
        if final >= 0.95:
            reason = "Doc length OK, no placeholders"
        elif score_A < 0.8:
            reason = f"Too short ({doc_len} chars, expected {expected_min})"
        else:
            reason = f"{matches} placeholder phrases detected"
        return ScoreDimension(
            name="specificity", score=round(final, 4), weight=self.WEIGHTS["specificity"],
            reason=reason,
        )

    def _score_raises(
        self, doc: str, record: CoverageRecord
    ) -> ScoreDimension:
        if not record.has_raise_statements:
            return ScoreDimension(
                name="raises", score=1.0, weight=self.WEIGHTS["raises"],
                reason="No raises - N/A",
            )

        has_section = bool(
            re.search(r"^\s*(Raises|Raise):", doc, re.MULTILINE)
        )
        if has_section:
            return ScoreDimension(
                name="raises", score=1.0, weight=self.WEIGHTS["raises"],
                reason="Raises section present",
            )
        return ScoreDimension(
            name="raises", score=0.0, weight=self.WEIGHTS["raises"],
            reason="Missing Raises section (raise found in body)",
        )

    def _get_summary_line(self, doc: str) -> str:
        for line in doc.splitlines():
            line = line.strip()
            if line:
                return line
        return ""
