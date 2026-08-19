import asyncio
import logging
import re
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from retrieval.vector_search import VectorSearch
from retrieval.graph_traverse import GraphSearch
from retrieval.community_search import CommunitySearch
import httpx

import config
from utils.logging_config import setup_logging

setup_logging()

OLLAMA_API_URL = f"{config.OLLAMA_BASE_URL}/api/generate"
MODEL_NAME = config.OLLAMA_MODEL
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
        # Student-record shaped queries. Unambiguous multi-word phrases are matched
        # as plain substrings; the bare words "student"/"roll" are ambiguous (they
        # also appear in ordinary FACT/GLOBAL document questions, e.g. "student
        # mentorship program"), so those only count when paired with record/lookup
        # context (a roll number, or a record/marks/score/result/grade keyword).
        student_phrase_kw = ["score of", "result for", "search for"]
        roll_number_re = re.compile(r'\broll\s*(no\.?|number)?\s*[:#]?\s*\d{4,}\b', re.IGNORECASE)
        # A standalone 10+ digit run is a student roll number even without the
        # word "roll" (e.g. "Did student 23067571263053 pass?"). Roll numbers in
        # this corpus are 10-14 digits; nothing else in the domain is that long
        # (years are 4, amounts far shorter), so this is a safe deterministic
        # TABULAR signal. Closes the T20 route-flicker: without it, such queries
        # fell through to the non-deterministic LLM classifier.
        bare_roll_re = re.compile(r'\b\d{10,}\b')
        # "pass"/"passed" is added here (requires co-occurring "student") rather
        # than to agg_kw as a bare word: "pass" is too common to route on alone,
        # but "did STUDENT X pass" is unambiguously a record lookup.
        student_record_re = re.compile(
            r'\bstudent\b.*\b(record|marks|score|result|grade|sgpa|cgpa|roll|pass(?:ed)?)\b'
            r'|\b(record|marks|score|result|grade|sgpa|cgpa|pass(?:ed)?)\b.*\bstudent\b',
            re.IGNORECASE,
        )
        # Aggregation/analytical shaped queries — rule-based route to TABULAR BEFORE
        # any LLM classify call (P3.10). Deterministic + works with Ollama offline.
        agg_kw = [
            "how many", "how much", "list all", "list of student", "which students",
            "at least", "atleast", "or more", "average", "count of", "number of",
            "toppers", "topper", "pass percentage", "pass rate", "pass %",
            "failed", "fail", "below sgpa", "sgpa below", "most subjects", "backlog",
            "top ",
        ]
        is_tabular_kw = (
            any(k in lower_q for k in student_phrase_kw)
            or bool(roll_number_re.search(lower_q))
            or bool(bare_roll_re.search(lower_q))
            or bool(student_record_re.search(lower_q))
        )
        if is_tabular_kw or any(k in lower_q for k in agg_kw):
            return "TABULAR", None

        # Document-attribute phrasings — "authors of X", "affiliated with",
        # "established in", etc. These are attribute LOOKUPS (a property of one
        # named thing), not relational/aggregate queries, so they belong on the
        # FACT vector path. Route them deterministically BEFORE the LLM
        # classifier ever runs — the classifier was misrouting several of them
        # to LOCAL/TABULAR. Kept general (regex on the attribute phrase itself),
        # not tied to any specific golden question.
        fact_attr_re = re.compile(
            r"\bauthors?\s+of\b|\bauthored\s+by\b|\bwritten\s+by\b"
            r"|\baffiliated\s+with\b|\baffiliation\b"
            r"|\bestablished\s+in\b|\bfounded\s+(?:by|in)\b"
            r"|\blocated\s+in\b|\bbased\s+in\b"
            r"|\b(?:programs?|courses?)\s+offered\b"
            r"|\b(?:programs?|courses?)\b.{0,20}\boffers?\b"
            r"|\boffers?\b.{0,20}\b(?:programs?|courses?)\b",
            re.IGNORECASE,
        )
        if fact_attr_re.search(lower_q):
            return "FACT", None

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
            "options": {"num_ctx": 2048, "num_predict": 10, "temperature": 0}
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

    def _fact_context(self, query: str) -> str:
        # Retrieve deeper (k=10) to reduce recall misses, then keep the top
        # chunks that fit the 2048 num_ctx budget rather than dropping k back
        # to 3. ~5000 chars of context leaves room for the prompt template
        # and the 512-token answer within 2048 ctx. The first (best) chunk
        # is always included even if long.
        results = self.vs.search(query, top_k=10)
        parts, budget = [], 5000
        for r in results:
            c = r["content"]
            if parts and len(c) > budget:
                break
            parts.append(c)
            budget -= len(c)
        return "\n".join(parts)

    async def route_query(self, query: str):
        qtype, fallback_reason = await self.classify_query(query)
        logging.info(f"Query classified as: {qtype}")

        metadata = {"fallback_reason": fallback_reason} if fallback_reason else {}

        context = ""
        if qtype == "FACT":
            context = self._fact_context(query)
        elif qtype == "GLOBAL":
            context = self.cs.get_all_summaries()
        elif qtype == "LOCAL":
            # Link entities named in the QUESTION to graph nodes (the graph is
            # keyed by entity names, not source filenames), then return their
            # neighborhood. Deterministic; logs what matched so failures are
            # diagnosable. Falls back to vector content when nothing links.
            from retrieval.entity_link import link_entities

            nodes = list(self.gs.G.nodes()) if self.gs.G is not None else []
            matched, scores = link_entities(query, nodes)
            edges: list[str] = []
            for node in matched:
                for e in self.gs.get_neighborhood(node, hops=2):
                    if e not in edges:
                        edges.append(e)
                    if len(edges) >= 40:
                        break
                if len(edges) >= 40:
                    break
            metadata["linked_entities"] = matched
            logging.info("LOCAL entity-link: matched=%s edges=%d", matched, len(edges))
            if edges:
                context = "\n".join(edges)
            else:
                # entity absent from graph (coverage gap) -> degrade to FACT-like
                # vector context rather than returning empty.
                results = self.vs.search(query, top_k=3)
                context = "\n".join(r["content"] for r in results)
        elif qtype == "TABULAR" and config.TABULAR_FACT_FALLBACK and \
                not (config.tenant_dir(self.tenant_id) / "tabular.duckdb").exists():
            # Document-only tenant: no tabular.duckdb at all, so the entire TABULAR
            # route is void (every lookup would raise FileNotFoundError or return a
            # "no data" sentinel). Skip it and answer from the FACT vector path.
            # This is the dominant Phase-0 miss (31/66 FACT stresskit Qs land here).
            context = self._fact_context(query)
            metadata["tabular_fallback"] = "TABULAR->FACT (no tabular.duckdb)"
            qtype = "FACT"
            logging.info("TABULAR->FACT fallback: tenant has no tabular.duckdb")
        elif qtype == "TABULAR":
            from retrieval.tabular_queries import get_average_sgpa, count_failures, list_students_below_sgpa, get_student_record, get_student_by_name, generate_and_run_sql
            from retrieval.sql_templates import match_template
            from retrieval.intent import classify_tabular_intent

            # The tabular path can still fail on a tenant that HAS a db (empty result,
            # lookup error). Guard the block so those outcomes fall back too.
            try:
                # P3.12: try a deterministic parameterized template FIRST (no LLM,
                # works offline). Only unmatched patterns fall through to the cascade
                # / LLM text-to-SQL below.
                matched = match_template(query)
                if matched:
                    fn, kwargs = matched
                    result = await asyncio.to_thread(fn, tenant_id=self.tenant_id, **kwargs)
                    metadata["debug_sql"] = result.get("debug_sql")
                    metadata["template"] = result.get("template")
                    # A valid tabular answer (incl. a legitimate "no rows") wins; only
                    # an empty answer falls through to the FACT fallback.
                    if str(result.get("answer", "")).strip():
                        return qtype, result["answer"], metadata
                else:
                    intent = classify_tabular_intent(query)
                    if intent.kind == "name_search":
                        context = await get_student_by_name(query, self.tenant_id)
                    elif intent.kind == "dynamic_sql":
                        sql_result = await generate_and_run_sql(query, self.tenant_id)
                        context = sql_result["answer"]
                        metadata["debug_sql"] = sql_result["debug_sql"]
                    elif intent.kind == "average_sgpa":
                        context = get_average_sgpa(intent.params["subject"], self.tenant_id)
                    elif intent.kind == "count_failures":
                        context = count_failures(intent.params["subject"], self.tenant_id)
                    elif intent.kind == "below_sgpa":
                        context = list_students_below_sgpa(intent.params["threshold"], self.tenant_id)
                    elif intent.kind == "record_by_roll":
                        context = get_student_record(intent.params["roll"], self.tenant_id)
            except Exception as e:
                # No DB / lookup error — log the source name only, never a payload.
                logging.warning("TABULAR path failed (%s); fallback_enabled=%s",
                                type(e).__name__, config.TABULAR_FACT_FALLBACK)
                metadata["tabular_error"] = type(e).__name__
                context = ""

            # TABULAR-miss -> FACT fallback. Reassign qtype to FACT so the answer is
            # SYNTHESISED from the vector context (not returned raw) and the route is
            # honestly reported as FACT to the recovered question.
            if config.TABULAR_FACT_FALLBACK and not str(context).strip():
                context = self._fact_context(query)
                metadata["tabular_fallback"] = "TABULAR->FACT"
                qtype = "FACT"
                logging.info("TABULAR->FACT fallback engaged")

        return qtype, context, metadata

if __name__ == "__main__":
    import asyncio
    router = QueryRouter()
    # route_query is async and returns (qtype, context, metadata) — the old
    # smoke block called it synchronously and unpacked two values, so it always
    # crashed when run directly.
    qtype, ctx, meta = asyncio.run(router.route_query("What is RAG-MicroSim?"))
    print(f"Type: {qtype}\nContext: {str(ctx)[:200]}")
