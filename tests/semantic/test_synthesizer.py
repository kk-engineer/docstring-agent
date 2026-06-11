from src.semantic.models import Action
from src.semantic.synthesizer import SummarySynthesizer


def _action(verb: str, obj: str | None = None, confidence: float = 0.95) -> Action:
    """     action.

    Args:
        verb (str): Verb.
        obj (str | None): Obj.
        confidence (float): Confidence.

    Returns:
        Action: Description.
    """
    return Action(verb=verb, obj=obj, source=f"{verb}_{obj}" if obj else verb, confidence=confidence)


class TestSummarySynthesizer:
    """Testsummarysynthesizer."""
    def test_zero_actions(self) -> None:
        """Test zero actions."""
        synth = SummarySynthesizer()
        assert synth.synthesize([]) is None

    def test_one_action(self) -> None:
        """Test one action."""
        synth = SummarySynthesizer()
        result = synth.synthesize([_action("validate", "orders")])
        assert result == "Validate orders."

    def test_two_actions(self) -> None:
        """Test two actions."""
        synth = SummarySynthesizer()
        result = synth.synthesize([
            _action("validate", "orders"),
            _action("save", "orders"),
        ])
        assert result == "Validate orders and save orders."

    def test_three_actions(self) -> None:
        """Test three actions."""
        synth = SummarySynthesizer()
        result = synth.synthesize([
            _action("validate", "orders"),
            _action("enrich", "orders"),
            _action("save", "orders"),
        ])
        assert result == "Validate orders, enrich orders, and save orders."

    def test_four_actions_oxford_comma(self) -> None:
        """Test four actions oxford comma."""
        synth = SummarySynthesizer()
        result = synth.synthesize([
            _action("authenticate", "user"),
            _action("authorize", "request"),
            _action("execute", "operation"),
            _action("audit", "entry"),
        ])
        assert result == "Authenticate user information, authorize requests, execute operations, and audit entries."

    def test_verb_only_action(self) -> None:
        """Test verb only action."""
        synth = SummarySynthesizer()
        result = synth.synthesize([_action("execute")])
        assert result == "Execute."

    def test_mixed_verb_and_obj(self) -> None:
        """Test mixed verb and obj."""
        synth = SummarySynthesizer()
        result = synth.synthesize([
            _action("execute"),
            _action("save", "report"),
        ])
        assert result == "Execute and save reports."
