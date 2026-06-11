from __future__ import annotations

from .purpose_models import PurposeFacts


class PurposeScorer:
    """Purposescorer."""
    def score(self, facts: PurposeFacts) -> None:
        """    Score.

    Args:
        facts (PurposeFacts): Facts.
    """
        s = 0.0
        if facts.outcomes:
            s += 0.5
        s += len(facts.major_steps) * 0.1
        s += len(facts.side_effects) * 0.1
        facts.confidence = min(s, 1.0)
