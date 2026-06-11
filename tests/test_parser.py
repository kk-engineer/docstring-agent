from src.parser import CSTParser
from tests.conftest import SAMPLE_NO_DOCS, SAMPLE_WITH_DOCS, SAMPLE_COMPLEX


parser = CSTParser("google")


def test_parse_no_docs_fixture() -> None:
    """Test parse no docs fixture."""
    records = parser.parse_file(SAMPLE_NO_DOCS)
    assert len(records) > 0
    class_records = [r for r in records if r.kind == "class"]
    assert len(class_records) == 1
    assert class_records[0].qualified_name == "ConfigParser"

    method_names = {r.qualified_name for r in records if r.kind != "class"}
    assert "ConfigParser.__init__" in method_names
    assert "ConfigParser.get_config" in method_names
    assert "ConfigParser.validate_path" in method_names
    assert "ConfigParser.complex_parse" in method_names
    assert "ConfigParser.default_config" in method_names

    init = [r for r in records if r.qualified_name == "ConfigParser.__init__"][0]
    assert init.kind == "method"
    assert len(init.params) == 1
    assert init.params[0].name == "path"
    assert init.params[0].annotation is not None
    assert init.existing_docstring is None


def test_parse_with_docs_fixture() -> None:
    """Test parse with docs fixture."""
    records = parser.parse_file(SAMPLE_WITH_DOCS)
    init = [r for r in records if r.qualified_name == "ConfigParser.__init__"][0]
    assert init.existing_docstring is not None
    assert init.existing_docstring == "Init."


def test_parse_complex_fixture() -> None:
    """Test parse complex fixture."""
    records = parser.parse_file(SAMPLE_COMPLEX)
    assert len(records) == 1
    assert records[0].qualified_name == "deeply_nested"
    assert records[0].kind == "function"
    assert len(records[0].params) > 0
    assert records[0].body_first_200
    assert records[0].full_body


def test_parse_param_annotations() -> None:
    """Test parse param annotations."""
    records = parser.parse_file(SAMPLE_NO_DOCS)
    get_config = [r for r in records if r.qualified_name == "ConfigParser.get_config"][0]
    assert len(get_config.params) == 2
    key_param = get_config.params[0]
    assert key_param.name == "key"
    assert key_param.annotation == "str"
    default_param = get_config.params[1]
    assert default_param.name == "default"
    assert default_param.annotation == "Optional[Any]"


def test_parse_return_annotation() -> None:
    """Test parse return annotation."""
    records = parser.parse_file(SAMPLE_NO_DOCS)
    get_config = [r for r in records if r.qualified_name == "ConfigParser.get_config"][0]
    assert get_config.return_annotation is not None


def test_parse_static_method() -> None:
    """Test parse static method."""
    records = parser.parse_file(SAMPLE_NO_DOCS)
    default_config = [r for r in records if r.qualified_name == "ConfigParser.default_config"][0]
    assert default_config.kind == "staticmethod"
