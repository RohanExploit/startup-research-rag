import asyncio
import duckdb
import sys
from pathlib import Path
import json
import re
import logging
import httpx
from rapidfuzz import process, fuzz, utils
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import tenant_dir

logger = logging.getLogger(__name__)

# NOTE: this module is single-tenant by design (module-level global). Defaults to
# tenant_1. Multi-tenant tabular needs a refactor to pass tenant_id per call.
db_path = str(tenant_dir("tenant_1") / "tabular.duckdb")

def get_connection():
    return duckdb.connect(db_path, read_only=True)

def get_average_sgpa(subject_code=None):
    """
    Returns the average SGPA. If a subject_code is provided, 
    returns the average SGPA of students who took that subject.
    """
    conn = get_connection()
    if subject_code:
        # Average SGPA of students taking this subject (they all might, but just in case)
        query = """
            SELECT AVG(s.sgpa) as avg_sgpa
            FROM students s
            JOIN student_subjects ss ON s.roll_no = ss.roll_no
            WHERE ss.subject_code = ? AND s.sgpa IS NOT NULL
        """
        res = conn.execute(query, (subject_code,)).fetchone()
    else:
        query = """
            SELECT AVG(sgpa) as avg_sgpa
            FROM students
            WHERE sgpa IS NOT NULL
        """
        res = conn.execute(query).fetchone()
        
    conn.close()
    if res and res[0] is not None:
        return f"The average SGPA is {res[0]:.2f}"
    return "Could not calculate average SGPA."

def count_failures(subject_code=None):
    """
    Counts the number of failed students overall or in a specific subject.
    """
    conn = get_connection()
    if subject_code:
        query = """
            SELECT COUNT(*) FROM student_subjects
            WHERE subject_code = ? AND grade IN ('FF', 'XX', 'AB')
        """
        res = conn.execute(query, (subject_code,)).fetchone()
        conn.close()
        return f"There are {res[0]} failures in subject {subject_code}."
    else:
        query = """
            SELECT COUNT(*) FROM students
            WHERE result = 'FAIL' OR result LIKE '%FAIL%'
        """
        res = conn.execute(query).fetchone()
        conn.close()
        return f"There are {res[0]} total failed students."

def list_students_below_sgpa(threshold: float):
    """
    Lists students with an SGPA strictly below the provided threshold.
    """
    conn = get_connection()
    query = """
        SELECT roll_no, name, sgpa 
        FROM students
        WHERE sgpa < ? AND sgpa IS NOT NULL
        ORDER BY sgpa ASC
    """
    results = conn.execute(query, (threshold,)).fetchall()
    conn.close()
    
    if not results:
        return f"No students found with SGPA below {threshold}."
        
    lines = [f"Found {len(results)} students with SGPA below {threshold}:"]
    for row in results:
        lines.append(f"- {row[1]} (Roll: {row[0]}): SGPA {row[2]:.2f}")
    return "\n".join(lines)

def get_student_record(roll_no: str):
    """
    Retrieves the complete record of a student given their roll number.
    """
    conn = get_connection()
    q_student = "SELECT name, sgpa, result, estimated_sgpa, total_marks, is_supply, seat_cancelled FROM students WHERE roll_no = ?"
    student = conn.execute(q_student, (roll_no,)).fetchone()
    
    if not student:
        conn.close()
        return f"Student with roll number {roll_no} not found."
        
    name, sgpa, result, est_sgpa, total_marks, is_supply, seat_cancelled = student
    
    q_subjects = "SELECT subject_code, grade, grade_point FROM student_subjects WHERE roll_no = ?"
    subjects = conn.execute(q_subjects, (roll_no,)).fetchall()
    conn.close()
    
    lines = [f"🎓 **Student Record for {name}**"]
    lines.append(f"🆔 Roll No: `{roll_no}`")
    
    res_emoji = "✅" if result == "PASS" else ("❌" if result == "FAIL" else "⚠️")
    lines.append(f"📊 Result: {res_emoji} {result}")
    
    sgpa_str = f"{sgpa:.2f}" if sgpa is not None else 'N/A'
    lines.append(f"📈 SGPA: **{sgpa_str}**")
    
    if is_supply:
        lines.append("🔖 Type: Supplementary Exam")
    if seat_cancelled:
        lines.append("🚫 Seat Cancelled")
        
    if total_marks is not None:
        lines.append(f"💯 Total Marks: {total_marks}")

    lines.append("\n📚 **Subjects:**")
    for sub in subjects:
        lines.append(f"  • `{sub[0]}`: Grade **{sub[1]}** (Point: {sub[2]})")
        
    return "\n".join(lines)

