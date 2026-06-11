from pathlib import Path

from docstring_agent.generators.heuristic import HeuristicGenerator
from docstring_agent.generators.template import TemplateGenerator
from docstring_agent.models import MethodRecord, ParamInfo


def _record(
    name: str,
    kind: str = "method",
    params: list | None = None,
    return_ann: str | None = None,
) -> MethodRecord:
    """    Create a method record with the given name and kind.

    Args:
      name (str): The name of the method.
      kind (str): The kind of the method.
      params (list | None): The parameters of the method.
      return_ann (str | None): The return annotation of the method.

    Returns:
      A method record.
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
        full_body="pass\n",
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
        assert doc == "Validate input and raise on failure."

    def test_returns_section_google(self) -> None:
        """Test returns section google."""
        gen = HeuristicGenerator("google")
        doc = gen.generate(_record(
            "get_user",
            return_ann="dict",
        ))
        assert doc == "Return user."
