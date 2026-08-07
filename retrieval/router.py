import asyncio
import logging
from retrieval.vector_search import VectorSearch
from retrieval.graph_traverse import GraphSearch
from retrieval.community_search import CommunitySearch
import httpx

logging.basicConfig(level=logging.INFO)

OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen3:4b-instruct-2507-q4_K_M"
OLLAMA_KEEP_ALIVE = "10m"

_http_client = httpx.AsyncClient(timeout=60.0)

class QueryRouter:
    def __init__(self, tenant_id="tenant_1"):
        self.tenant_id = tenant_id
        self.vs = VectorSearch(tenant_id)
        self.gs = GraphSearch(tenant_id)
        self.cs = CommunitySearch(tenant_id)

    async def classify_query(self, query: str) -> str:
        # Deterministic override for student/tabular queries — skips the LLM
        # classify call entirely for the most common query shape (RTX2050 is
        # single-request-at-a-time on the 4B model, so every skipped call is
        # a full inference round-trip saved).
        lower_q = query.lower()
        # Student-record shaped queries
        student_kw = ["score of", "student", "roll", "result for", "search for"]
        # Aggregation/analytical shaped queries — rule-based route to TABULAR BEFORE
        # any LLM classify call (P3.10). Deterministic + works with Ollama offline.
        agg_kw = [
            "how many", "how much", "list all", "list of student", "which students",
            "at least", "atleast", "or more", "average", "count of", "number of",
            "toppers", "topper", "pass percentage", "pass rate", "pass %",
            "failed", "fail", "below sgpa", "sgpa below", "most subjects", "backlog",
            "top ",
        ]
        if any(k in lower_q for k in student_kw) or any(k in lower_q for k in agg_kw):
            return "TABULAR", None

        prompt = f"""
Classify the following query into one of four categories:
1. FACT: The user is asking for a specific fact, definition, or detail (e.g., "What is X?").
2. LOCAL: The user is asking about the relationships or connections of a specific entity (e.g., "Who works with X?").
3. GLOBAL: The user is asking for a high-level summary or broad theme across the dataset (e.g., "What are the main topics discussed?").
4. TABULAR: The user is asking aggregate/analytical questions (e.g., "how many", "average", "list all"), or asking for a specific student's record, score, or results by name or roll number.

Output ONLY the category name (FACT, LOCAL, GLOBAL, or TABULAR).
Query: "{query}"
        """
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {"num_ctx": 2048, "num_predict": 10}
        }
        try:
            response = await _http_client.post(OLLAMA_API_URL, json=payload)
            if response.status_code != 200:
                logging.error(f"Ollama returned status {response.status_code}: {response.text}")
            response.raise_for_status()
            cat = response.json()["response"].strip().upper()

            if "LOCAL" in cat: return "LOCAL", None
            if "GLOBAL" in cat: return "GLOBAL", None
            if "TABULAR" in cat: return "TABULAR", None
            return "FACT", None
        except httpx.HTTPStatusError as exc:
            fallback = f"ollama_exception:{type(exc).__name__}"
            logging.error(f"Router fallback triggered — Ollama HTTP status {exc.response.status_code}: {exc.response.text}. Defaulting to FACT. Query: {query}")
            return "FACT", fallback
        except httpx.RequestError as exc:
            fallback = f"ollama_exception:{type(exc).__name__}"
            logging.error(f"Router fallback triggered — Ollama connection/request error: {exc}. Defaulting to FACT. Query: {query}", exc_info=True)
            return "FACT", fallback
        except Exception as e:
            fallback = f"ollama_exception:{type(e).__name__}"
            logging.error(f"Router fallback triggered — Unexpected error: {e}. Defaulting to FACT. Query: {query}", exc_info=True)
            return "FACT", fallback

    async def route_query(self, query: str):
        qtype, fallback_reason = await self.classify_query(query)
        logging.info(f"Query classified as: {qtype}")
        
        metadata = {"fallback_reason": fallback_reason} if fallback_reason else {}
        
        context = ""
        if qtype == "FACT":
            results = self.vs.search(query, top_k=3)
            context = "\n".join([r["content"] for r in results])
        elif qtype == "GLOBAL":
            context = self.cs.get_all_summaries()
        elif qtype == "LOCAL":
            results = self.vs.search(query, top_k=1)
            if results:
                entity = results[0]["metadata"].get("source", "Unknown")
                edges = self.gs.get_neighborhood(entity, hops=1)
                context = "\n".join(edges)
        elif qtype == "TABULAR":
            import re
            from retrieval.tabular_queries import get_average_sgpa, count_failures, list_students_below_sgpa, get_student_record, get_student_by_name, generate_and_run_sql
            from retrieval.sql_templates import match_template
            q_lower = query.lower()

            # P3.12: try a deterministic parameterized template FIRST (no LLM,
            # works offline). Only unmatched patterns fall through to the cascade
            # / LLM text-to-SQL below.
            matched = match_template(query)
            if matched:
                fn, kwargs = matched
                result = await asyncio.to_thread(fn, tenant_id=self.tenant_id, **kwargs)
                metadata["debug_sql"] = result.get("debug_sql")
                metadata["template"] = result.get("template")
                return qtype, result["answer"], metadata

            # Route to dynamic SQL generator for complex/list queries
            if "search for" in q_lower or "list all" in q_lower or "which students" in q_lower or "at least" in q_lower or "atleast" in q_lower:
                # If it is a simple single student name search
                if "search for" in q_lower and not ("fail" in q_lower or "sgpa" in q_lower or "subject" in q_lower or "grade" in q_lower or "sem" in q_lower):
                    context = await get_student_by_name(query)
                else:
                    sql_result = await generate_and_run_sql(query)
                    context = sql_result["answer"]
                    metadata["debug_sql"] = sql_result["debug_sql"]
            elif "average sgpa" in q_lower:
                match = re.search(r'subject\s+(BT\w+)', query, re.IGNORECASE)
                context = get_average_sgpa(match.group(1) if match else None)
            elif "fail" in q_lower:
                if "how many" in q_lower or "count" in q_lower or "number" in q_lower:
                    match = re.search(r'subject\s+(BT\w+)', query, re.IGNORECASE)
                    context = count_failures(match.group(1) if match else None)
                else:
                    sql_result = await generate_and_run_sql(query)
                    context = sql_result["answer"]
                    metadata["debug_sql"] = sql_result["debug_sql"]
            elif "below" in q_lower and "sgpa" in q_lower:
                match = re.search(r'(\d+\.\d+|\d+)', query)
                context = list_students_below_sgpa(float(match.group(1)) if match else 6.0)
            elif "record" in q_lower or "roll" in q_lower or "student" in q_lower or "score" in q_lower:
                match = re.search(r'(\d{10,15})', query)
                if match:
                    context = get_student_record(match.group(1))
                else:
                    context = await get_student_by_name(query)
            else:
                sql_result = await generate_and_run_sql(query)
                context = sql_result["answer"]
                metadata["debug_sql"] = sql_result["debug_sql"]
                
        return qtype, context, metadata

if __name__ == "__main__":
    router = QueryRouter()
    qtype, ctx = router.route_query("What is RAG-MicroSim?")
    print(f"Type: {qtype}\nContext: {ctx[:200]}")
