from pathlib import Path

from src.audit.models import CoverageRecord, CoverageStatus, QualityScore
from src.audit.scorer import QualityScorer


def _make_record(
    existing_docstring: str | None = None,
    param_count: int = 0,
    has_return_annotation: bool = False,
    has_raise_statements: bool = False,
    cyclomatic_complexity: int = 1,
    qualified_name: str = "test_func",
) -> CoverageRecord:
    """     make record.

    Args:
        existing_docstring (str | None): Description.
        param_count (int): Description.
        has_return_annotation (bool): Description.
        has_raise_statements (bool): Description.
        cyclomatic_complexity (int): Description.
        qualified_name (str): Description.

    Returns:
        CoverageRecord: Description.
    """
    return CoverageRecord(
        file_path=Path("/fake/file.py"),
        qualified_name=qualified_name,
        kind="function",
        start_line=1,
        status=CoverageStatus.PRESENT if existing_docstring else CoverageStatus.MISSING,
        existing_docstring=existing_docstring,
        quality=None,
        cyclomatic_complexity=cyclomatic_complexity,
        param_count=param_count,
        has_return_annotation=has_return_annotation,
        has_raise_statements=has_raise_statements,
    )


class TestScoreSummary:
    """Testscoresummary."""
    def test_trivial_one_liner_low_score(self) -> None:
        """Test trivial one liner low score."""
        scorer = QualityScorer(0.65)
        record = _make_record(existing_docstring="Hi.")
        dim = scorer._score_summary("Hi.", record)
        assert dim.score == 0.5
        assert "Too short" in dim.reason

    def test_complete_sentence_full_score(self) -> None:
        """Test complete sentence full score."""
        scorer = QualityScorer(0.65)
        record = _make_record(existing_docstring="Parse the configuration file.")
        dim = scorer._score_summary("Parse the configuration file.", record)
        assert dim.score == 1.0
        assert "Good summary" in dim.reason

    def test_no_summary_zero_score(self) -> None:
        """Test no summary zero score."""
        scorer = QualityScorer(0.65)
        record = _make_record(existing_docstring="")
        dim = scorer._score_summary("", record)
        assert dim.score == 0.0
        assert "No summary" in dim.reason

    def test_placeholder_todo_zero_score(self) -> None:
        """Test placeholder todo zero score."""
        scorer = QualityScorer(0.65)
        record = _make_record(existing_docstring="TODO implement this")
        dim = scorer._score_summary("TODO implement this", record)
        assert dim.score == 0.0
        assert "Placeholder" in dim.reason


class TestScoreArgsCoverage:
    """Testscoreargscoverage."""
    def test_no_params_full_score(self) -> None:
        """Test no params full score."""
        scorer = QualityScorer(0.65)
        record = _make_record(existing_docstring="Do stuff.", param_count=0)
        dim = scorer._score_args_coverage("Do stuff.", record)
        assert dim.score == 1.0
        assert "N/A" in dim.reason

    def test_two_params_none_documented_zero_score(self) -> None:
        """Test two params none documented zero score."""
        scorer = QualityScorer(0.65)
        doc = """Do stuff.

        Returns:
            int: The result.
        """
        record = _make_record(existing_docstring=doc, param_count=2)
        dim = scorer._score_args_coverage(doc, record)
        assert dim.score == 0.0
        assert "no Args section" in dim.reason

    def test_two_params_both_documented_full_score(self) -> None:
        """Test two params both documented full score."""
        scorer = QualityScorer(0.65)
        doc = """Do stuff.

        Args:
            x (int): The first param.
            y (str): The second param.

        Returns:
            int: The result.
        """
        record = _make_record(existing_docstring=doc, param_count=2)
        dim = scorer._score_args_coverage(doc, record)
        assert dim.score == 1.0
        assert "2/2" in dim.reason

    def test_two_params_one_documented_partial_score(self) -> None:
        """Test two params one documented partial score."""
        scorer = QualityScorer(0.65)
        doc = """Do stuff.

        Args:
            x (int): The first param.
        """
        record = _make_record(existing_docstring=doc, param_count=2)
        dim = scorer._score_args_coverage(doc, record)
        assert dim.score == 0.5
        assert "1/2" in dim.reason


