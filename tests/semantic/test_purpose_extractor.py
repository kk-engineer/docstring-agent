from src.semantic.purpose_extractor import PurposeExtractor


def _extract(body: str):
    """     extract.

    Args:
        body (str): Body.
    """
    extractor = PurposeExtractor()
    return extractor.extract(body)


class TestPurposeExtractor:
    """Testpurposeextractor."""
    def test_return_outcome(self) -> None:
        """Test return outcome."""
        facts = _extract(
            "def f():\n"
            "    return save_orders(data)\n"
        )
        assert facts.outcomes == ["save orders"]
        assert facts.returned_entity == "orders"

    def test_assignment_pipeline(self) -> None:
        """Test assignment pipeline."""
        facts = _extract(
            "def f():\n"
            "    validated = validate_orders(data)\n"
            "    enriched = enrich_orders(validated)\n"
            "    return save_orders(enriched)\n"
        )
        assert "validate orders" in facts.major_steps
        assert "enrich orders" in facts.major_steps
        assert facts.outcomes == ["save orders"]

    def test_return_mapping(self) -> None:
        """Test return mapping."""
        facts = _extract(
            "def f():\n"
            "    return json.loads(text)\n"
        )
        assert facts.outcomes == ["parse JSON response"]
        assert facts.returned_entity == "JSON response"

    def test_logger_only(self) -> None:
        """Test logger only."""
        facts = _extract(
            "def f():\n"
            "    logger.info('start')\n"
            "    logger.debug('done')\n"
        )
        assert facts.outcomes == []
        assert facts.major_steps == []
        assert facts.side_effects == []

    def test_side_effects(self) -> None:
        """Test side effects."""
        facts = _extract(
            "def f():\n"
            "    session.commit()\n"
            "    publish(event)\n"
        )
        assert "commit" in facts.side_effects or "publish" in facts.side_effects
        assert len(facts.side_effects) == 2

    def test_empty_body(self) -> None:
        """Test empty body."""
        facts = _extract("pass")
        assert facts.outcomes == []
        assert facts.major_steps == []
        assert facts.side_effects == []

    def test_syntax_error_fallback(self) -> None:
        """Test syntax error fallback."""
        facts = _extract("def broken(:")
        assert facts.outcomes == []
        assert facts.major_steps == []

    def test_consecutive_dedup(self) -> None:
        """Test consecutive dedup."""
        facts = _extract(
            "def f():\n"
            "    validate(x)\n"
            "    validate(x)\n"
            "    save(x)\n"
        )
        steps = [s for s in facts.major_steps if s.startswith("validate")]
        assert len(steps) == 1

    def test_top_level_expressions(self) -> None:
        """Test top level expressions."""
        facts = _extract(
            "def f():\n"
            "    authenticate()\n"
            "    authorize()\n"
            "    execute()\n"
            "    audit()\n"
        )
        assert "authenticate" in facts.major_steps
        assert "authorize" in facts.major_steps
        assert "execute" in facts.major_steps
        assert "audit" in facts.major_steps

    def test_nested_side_effect_detected(self) -> None:
        """Test nested side effect detected."""
        facts = _extract(
            "def f():\n"
            "    try:\n"
            "        result = save_data(data)\n"
            "        session.commit()\n"
            "    except:\n"
            "        session.rollback()\n"
            "        raise\n"
        )
        # save_data is in assignment → major_step
        assert "save data" in facts.major_steps
        # commit inside try is a nested side effect
        assert "commit" in facts.side_effects
        # rollback inside except is a nested side effect
        assert "rollback" in facts.side_effects

    def test_nested_non_side_effect_ignored(self) -> None:
        """Test nested non side effect ignored."""
        facts = _extract(
            "def f():\n"
            "    if not self.path.exists():\n"
            "        return False\n"
            "    if not self.path.is_file():\n"
            "        return False\n"
            "    return True\n"
        )
        # exists/is_file are implementation details, not major steps
        for step in facts.major_steps:
            assert "exist" not in step
            assert "file" not in step
        # No side effects either
        assert facts.side_effects == []
        # No outcome (returns are constants)
        assert facts.outcomes == []

    def test_nested_publish_is_both_step_and_side_effect(self) -> None:
        """Test nested publish is both step and side effect."""
        facts = _extract(
            "def f():\n"
            "    if enabled:\n"
            "        publish(event)\n"
        )
        # publish is in top_exprs (it's Expr→Call inside if body) → major_step
        assert "publish" in facts.major_steps
        # publish is in _EVENT_VERBS → side effect
        assert "publish" in facts.side_effects
