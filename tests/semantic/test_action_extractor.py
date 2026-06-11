from src.semantic.action_extractor import SemanticActionExtractor


def _extract(body: str) -> list[tuple[str, str | None]]:
    """     extract.

    Args:
        body (str): Body.

    Returns:
        list[tuple[str, str | None]]: Description.
    """
    extractor = SemanticActionExtractor()
    actions = extractor.extract(body)
    return [(a.verb, a.obj) for a in actions]


class TestSemanticActionExtractor:
    """Testsemanticactionextractor."""
    def test_direct_calls(self) -> None:
        """Test direct calls."""
        actions = _extract("validate_orders(data)\nsave_orders(result)")
        assert actions == [("validate", "orders"), ("save", "orders")]

    def test_ignore_boilerplate(self) -> None:
        """Test ignore boilerplate."""
        actions = _extract(
            "logger.info('start')\n"
            "items.append(x)\n"
            "data.get('key')\n"
        )
        assert actions == []

    def test_attribute_call(self) -> None:
        """Test attribute call."""
        actions = _extract("client.fetch_user(uid)")
        assert actions == [("fetch", "user")]

    def test_consecutive_duplicates(self) -> None:
        """Test consecutive duplicates."""
        actions = _extract(
            "validate_orders(data)\n"
            "validate_orders(data)\n"
            "save_orders(result)\n"
        )
        assert actions == [("validate", "orders"), ("save", "orders")]

    def test_maximum_actions(self) -> None:
        """Test maximum actions."""
        body = "\n".join(f"action_{i}(x)" for i in range(10))
        actions = _extract(body)
        assert len(actions) <= 5

    def test_verb_only(self) -> None:
        """Test verb only."""
        actions = _extract("execute(cmd)")
        assert actions == [("execute", None)]

    def test_chained_attribute(self) -> None:
        """Test chained attribute."""
        actions = _extract("self.repository.save_order(order)")
        assert actions == [("save", "order")]

    def test_mixed_boilerplate_and_meaningful(self) -> None:
        """Test mixed boilerplate and meaningful."""
        body = (
            "logger.info('processing')\n"
            "validate_orders(data)\n"
            "items.append(result)\n"
            "save_orders(data)\n"
        )
        actions = _extract(body)
        assert actions == [("validate", "orders"), ("save", "orders")]

    def test_non_consecutive_repeat(self) -> None:
        """Test non consecutive repeat."""
        actions = _extract(
            "validate(x)\n"
            "save(x)\n"
            "validate(x)\n"
        )
        assert actions == [("validate", None), ("save", None), ("validate", None)]

    def test_empty_body(self) -> None:
        """Test empty body."""
        assert _extract("pass") == []

    def test_syntax_error_fallback(self) -> None:
        """Test syntax error fallback."""
        assert _extract("def broken(:") == []

    def test_call_order_preserved(self) -> None:
        """Test call order preserved."""
        actions = _extract(
            "fetch_user(uid)\n"
            "transform_user(data)\n"
            "save_user(data)\n"
            "publish_event(event)\n"
        )
        expected = [
            ("fetch", "user"),
            ("transform", "user"),
            ("save", "user"),
            ("publish", "event"),
        ]
        assert actions == expected
