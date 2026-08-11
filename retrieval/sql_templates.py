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


# Bounded result cache (P4.14). Key includes analytics.duckdb mtime so a rebuild
# transparently invalidates stale entries. Data is static between ingests.
_SQL_CACHE = {}
_SQL_CACHE_MAX = 256


def clear_sql_cache():
    _SQL_CACHE.clear()


def _rows(tenant_id, sql, params=()):
    tid = tenant_id or DEFAULT_TENANT_ID
    path = _analytics_path(tid)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None
    key = (tid, mtime, sql, tuple(params))
    cached = _SQL_CACHE.get(key)
    if cached is not None:
        return cached

    con = get_analytics_connection(tid)
    try:
        cur = con.execute(sql, params)
        cols = [d[0] for d in con.description]
        result = (cur.fetchall(), cols)
    finally:
        con.close()

    if len(_SQL_CACHE) >= _SQL_CACHE_MAX:
        _SQL_CACHE.pop(next(iter(_SQL_CACHE)))
    _SQL_CACHE[key] = result
    return result


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


def student_count(tenant_id: str = None) -> dict:
    sql = "SELECT COUNT(DISTINCT roll_no) FROM exam_results"
    rows, _ = _rows(tenant_id, sql)
    n = rows[0][0]
    return {"answer": f"There are {n} students in the database.",
            "debug_sql": sql, "template": "student_count"}


def result_count(status: str = "PASS", tenant_id: str = None) -> dict:
    # DISTINCT (roll_no, result) so each student counts once regardless of how
    # many subject rows they have. status is code-controlled (PASS/FAIL).
    status = "FAIL" if str(status).upper().startswith("FAIL") else "PASS"
    sql = ("SELECT COUNT(*) FROM (SELECT DISTINCT roll_no, result FROM exam_results) "
           "WHERE result = ?")
    rows, _ = _rows(tenant_id, sql, (status,))
    n = rows[0][0]
    verb = "failed" if status == "FAIL" else "passed"
    return {"answer": f"{n} students {verb} their semester examination.",
            "debug_sql": sql, "template": "result_count"}


def bottom_by_sgpa(limit: int = 10, tenant_id: str = None) -> dict:
    sql = ("SELECT DISTINCT roll_no, name, sgpa FROM exam_results "
           "WHERE sgpa IS NOT NULL ORDER BY sgpa ASC, roll_no LIMIT ?")
    rows, _ = _rows(tenant_id, sql, (limit,))
    if not rows:
        return {"answer": "No SGPA data available.", "debug_sql": sql, "template": "bottom_by_sgpa"}
    lines = [f"Lowest {len(rows)} students by SGPA:"]
    for i, (roll, name, sgpa) in enumerate(rows, 1):
        lines.append(f"{i}. {name or 'Unknown'} (Roll: {roll}): SGPA {sgpa:.2f}")
    return {"answer": "\n".join(lines), "debug_sql": sql, "template": "bottom_by_sgpa"}


def count_sgpa_at_least(threshold: float, tenant_id: str = None) -> dict:
    sql = ("SELECT COUNT(*) FROM (SELECT DISTINCT roll_no, sgpa FROM exam_results "
           "WHERE sgpa IS NOT NULL) WHERE sgpa >= ?")
    rows, _ = _rows(tenant_id, sql, (threshold,))
    n = rows[0][0]
    if n == 0:
        return {"answer": f"No students have an SGPA of {threshold:g} or above.",
                "debug_sql": sql, "template": "count_sgpa_at_least"}
    return {"answer": f"{n} students have an SGPA of {threshold:g} or above.",
            "debug_sql": sql, "template": "count_sgpa_at_least"}


def supplementary_count(tenant_id: str = None) -> dict:
    sql = "SELECT COUNT(DISTINCT roll_no) FROM exam_results WHERE is_supply"
    rows, _ = _rows(tenant_id, sql)
    n = rows[0][0]
    if n == 0:
        return {"answer": "No students appeared for a supplementary examination.",
                "debug_sql": sql, "template": "supplementary_count"}
    return {"answer": f"{n} students appeared for a supplementary examination.",
            "debug_sql": sql, "template": "supplementary_count"}


# --------------------------------------------------------------------------
# Matcher
# --------------------------------------------------------------------------

_AT_LEAST_N = re.compile(r"(?:at\s*least|atleast|>=|minimum(?:\s+of)?|min)\s*(\d+)", re.I)
_N_OR_MORE = re.compile(r"(\d+)\s*(?:or\s+more|\+)\s*subject", re.I)
_TOP_N = re.compile(r"top\s+(\d+)", re.I)
_SUBJECT_CODE = re.compile(r"\bBT[A-Z]{2,5}\d{3}[A-Z]?\b", re.I)


def match_template(query: str):
    """Return (callable, kwargs) for a matched analytical template, else None."""
    q = query.lower()

    # queries naming specific subject codes (e.g. "compare BTCOE504A and
    # BTCOL506") are targeted comparisons, not requests for the full
    # per-subject ranking — let these fall through to LLM text-to-SQL
    # instead of being swallowed by subject_failure_counts below.
    named_subjects = _SUBJECT_CODE.findall(query)

    # if "subject" is mentioned before "fail", the question is scoped to
    # per-subject breakdown, not per-student — don't let the failed-most-
    # subjects branch below shadow subject_failure_counts.
    subject_asks_first = "subject" in q and "fail" in q and q.find("subject") < q.find("fail")

    # failed the most subjects
    if not subject_asks_first and ("fail" in q or "backlog" in q) and ("most" in q or "highest number" in q or "maximum" in q):
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
    if (not named_subjects and "subject" in q and "fail" in q
            and ("per" in q or "each" in q or "which" in q or "wise" in q or "count" in q)):
        return subject_failure_counts, {}

    # lowest / bottom students by SGPA (highest/top handled by toppers above)
    if ("lowest" in q or "bottom" in q or "worst" in q) and "sgpa" in q:
        m = _TOP_N.search(q)
        return bottom_by_sgpa, ({"limit": int(m.group(1))} if m else {})

    # count of students at/above an SGPA threshold (mirrors below_sgpa)
    if ("sgpa" in q and "subject" not in q and "fail" not in q
            and ("above" in q or "greater" in q or "or more" in q or "at least" in q or ">=" in q)
            and ("how many" in q or "number of" in q or "count" in q)):
        m = re.search(r"(\d+(?:\.\d+)?)", q)
        return count_sgpa_at_least, {"threshold": float(m.group(1)) if m else 9.0}

    # supplementary-exam student count
    if "supplement" in q and ("how many" in q or "number of" in q or "count" in q):
        return supplementary_count, {}

    # passed-student count (not the percentage/rate template above)
    if ("pass" in q and ("how many" in q or "number of" in q or "count of" in q)
            and "percent" not in q and "rate" not in q and "%" not in q):
        return result_count, {"status": "PASS"}

    # total student count
    if (("how many" in q or "number of" in q or "total" in q) and "student" in q
            and not any(w in q for w in ("fail", "subject", "sgpa", "pass", "below",
                                         "above", "supplement", "review", "backlog",
                                         "topper", "most", "least"))):
        return student_count, {}

    return None
