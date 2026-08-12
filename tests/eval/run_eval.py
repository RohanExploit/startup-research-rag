"""
Golden-set evaluation runner (Phase 1 / CR3).

Runs each question in golden_set.json through the LIVE retrieval system exactly
as the API does (retrieval.router.QueryRouter + generation.answer), scores the
answer against a hand-verified gold, and reports per-route + overall accuracy.

Standalone (not a pytest test) so it can run against the real tenant_1 corpus
without the audit/ conftest import chain. Read-only: never writes tenant data.

Usage:
    python tests/eval/run_eval.py                      # full run, prints report
    python tests/eval/run_eval.py --out baseline.json  # also dump machine result
    python tests/eval/run_eval.py --limit 5            # first N questions (smoke)

Scoring modes (per question `gold.mode`):
    contains      answer must contain EVERY string in gold.expect (case-insensitive)
    contains_any  answer must contain AT LEAST ONE string in gold.expect
    insufficient  answer must signal missing evidence ("don't have enough", etc.)
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from retrieval.router import QueryRouter          # noqa: E402
from generation.answer import generate_answer     # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden_set.json"
# Heuristic markers of an "I can't answer that" refusal. Substring match, so it
# can over-fire on a long answer that merely quotes one of these phrases — an
# accepted limitation of a keyword scorer; keep the phrases refusal-specific.
_INSUFFICIENT_MARKERS = (
    "don't have enough", "do not have enough", "insufficient",
    "not enough information", "no information", "cannot find", "not found",
    "no student", "no matching", "no record", "no such", "does not exist",
    "not exist", "could not extract", "no results",
)


def score(answer: str, gold: dict) -> bool:
    a = (answer or "").lower()
    mode = gold["mode"]
    expect = [str(x).lower() for x in gold.get("expect", [])]
    if mode == "contains":
        return all(e in a for e in expect)
    if mode == "contains_any":
        return any(e in a for e in expect)
    if mode == "insufficient":
        return any(m in a for m in _INSUFFICIENT_MARKERS)
    raise ValueError(f"unknown gold.mode: {mode}")


async def answer_for(router: QueryRouter, query: str) -> tuple[str, str]:
    """Mirror api/main.py: route -> (TABULAR short-circuit | LLM synthesis)."""
    qtype, context, _meta = await router.route_query(query)
    context_text = str(context).strip()
    if not context_text:
        return qtype, "I don't have enough information to answer that."
    if qtype == "TABULAR":
        return qtype, context_text
    return qtype, await generate_answer(query, context, qtype)


async def run(golden_path: Path, limit: int | None):
    spec = json.loads(golden_path.read_text(encoding="utf-8"))
    questions = spec["questions"][: limit or None]
    tenant_id = spec.get("tenant_id", "tenant_1")
    router = QueryRouter(tenant_id)

    per_route = {}   # route -> [correct, total]
    route_hits = 0   # classifier routed to the expected route
    rows = []
    for q in questions:
        exp_route = q["route"]
        try:
            got_route, answer = await answer_for(router, q["query"])
        except Exception as e:
            got_route, answer = "ERROR", f"<exception: {e}>"
        ok = score(answer, q["gold"]) if got_route != "ERROR" else False
        route_ok = got_route == exp_route
        route_hits += int(route_ok)
        pr = per_route.setdefault(exp_route, [0, 0])
        pr[0] += int(ok)
        pr[1] += 1
        rows.append({
            "id": q["id"], "route": exp_route, "routed_as": got_route,
            "route_ok": route_ok, "answer_ok": ok,
            "query": q["query"], "answer": answer[:300],
        })
        print(f"  [{'PASS' if ok else 'FAIL'}] {q['id']} {exp_route}"
              f"{'' if route_ok else f'(routed {got_route})'}: {q['query'][:60]}")

    total_ok = sum(p[0] for p in per_route.values())
    total = sum(p[1] for p in per_route.values())
    summary = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "golden_version": spec.get("version"),
        "tenant_id": tenant_id,
        "overall_accuracy": round(total_ok / total, 4) if total else 0.0,
        "route_classification_accuracy": round(route_hits / total, 4) if total else 0.0,
        "n": total,
        "per_route": {r: {"correct": c, "total": t, "accuracy": round(c / t, 4) if t else 0.0}
                      for r, (c, t) in sorted(per_route.items())},
    }
    print("\n=== EVAL SUMMARY ===")
    print(f"overall answer accuracy: {summary['overall_accuracy']:.1%}  ({total_ok}/{total})")
    print(f"route classification acc: {summary['route_classification_accuracy']:.1%}")
    for r, s in summary["per_route"].items():
        print(f"  {r:8s} {s['accuracy']:.1%}  ({s['correct']}/{s['total']})")
    return summary, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default=str(GOLDEN))
    ap.add_argument("--out", default=None, help="write summary+rows JSON here")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    summary, rows = asyncio.run(run(Path(args.golden), args.limit))
    if args.out:
        # --out gets the PII-safe summary only. The full rows (answer text can
        # contain student names) always go to a sibling *_results.json, which is
        # gitignored — so a documented `--out baseline.json` can never leak PII.
        out = Path(args.out)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        rows_path = out.with_name(out.stem + "_results.json")
        rows_path.write_text(
            json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nwrote {out} (summary) and {rows_path.name} (rows — gitignored)")


if __name__ == "__main__":
    main()