class TestScoreReturns:
    """Testscorereturns."""
    def test_no_return_annotation_full_score(self) -> None:
        """Test no return annotation full score."""
        scorer = QualityScorer(0.65)
        record = _make_record(existing_docstring="Do stuff.", has_return_annotation=False)
        dim = scorer._score_returns("Do stuff.", record)
        assert dim.score == 1.0
        assert "N/A" in dim.reason

    def test_return_annotation_missing_section_zero_score(self) -> None:
        """Test return annotation missing section zero score."""
        scorer = QualityScorer(0.65)
        doc = """Do stuff."""
        record = _make_record(existing_docstring=doc, has_return_annotation=True)
        dim = scorer._score_returns(doc, record)
        assert dim.score == 0.0
        assert "Missing Returns" in dim.reason

    def test_return_annotation_with_section_full_score(self) -> None:
        """Test return annotation with section full score."""
        scorer = QualityScorer(0.65)
        doc = """Do stuff.

        Returns:
            int: The result.
        """
        record = _make_record(existing_docstring=doc, has_return_annotation=True)
        dim = scorer._score_returns(doc, record)
        assert dim.score == 1.0
        assert "present" in dim.reason


class TestScoreSpecificity:
    """Testscorespecificity."""
    def test_placeholder_deduction(self) -> None:
        """Test placeholder deduction."""
        scorer = QualityScorer(0.65)
        record = _make_record(
            existing_docstring="This method does stuff.",
            cyclomatic_complexity=1,
        )
        dim = scorer._score_specificity("This method does stuff.", record)
        assert dim.score < 1.0

    def test_adequate_length_full_score(self) -> None:
        """Test adequate length full score."""
        scorer = QualityScorer(0.65)
        long_doc = "Parse the configuration file and return a dictionary of settings."
        record = _make_record(
            existing_docstring=long_doc,
            cyclomatic_complexity=1,
        )
        dim = scorer._score_specificity(long_doc, record)
        assert dim.score >= 0.9


class TestScoreRaises:
    """Testscoreraises."""
    def test_no_raises_full_score(self) -> None:
        """Test no raises full score."""
        scorer = QualityScorer(0.65)
        record = _make_record(existing_docstring="Do stuff.", has_raise_statements=False)
        dim = scorer._score_raises("Do stuff.", record)
        assert dim.score == 1.0
        assert "No raises" in dim.reason

    def test_raises_missing_section_zero_score(self) -> None:
        """Test raises missing section zero score."""
        scorer = QualityScorer(0.65)
        doc = """Do stuff."""
        record = _make_record(existing_docstring=doc, has_raise_statements=True)
        dim = scorer._score_raises(doc, record)
        assert dim.score == 0.0
        assert "Missing Raises" in dim.reason

    def test_raises_with_section_full_score(self) -> None:
        """Test raises with section full score."""
        scorer = QualityScorer(0.65)
        doc = """Do stuff.

        Raises:
            ValueError: If input is invalid.
        """
        record = _make_record(existing_docstring=doc, has_raise_statements=True)
        dim = scorer._score_raises(doc, record)
        assert dim.score == 1.0
        assert "present" in dim.reason


class TestComposite:
    """Testcomposite."""
    def test_weights_sum_to_one(self) -> None:
        """Test weights sum to one."""
        total = sum(QualityScorer.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_perfect_docstring_scores_high(self) -> None:
        """Test perfect docstring scores high."""
        scorer = QualityScorer(0.65)
        doc = """Parse the configuration file.

        Args:
            path (str): The file path.

        Returns:
            dict: Parsed config.
        """
        record = _make_record(
            existing_docstring=doc,
            param_count=1,
            has_return_annotation=True,
            cyclomatic_complexity=2,
        )
        qs = scorer.score(record)
        assert qs.composite > 0.8

    def test_missing_returns_drags_score(self) -> None:
        """Test missing returns drags score."""
        scorer = QualityScorer(0.65)
        doc = """Do stuff."""
        record = _make_record(
            existing_docstring=doc,
            param_count=0,
            has_return_annotation=True,
        )
        qs = scorer.score(record)
        assert qs.composite < 0.85

    def test_composite_manual_calculation(self) -> None:
        """Test composite manual calculation."""
        scorer = QualityScorer(0.65)
        doc = "Do stuff."
        record = _make_record(
            existing_docstring=doc,
            param_count=0,
            has_return_annotation=False,
            has_raise_statements=False,
            cyclomatic_complexity=1,
        )
        qs = scorer.score(record)
        # "Do stuff." has 9 chars → summary score 0.5 (short), specificity = (9/30 + 1.0)/2 = 0.65
        expected = (
            0.5 * 0.25        # summary
            + 1.0 * 0.25      # args_coverage (N/A)
            + 1.0 * 0.20      # returns (N/A)
            + 0.65 * 0.15     # specificity
            + 1.0 * 0.15      # raises (N/A)
        )
        assert abs(qs.composite - expected) < 0.01
