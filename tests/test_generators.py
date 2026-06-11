from pathlib import Path

from src.generators.heuristic import HeuristicGenerator
from src.generators.template import TemplateGenerator
from src.models import MethodRecord, ParamInfo


def _record(
    name: str,
    kind: str = "method",
    params: list | None = None,
    return_ann: str | None = None,
    full_body: str | None = None,
) -> MethodRecord:
    """     record.

    Args:
        name (str): Name of the entity.
        kind (str): Kind.
        params (list | None): Parameters used by the operation.
        return_ann (str | None): Return ann.
        full_body (str | None): Full body.

    Returns:
        MethodRecord: Description.
    """
    return MethodRecord(
        file_path=Path("test.py"),
        qualified_name=name,
        kind=kind,
        params=params or [],
        return_annotation=return_ann,
        start_line=1,
        end_line=5,
        body_first_200="pass",
        full_body=full_body or "pass\n",
        existing_docstring=None,
    )


class TestTemplateGenerator:
    """Testtemplategenerator."""
    def test_init(self) -> None:
        """Test init."""
        gen = TemplateGenerator("google")
        doc = gen.generate(_record("__init__"))
        assert "Initialise" in doc

    def test_str(self) -> None:
        """Test str."""
        gen = TemplateGenerator("google")
        doc = gen.generate(_record("__str__"))
        assert "Return a string representation" in doc

    def test_unknown_method(self) -> None:
        """Test unknown method."""
        gen = TemplateGenerator("google")
        doc = gen.generate(_record("do_something"))
        assert "Do something" in doc

    def test_with_params_google(self) -> None:
        """Test with params google."""
        gen = TemplateGenerator("google")
        doc = gen.generate(_record(
            "set_value",
            params=[ParamInfo(name="key", annotation="str"), ParamInfo(name="value")],
            return_ann="None",
        ))
        assert "Set value." in doc
        assert "Args" not in doc

    def test_with_params_numpy(self) -> None:
        """Test with params numpy."""
        gen = TemplateGenerator("numpy")
        doc = gen.generate(_record(
            "set_value",
            params=[ParamInfo(name="key", annotation="str")],
        ))
        assert doc == "Set value."

    def test_with_params_sphinx(self) -> None:
        """Test with params sphinx."""
        gen = TemplateGenerator("sphinx")
        doc = gen.generate(_record(
            "set_value",
            params=[ParamInfo(name="key", annotation="str")],
            return_ann="bool",
        ))
        assert doc == "Set value."


class TestHeuristicGenerator:
    """Testheuristicgenerator."""
    def test_parse_prefix(self) -> None:
        """Test parse prefix."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record("parse_config"))
        assert "Parse" in doc
        assert "config" in doc
        assert "return the result" in doc

    def test_validate_prefix(self) -> None:
        """Test validate prefix."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record("validate_input"))
        assert "Validate" in doc
        assert "raise on failure" in doc

    def test_fetch_prefix(self) -> None:
        """Test fetch prefix."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record("fetch_user_data"))
        assert "Fetch" in doc
        assert "from the source" in doc

    def test_compute_prefix(self) -> None:
        """Test compute prefix."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record("compute_average"))
        assert "Compute" in doc

    def test_build_prefix(self) -> None:
        """Test build prefix."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record("build_response"))
        assert "Build and return a" in doc

    def test_is_prefix(self) -> None:
        """Test is prefix."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record("is_valid"))
        assert "Return True if" in doc

    def test_get_prefix(self) -> None:
        """Test get prefix."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record("get_user"))
        assert "Return" in doc

    def test_set_prefix(self) -> None:
        """Test set prefix."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record("set_name"))
        assert "Set" in doc

    def test_default_name(self) -> None:
        """Test default name."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record("do_something"))
        assert doc.startswith("Do something")

    def test_args_section_google(self) -> None:
        """Test args section google."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record(
            "validate_input",
            params=[ParamInfo(name="data", annotation="str")],
        ))
        assert "Validate input and raise on failure." in doc
        assert "Args:" in doc
        assert "data (str): Input data to process." in doc

    def test_returns_section_google(self) -> None:
        """Test returns section google."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record(
            "get_user",
            return_ann="dict",
        ))
        assert "Return user." in doc
        assert "Returns:" in doc
        assert "dict: Description." in doc

    def test_semantic_summary_process_orders(self) -> None:
        """Test semantic summary process orders."""
        body = (
            "def process_orders(orders):\n"
            "    validated = validate_orders(orders)\n"
            "    enriched = enrich_orders(validated)\n"
            "    return save_orders(enriched)\n"
        )
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record(
            "process_orders",
            full_body=body,
        ))
        assert doc.startswith("Validate and enrich orders before saving.")

    def test_semantic_summary_logger_only_fallback(self) -> None:
        """Test semantic summary logger only fallback."""
        body = (
            "def do_something(data):\n"
            "    logger.info('start')\n"
            "    logger.debug('processing')\n"
            "    logger.info('done')\n"
        )
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record(
            "do_something",
            full_body=body,
        ))
        assert doc.startswith("Do something.")

    def test_semantic_summary_ast_failure_fallback(self) -> None:
        """Test semantic summary ast failure fallback."""
        body = "def broken(:\n"
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record(
            "do_something",
            full_body=body,
        ))
        assert doc.startswith("Do something.")

    def test_semantic_summary_verb_only_actions(self) -> None:
        """Test semantic summary verb only actions."""
        body = (
            "def process():\n"
            "    authenticate()\n"
            "    authorize()\n"
            "    execute()\n"
            "    audit()\n"
        )
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record(
            "process",
            full_body=body,
        ))
        assert doc.startswith("Authenticate, authorize, execute, and audit.")

    def test_semantic_summary_crud_workflow(self) -> None:
        """Test semantic summary crud workflow."""
        body = (
            "def crud_workflow():\n"
            "    fetch_user(uid)\n"
            "    transform_user(data)\n"
            "    save_user(data)\n"
            "    publish_event(event)\n"
        )
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record(
            "crud_workflow",
            full_body=body,
        ))
        expected = (
            "Fetch user information, transform user information, "
            "save users, and publish events."
        )
        assert doc.startswith(expected)

    def test_semantic_summary_empty_body_fallback(self) -> None:
        """Test semantic summary empty body fallback."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record(
            "do_something",
            full_body="",
        ))
        assert doc.startswith("Do something.")
