"""
Parameterized SQL templates for the top analytical queries (P3.12).

These run BEFORE any LLM SQL generation: deterministic, fast, and available
even when Ollama is down. All queries are parameterized SELECTs against the
read-only analytics.duckdb `exam_results` table (built by
ingestion/build_exam_results.py). No string interpolation of user input.

match_template(query) -> (fn, kwargs) | None  lets the router try a template
first and fall back to LLM text-to-SQL only for unmatched patterns.
"""
import re
import sys
from pathlib import Path

import duckdb

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import tenant_dir, DEFAULT_TENANT_ID


def _analytics_path(tenant_id: str) -> Path:
    return tenant_dir(tenant_id) / "analytics.duckdb"


def get_analytics_connection(tenant_id: str = None):
    """Read-only connection to analytics.duckdb; builds it once if missing."""
    tenant_id = tenant_id or DEFAULT_TENANT_ID
    path = _analytics_path(tenant_id)
    if not path.exists():
        from ingestion.build_exam_results import build_exam_results
        build_exam_results(tenant_id)
    return duckdb.connect(str(path), read_only=True)


def _rows(tenant_id, sql, params=()):
    con = get_analytics_connection(tenant_id)
    try:
        cur = con.execute(sql, params)
        cols = [d[0] for d in con.description]
        return cur.fetchall(), cols
    finally:
        con.close()


# --------------------------------------------------------------------------
# Templates  (each returns {"answer", "debug_sql", "template"})
# --------------------------------------------------------------------------

def students_failed_at_least(n: int, tenant_id: str = None) -> dict:
    sql = (
        "SELECT roll_no, name, COUNT(DISTINCT subject_code) AS failed_subjects "
        "FROM exam_results WHERE is_fail "
        "GROUP BY roll_no, name "
        "HAVING COUNT(DISTINCT subject_code) >= ? "
        "ORDER BY failed_subjects DESC, roll_no"
    )
    rows, _ = _rows(tenant_id, sql, (n,))
    if not rows:
        return {"answer": f"No students failed at least {n} subjects.",
                "debug_sql": sql, "template": "students_failed_at_least"}
    lines = [f"Found {len(rows)} students who failed at least {n} subjects:"]
    for roll, name, fails in rows:
        lines.append(f"- {name or 'Unknown'} (Roll: {roll}): {fails} subjects")
    return {"answer": "\n".join(lines), "debug_sql": sql, "template": "students_failed_at_least"}


def students_failed_most(limit: int = 10, tenant_id: str = None) -> dict:
    sql = (
        "SELECT roll_no, name, COUNT(DISTINCT subject_code) AS failed_subjects "
        "FROM exam_results WHERE is_fail "
        "GROUP BY roll_no, name "
        "ORDER BY failed_subjects DESC, roll_no "
        "LIMIT ?"
    )
    rows, _ = _rows(tenant_id, sql, (limit,))
    if not rows:
        return {"answer": "No failing students found.", "debug_sql": sql,
                "template": "students_failed_most"}
    top = rows[0][2]
    lines = [f"Students who failed the most subjects (max = {top}):"]
    for roll, name, fails in rows:
        lines.append(f"- {name or 'Unknown'} (Roll: {roll}): {fails} subjects")
    return {"answer": "\n".join(lines), "debug_sql": sql, "template": "students_failed_most"}


def pass_percentage(tenant_id: str = None) -> dict:
    sql = (
        "SELECT "
        "  100.0 * COUNT(*) FILTER (WHERE result = 'PASS') / NULLIF(COUNT(*), 0) AS pass_pct, "
        "  COUNT(*) FILTER (WHERE result = 'PASS') AS passed, "
        "  COUNT(*) AS total "
        "FROM (SELECT DISTINCT roll_no, result FROM exam_results)"
    )
    rows, _ = _rows(tenant_id, sql)
    pct, passed, total = rows[0]
    if pct is None:
        return {"answer": "No result data available.", "debug_sql": sql, "template": "pass_percentage"}
    return {"answer": f"Pass percentage: {pct:.1f}% ({passed} of {total} students passed).",
            "debug_sql": sql, "template": "pass_percentage"}


def toppers_by_sgpa(limit: int = 10, tenant_id: str = None) -> dict:
    sql = (
        "SELECT DISTINCT roll_no, name, sgpa FROM exam_results "
        "WHERE sgpa IS NOT NULL ORDER BY sgpa DESC, roll_no LIMIT ?"
    )
    rows, _ = _rows(tenant_id, sql, (limit,))
    if not rows:
        return {"answer": "No SGPA data available.", "debug_sql": sql, "template": "toppers_by_sgpa"}
    lines = [f"Top {len(rows)} students by SGPA:"]
    for i, (roll, name, sgpa) in enumerate(rows, 1):
        lines.append(f"{i}. {name or 'Unknown'} (Roll: {roll}): SGPA {sgpa:.2f}")
    return {"answer": "\n".join(lines), "debug_sql": sql, "template": "toppers_by_sgpa"}


def subject_failure_counts(limit: int = 50, tenant_id: str = None) -> dict:
    sql = (
        "SELECT subject_code, COUNT(*) FILTER (WHERE is_fail) AS fails "
        "FROM exam_results GROUP BY subject_code HAVING fails > 0 "
        "ORDER BY fails DESC, subject_code LIMIT ?"
    )
    rows, _ = _rows(tenant_id, sql, (limit,))
    if not rows:
        return {"answer": "No subject failures found.", "debug_sql": sql,
                "template": "subject_failure_counts"}
    lines = ["Failures per subject:"]
    for code, fails in rows:
        lines.append(f"- {code}: {fails} failures")
    return {"answer": "\n".join(lines), "debug_sql": sql, "template": "subject_failure_counts"}


# --------------------------------------------------------------------------
# Matcher
# --------------------------------------------------------------------------

_AT_LEAST_N = re.compile(r"(?:at\s*least|atleast|>=|minimum(?:\s+of)?|min)\s*(\d+)", re.I)
_N_OR_MORE = re.compile(r"(\d+)\s*(?:or\s+more|\+)\s*subject", re.I)
_TOP_N = re.compile(r"top\s+(\d+)", re.I)


def match_template(query: str):
    """Return (callable, kwargs) for a matched analytical template, else None."""
    q = query.lower()

    # failed the most subjects
    if ("fail" in q or "backlog" in q) and ("most" in q or "highest number" in q or "maximum" in q):
        return students_failed_most, {}

    # failed at least N subjects  (also "N or more subjects")
    if "fail" in q or "backlog" in q:
        m = _AT_LEAST_N.search(q) or _N_OR_MORE.search(q)
        if m:
            return students_failed_at_least, {"n": int(m.group(1))}

    # pass percentage / rate
    if ("pass" in q and ("percent" in q or "percentage" in q or "%" in q or "rate" in q)):
        return pass_percentage, {}

    # toppers / top N by sgpa
    if "topper" in q or ("top" in q and "sgpa" in q) or ("highest" in q and "sgpa" in q):
        m = _TOP_N.search(q)
        return toppers_by_sgpa, ({"limit": int(m.group(1))} if m else {})

    # per-subject failure counts
    if ("subject" in q and "fail" in q and ("per" in q or "each" in q or "which" in q or "wise" in q or "count" in q)):
        return subject_failure_counts, {}

    return None
