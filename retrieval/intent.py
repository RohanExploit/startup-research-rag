"""Deterministic tabular-query intent classification, extracted from
retrieval/router.py so the routing decision is pure and unit-testable (no DB,
no LLM). route_query() dispatches on the returned intent; the decisions here
are byte-for-byte the same as the old inline if/elif cascade."""
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TabularIntent:
    kind: str                 # one of: name_search, dynamic_sql, average_sgpa,
                              # count_failures, below_sgpa, record_by_roll
    params: dict = field(default_factory=dict)


def classify_tabular_intent(query: str) -> TabularIntent:
    q_lower = query.lower()

    # Route to dynamic SQL generator for complex/list queries
    if "search for" in q_lower or "list all" in q_lower or "which students" in q_lower or "at least" in q_lower or "atleast" in q_lower:
        # If it is a simple single student name search
        if "search for" in q_lower and not ("fail" in q_lower or "sgpa" in q_lower or "subject" in q_lower or "grade" in q_lower or "sem" in q_lower):
            return TabularIntent("name_search")
        else:
            return TabularIntent("dynamic_sql")
    elif "average sgpa" in q_lower:
        match = re.search(r'subject\s+(BT\w+)', query, re.IGNORECASE)
        return TabularIntent("average_sgpa", {"subject": match.group(1) if match else None})
    elif "fail" in q_lower:
        if "how many" in q_lower or "count" in q_lower or "number" in q_lower:
            match = re.search(r'subject\s+(BT\w+)', query, re.IGNORECASE)
            return TabularIntent("count_failures", {"subject": match.group(1) if match else None})
        else:
            return TabularIntent("dynamic_sql")
    elif "below" in q_lower and "sgpa" in q_lower:
        # Pull the threshold tied to "below"/"under"/"sgpa" — not just the
        # first number in the query, which could be a semester or year
        # (e.g. "semester 3 students below 6 sgpa" must give 6, not 3).
        # Fall back to the first decimal, then a 6.0 default.
        match = (re.search(r'(?:below|under|sgpa)\D{0,10}(\d+(?:\.\d+)?)', q_lower)
                 or re.search(r'(\d+\.\d+)', query))
        threshold = float(match.group(1)) if match else 6.0
        return TabularIntent("below_sgpa", {"threshold": threshold})
    elif "record" in q_lower or "roll" in q_lower or "student" in q_lower or "score" in q_lower:
        match = re.search(r'(\d{10,15})', query)
        if match:
            return TabularIntent("record_by_roll", {"roll": match.group(1)})
        else:
            return TabularIntent("name_search")
    else:
        return TabularIntent("dynamic_sql")
