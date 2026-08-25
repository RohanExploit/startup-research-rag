"""Regression tests for three TABULAR answers that were confidently wrong.

Each of these reached a live demo. They are pinned here because the failure mode
was not a crash but a plausible-looking wrong number, which no smoke test catches.
"""
import pytest

from retrieval.intent import classify_tabular_intent
from retrieval.sql_templates import match_template


class TestFailPercentage:
    """`WHERE result = 'FAIL'` before aggregating made the answer always 100%."""

    @pytest.mark.parametrize("q", [
        "What is the fail percentage?",
        "what is the failure rate",
        "fail percentage of students",
        "What % of students failed?",
    ])
    def test_routes_to_fail_percentage_template(self, q):
        matched = match_template(q)
        assert matched is not None, f"{q!r} fell through to LLM text-to-SQL"
        assert matched[0].__name__ == "fail_percentage"

    def test_pass_percentage_still_wins_for_pass_queries(self):
        assert match_template("What is the pass percentage?")[0].__name__ == "pass_percentage"

    def test_sql_does_not_filter_before_aggregating(self):
        """The denominator must be every student, not just the failing ones."""
        from retrieval import sql_templates
        import inspect
        src = inspect.getsource(sql_templates.fail_percentage)
        assert "FILTER (WHERE result = 'FAIL')" in src
        assert "WHERE result = 'FAIL'" not in src.split("FROM")[-1], \
            "a trailing WHERE would filter the denominator too"


class TestFailedAtLeastN:
    """Worded counts missed every template and fell through to a wrong LLM answer."""

    @pytest.mark.parametrize("q,n", [
        ("How many students failed two or more subjects?", 2),
        ("How many failed 2 or more subjects", 2),
        ("Number of students with more than one backlog", 2),
        ("students with multiple backlogs", 2),
        ("How many students failed at least three subjects?", 3),
        ("students failing more than 2 subjects", 3),
    ])
    def test_worded_and_digit_counts_both_match(self, q, n):
        matched = match_template(q)
        assert matched is not None, f"{q!r} fell through"
        fn, kwargs = matched
        assert fn.__name__ == "students_failed_at_least"
        assert kwargs["n"] == n

    def test_plain_fail_count_is_not_swallowed(self):
        """"How many students failed?" is still the student-level FAIL count."""
        fn, kwargs = match_template("How many students failed?")
        assert fn.__name__ == "result_count"
        assert kwargs["status"] == "FAIL"


class TestSingleStudentGpaLookup:
    """A named-student GPA question crashed with a DuckDB binder error."""

    @pytest.mark.parametrize("q", [
        "What is the CGPA of Priyanka Deshmukh Ramrao?",
        "cgpa of Rohan Vijay Gaikwad",
        "sgpa of HAJARE NIKHIL RAJENDRA",
    ])
    def test_named_gpa_query_uses_fuzzy_name_search(self, q):
        assert classify_tabular_intent(q).kind == "name_search"

    @pytest.mark.parametrize("q,kind", [
        ("students below 6 sgpa", "below_sgpa"),
        ("average sgpa", "average_sgpa"),
    ])
    def test_aggregate_gpa_queries_are_not_name_lookups(self, q, kind):
        assert classify_tabular_intent(q).kind == kind
