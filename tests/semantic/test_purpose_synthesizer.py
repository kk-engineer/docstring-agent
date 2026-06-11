from src.semantic.purpose_models import PurposeFacts
from src.semantic.purpose_synthesizer import PurposeSynthesizer


def _facts(
    outcomes: list[str] | None = None,
    major_steps: list[str] | None = None,
    side_effects: list[str] | None = None,
) -> PurposeFacts:
    """     facts.

    Args:
        outcomes (list[str] | None): Outcomes.
        major_steps (list[str] | None): Major steps.
        side_effects (list[str] | None): Side effects.

    Returns:
        PurposeFacts: Description.
    """
    return PurposeFacts(
        outcomes=outcomes or [],
        major_steps=major_steps or [],
        side_effects=side_effects or [],
    )


class TestPurposeSynthesizer:
    """Testpurposesynthesizer."""
    def test_outcome_and_steps(self) -> None:
        """Test outcome and steps."""
        synth = PurposeSynthesizer()
        result = synth.synthesize(_facts(
            outcomes=["save orders"],
            major_steps=["validate orders", "enrich orders"],
        ))
        assert result == "Validate and enrich orders before saving."

    def test_outcome_only(self) -> None:
        """Test outcome only."""
        synth = PurposeSynthesizer()
        result = synth.synthesize(_facts(
            outcomes=["execute operation"],
        ))
        assert result == "Execute operation."

    def test_steps_only(self) -> None:
        """Test steps only."""
        synth = PurposeSynthesizer()
        result = synth.synthesize(_facts(
            major_steps=["authenticate", "authorize", "execute", "audit"],
        ))
        assert result == "Authenticate, authorize, execute, and audit."

    def test_side_effects_only(self) -> None:
        """Test side effects only."""
        synth = PurposeSynthesizer()
        result = synth.synthesize(_facts(
            side_effects=["publish events"],
        ))
        assert result == "Publish events to downstream consumers."

    def test_no_facts(self) -> None:
        """Test no facts."""
        synth = PurposeSynthesizer()
        result = synth.synthesize(_facts())
        assert result is None

    def test_humanized_steps(self) -> None:
        """Test humanized steps."""
        synth = PurposeSynthesizer()
        result = synth.synthesize(_facts(
            major_steps=[
                "fetch user",
                "transform user",
                "save user",
                "publish event",
            ],
        ))
        expected = (
            "Fetch user information, transform user information, "
            "save users, and publish events."
        )
        assert result == expected

    def test_single_step(self) -> None:
        """Test single step."""
        synth = PurposeSynthesizer()
        result = synth.synthesize(_facts(
            major_steps=["validate orders"],
        ))
        assert result == "Validate orders."
