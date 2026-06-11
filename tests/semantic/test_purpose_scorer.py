from src.semantic.purpose_models import PurposeFacts
from src.semantic.scoring import PurposeScorer


class TestPurposeScorer:
    """Testpurposescorer."""
    def test_outcome_scores_half(self) -> None:
        """Test outcome scores half."""
        facts = PurposeFacts(outcomes=["save"])
        scorer = PurposeScorer()
        scorer.score(facts)
        assert facts.confidence == 0.5

    def test_steps_score_point_one_each(self) -> None:
        """Test steps score point one each."""
        facts = PurposeFacts(major_steps=["a", "b", "c"])
        scorer = PurposeScorer()
        scorer.score(facts)
        assert abs(facts.confidence - 0.3) < 1e-9

    def test_side_effects_score_point_one_each(self) -> None:
        """Test side effects score point one each."""
        facts = PurposeFacts(side_effects=["x", "y"])
        scorer = PurposeScorer()
        scorer.score(facts)
        assert facts.confidence == 0.2

    def test_caps_at_one(self) -> None:
        """Test caps at one."""
        facts = PurposeFacts(
            outcomes=["save"],
            major_steps=["a", "b", "c", "d", "e", "f"],
            side_effects=["x", "y", "z"],
        )
        scorer = PurposeScorer()
        scorer.score(facts)
        assert facts.confidence == 1.0

    def test_combined_score(self) -> None:
        """Test combined score."""
        facts = PurposeFacts(
            outcomes=["save"],
            major_steps=["validate", "enrich"],
        )
        scorer = PurposeScorer()
        scorer.score(facts)
        assert facts.confidence == 0.7

    def test_no_facts_zero(self) -> None:
        """Test no facts zero."""
        facts = PurposeFacts()
        scorer = PurposeScorer()
        scorer.score(facts)
        assert facts.confidence == 0.0