async def extract_student_identifier(raw_query: str) -> dict:
    """
    Uses the local LLM to extract student name or roll number from a natural language query.
    Returns: {"name": str|None, "roll_no": str|None}
    """
    prompt = f"""Extract the student name or roll number being asked about in this query. 
Respond with ONLY valid JSON, no other text.

Query: "{raw_query}"

Format: {{"name": "extracted name or null", "roll_no": "extracted roll number or null"}}"""
    
    payload = {
        "model": "qwen3:4b-instruct-2507-q4_K_M",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_ctx": 2048}
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post("http://127.0.0.1:11434/api/generate", json=payload)
            res.raise_for_status()
            text = res.json()["response"].strip()
            # Try to strip markdown code blocks if any
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            return {
                "name": data.get("name") if data.get("name") else None,
                "roll_no": data.get("roll_no") if data.get("roll_no") else None
            }
    except Exception as e:
        print(f"[DEBUG] Extraction failed: {e}")
        return {"name": None, "roll_no": None}

def fuzzy_find_student(extracted_name: str, all_db_names: list[tuple[str, str]], threshold: int = 75):
    """
    all_db_names is a list of tuples: (roll_no, name)
    Returns list of (roll_no, name, score) sorted by score descending.
    """
    names_only = [x[1] for x in all_db_names]
    matches = process.extract(extracted_name, names_only, scorer=fuzz.WRatio, processor=utils.default_process, limit=3)
    
    results = []
    for match_name, score, idx in matches:
        if score >= threshold:
            results.append((all_db_names[idx][0], match_name, score))
    return results

async def get_student_by_name(name_query: str):
    """
    Searches for a student by name using LLM extraction and rapidfuzz.
    """
    extracted = await extract_student_identifier(name_query)
    roll_no_ext = extracted.get("roll_no")
    name_ext = extracted.get("name")
    
    if roll_no_ext:
        return get_student_record(str(roll_no_ext))
        
    if not name_ext:
        return "Could not extract a valid student name or roll number from the query."
        
    conn = get_connection()
    
    # 1. Try robust tokenized search
    tokens = [t.strip() for t in name_ext.lower().split() if len(t.strip()) > 2]
    if tokens:
        query_parts = []
        params = []
        for token in tokens:
            query_parts.append("LOWER(name) LIKE ?")
            params.append(f"%{token}%")
        where_clause = " AND ".join(query_parts)
        sql = f"SELECT roll_no, name FROM students WHERE {where_clause} LIMIT 10"
        exact_matches = conn.execute(sql, params).fetchall()
        
        if len(exact_matches) == 1:
            conn.close()
            return get_student_record(exact_matches[0][0])
        elif len(exact_matches) > 1 and len(exact_matches) <= 3:
            # Disambiguate exact matches
            conn.close()
            lines = [f"Found {len(exact_matches)} students matching '{name_ext}':"]
            for idx, match in enumerate(exact_matches):
                lines.append(f"{idx+1}. {match[1]} (Roll: {match[0]})")
            lines.append("Reply with the roll number to confirm.")
            return "\n".join(lines)
            
    # Fallback to rapidfuzz
    all_students = conn.execute("SELECT roll_no, name FROM students").fetchall()
    conn.close()
    
    matches = fuzzy_find_student(name_ext, all_students, threshold=75)
    
    if not matches:
        return f"Student matching '{name_ext}' not found (highest match score was below threshold). Extracted as: {extracted}"
        
    # Check if we have a clear winner
    # A clear winner is either the only match above 75, or the top match is >90 and beats the runner-up by > 5 points
    is_clear_winner = False
    if len(matches) == 1 and matches[0][2] >= 75:
        is_clear_winner = True
    elif len(matches) > 1 and matches[0][2] >= 90 and (matches[0][2] - matches[1][2] > 5):
        is_clear_winner = True
        
    if is_clear_winner:
        return get_student_record(matches[0][0])
        
    # Disambiguation
    lines = [f"Did you mean one of these? (Extracted: '{name_ext}')"]
    for idx, match in enumerate(matches):
        lines.append(f"{idx+1}. {match[1]} (Roll: {match[0]}) - Match Score: {match[2]:.1f}")
    lines.append("Reply with the roll number to confirm.")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# SQL guardrail helpers
# ---------------------------------------------------------------------------

_STRIP_MD = re.compile(r'^```(?:sql)?\s*|\s*```$', re.IGNORECASE)
_MULTI_STMT = re.compile(r';\s*\S')  # semicolon followed by non-whitespace → 2nd statement
_LIMIT_MISSING = re.compile(r'\bLIMIT\b', re.IGNORECASE)
_UNBOUNDED_LIMIT = 200  # cap applied when the model omits LIMIT entirely
_QUERY_TIMEOUT_SECONDS = 10  # kill runaway scans on the 4GB-VRAM / shared-CPU box

# Only these tables/columns may appear in generated SQL — enforced deterministically,
# never by asking the LLM nicely (see researchdoneby web based claude.md, section D).
_ALLOWED_TABLES = {"students", "student_subjects"}
_TABLE_REF = re.compile(r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE)


def _check_table_allowlist(sql: str) -> str | None:
    """Returns a rejection reason if any FROM/JOIN targets a non-allowed table."""
    referenced = {m.group(1).lower() for m in _TABLE_REF.finditer(sql)}
    disallowed = referenced - _ALLOWED_TABLES
    if disallowed:
        return f"Guardrail: query references non-allowlisted table(s): {sorted(disallowed)}"
    return None


def _sanitize_sql(raw: str) -> tuple[str, str | None]:
    """
    Strip markdown fences, enforce a single SELECT statement over allowlisted tables.
    Returns (cleaned_sql, rejection_reason).  rejection_reason is None on success.
    """
    sql = _STRIP_MD.sub('', raw.strip()).strip()

    # Must start with SELECT
    if not sql.upper().lstrip().startswith('SELECT'):
        return sql, f"Guardrail: generated SQL does not start with SELECT (got: {sql[:80]!r})"

    # Must be a single statement (no second statement after a semicolon)
    stripped = sql.rstrip(';')
    if _MULTI_STMT.search(stripped):
        return sql, "Guardrail: multi-statement SQL rejected (only single SELECT allowed)"

    table_rejection = _check_table_allowlist(stripped)
    if table_rejection:
        return sql, table_rejection

    # Add a LIMIT cap if the model forgot one (prevents accidental full-table dumps)
    if not _LIMIT_MISSING.search(stripped):
        sql = stripped + f" LIMIT {_UNBOUNDED_LIMIT}"
        logger.info("SQL guardrail: no LIMIT found, capped at %d", _UNBOUNDED_LIMIT)

    return sql, None


def _execute_with_timeout(sql: str) -> tuple[list | None, list | None, str | None]:
    """Runs sql against a fresh read-only connection, interrupting it after
    _QUERY_TIMEOUT_SECONDS. Returns (rows, columns, error_message)."""
    conn = get_connection()
    result_holder: dict = {}

    def _run():
        try:
            result_holder["rows"] = conn.execute(sql).fetchall()
            result_holder["columns"] = [d[0] for d in conn.description]
        except Exception as e:
            result_holder["error"] = str(e)

    import threading
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(_QUERY_TIMEOUT_SECONDS)

    if t.is_alive():
        try:
            conn.interrupt()
        except Exception:
            pass
        t.join(2)
        conn.close()
        return None, None, f"Query timed out after {_QUERY_TIMEOUT_SECONDS}s"

    conn.close()
    if "error" in result_holder:
        return None, None, result_holder["error"]
    return result_holder["rows"], result_holder["columns"], None


_SQL_SCHEMA = '''
Table: students
- roll_no (VARCHAR, Primary Key)
- name (VARCHAR)
- sgpa (DOUBLE)
- estimated_sgpa (DOUBLE)
- total_marks (INTEGER)
- result (VARCHAR): e.g. "PASS", "FAIL"
- is_supply (BOOLEAN)
- seat_cancelled (BOOLEAN)

Table: student_subjects
- roll_no (VARCHAR, Foreign Key to students)
- subject_code (VARCHAR): e.g. 'BTCOC501', 'BTCOC502'.
  The first digit after the letter prefix indicates semester (e.g. 'BTCOC501' is sem 5).
  To match all sem-5 subjects use: subject_code LIKE 'BT%5%'
- credit (INTEGER)
- grade (VARCHAR): 'AA','AB','BB','BC','CC','CD','DD','EE','DE','FF','XX'.
  Failed grades: 'FF', 'XX', 'AB' (absent).
- grade_point (DOUBLE)
- raw_grade_string (VARCHAR)
'''

_SQL_GEN_RULES = (
    "You are a DuckDB SQL expert. Write ONE SQL SELECT query to answer the question below.\n"
    "Rules:\n"
    "- Output ONLY the raw SQL, no markdown, no explanation.\n"
    "- Must be a single SELECT statement.\n"
    "- Only use the tables `students` and `student_subjects` — no other tables exist.\n"
    "- Do NOT include LIMIT unless the question asks for a specific number.\n"
)


async def _ask_llm_for_sql(prompt: str) -> str | None:
    payload = {
        "model": "qwen3:4b-instruct-2507-q4_K_M",
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.0, "num_ctx": 2048},
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post("http://127.0.0.1:11434/api/generate", json=payload)
            res.raise_for_status()
            return res.json()["response"].strip()
    except Exception as e:
        logger.error("generate_and_run_sql: LLM call failed: %s", e)
        return None


async def generate_and_run_sql(raw_query: str) -> dict:
    """
    Uses LLM to generate DuckDB SQL for complex queries and executes it.
    On execution error, feeds the error back to the model once for a self-correction
    retry (execution-based self-correction — see researchdoneby web based claude.md, C.4).

    Returns a dict with:
      - answer (str): human-readable result or error
      - debug_sql (str | None): the exact SQL that was generated and run
        (or None / rejected SQL for auditability when guardrail fires)
    """
    prompt = (
        _SQL_GEN_RULES +
        "\nSchema:\n" + _SQL_SCHEMA +
        "\nQuestion: " + raw_query
    )

    raw_sql = await _ask_llm_for_sql(prompt)
    if raw_sql is None:
        return {"answer": "Failed to reach Ollama.", "debug_sql": None}

    sql, rejection = _sanitize_sql(raw_sql)
    if rejection:
        logger.warning("generate_and_run_sql REJECTED: %s | raw=%r", rejection, raw_sql)
        return {
            "answer": f"Query rejected by guardrail: {rejection}",
            "debug_sql": raw_sql,  # expose what the model generated for auditability
        }

    logger.info("generate_and_run_sql executing: %s", sql)
    results, columns, error = await asyncio.to_thread(_execute_with_timeout, sql)

    if error:
        logger.warning("generate_and_run_sql DB error, retrying once: %s | sql=%r", error, sql)
        retry_prompt = (
            _SQL_GEN_RULES +
            "\nSchema:\n" + _SQL_SCHEMA +
            "\nQuestion: " + raw_query +
            f"\n\nYour previous query failed with this error:\n{sql}\n-- error: {error}\n"
            "Fix the query and output ONLY the corrected raw SQL."
        )
        retry_raw_sql = await _ask_llm_for_sql(retry_prompt)
        if retry_raw_sql is not None:
            retry_sql, retry_rejection = _sanitize_sql(retry_raw_sql)
            if retry_rejection:
                return {
                    "answer": f"Query rejected by guardrail on retry: {retry_rejection}",
                    "debug_sql": retry_raw_sql,
                }
            logger.info("generate_and_run_sql retry executing: %s", retry_sql)
            results, columns, error = await asyncio.to_thread(_execute_with_timeout, retry_sql)
            sql = retry_sql

        if error:
            return {"answer": f"Error executing SQL: {error}", "debug_sql": sql}

    if not results:
        return {"answer": "Query returned no results.", "debug_sql": sql}

    # Format as markdown table (capped at 200 rows — already enforced by LIMIT above)
    header = "| " + " | ".join(columns) + " |"
    separator = "|" + "|".join(["---"] * len(columns)) + "|"
    rows = [
        "| " + " | ".join(str(x) if x is not None else "NULL" for x in row) + " |"
        for row in results
    ]
    table = header + "\n" + separator + "\n" + "\n".join(rows)
    if len(results) >= _UNBOUNDED_LIMIT:
        table += f"\n\n*(Capped at {_UNBOUNDED_LIMIT} rows)*"

    return {"answer": table, "debug_sql": sql}
