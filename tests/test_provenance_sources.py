"""Provenance: the FACT path must report which documents it answered from (Phase-B T2.1).

VectorSearch has always returned per-hit metadata; _fact_context was the one place it
got dropped, so no surface could cite anything while the GLOBAL prompt simultaneously
ordered the model to write a citations section it had no material for.

Two properties are load-bearing here and are asserted below:
  * sources land in metadata["sources"], NOT in the context string. 15 of 120 stress
    golds pass on source-label text alone, so labels in context would inflate every
    substring score measured afterwards.
  * _fact_context keeps its single-argument signature — three fallback tests monkeypatch
    it with a one-arg lambda, and shipping citations must not break the TABULAR fallback.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))
import retrieval.router as router_mod


class _FakeVS:
    """Two hits from two documents, plus a duplicate of the first source."""

    def search(self, query, top_k=5):
        return [
            {"content": "B.Tech requires 168 credits.",
             "metadata": {"source": "01_academic_regulations.md", "Header 2": "Credits"}},
            {"content": "Hostel fee is Rs 45,000.",
             "metadata": {"source": "02_fee_structure.md", "Header 2": "Hostel"}},
            {"content": "A minimum CGPA of 6.0 applies.",
             "metadata": {"source": "01_academic_regulations.md", "Header 2": "Credits"}},
        ]


@pytest.fixture
def router(monkeypatch):
    monkeypatch.setattr(router_mod, "VectorSearch", lambda tid: _FakeVS())
    monkeypatch.setattr(router_mod, "GraphSearch", lambda tid: object())
    monkeypatch.setattr(router_mod, "CommunitySearch", lambda tid: object())
    return router_mod.QueryRouter("t")


@pytest.mark.asyncio
async def test_fact_route_reports_sources(router, monkeypatch):
    monkeypatch.setattr(router, "classify_query", AsyncMock(return_value=("FACT", None)))

    qtype, context, metadata = await router.route_query("How many credits?")

    assert qtype == "FACT"
    sources = metadata["sources"]
    assert [s["source"] for s in sources] == [
        "01_academic_regulations.md", "02_fee_structure.md"
    ], "duplicate sources must collapse, order follows retrieval rank"
    assert sources[0]["section"] == "Credits"


@pytest.mark.asyncio
async def test_source_labels_never_enter_the_context_string(router, monkeypatch):
    """The scorer is substring-based; labels in context would be free gold tokens."""
    monkeypatch.setattr(router, "classify_query", AsyncMock(return_value=("FACT", None)))

    _, context, _ = await router.route_query("How many credits?")

    assert "01_academic_regulations.md" not in context
    assert "Credits" not in context
    assert context == (
        "B.Tech requires 168 credits.\n"
        "Hostel fee is Rs 45,000.\n"
        "A minimum CGPA of 6.0 applies."
    )


def test_fact_context_stays_single_argument(router):
    """Three fallback tests monkeypatch this with `lambda q: ...` — keep it callable so."""
    assert router._fact_context("How many credits?").startswith("B.Tech requires")


@pytest.mark.asyncio
async def test_no_sources_key_when_path_has_no_provenance(router, monkeypatch):
    """GLOBAL/LOCAL graph paths carry no source metadata; absence is the honest signal."""
    monkeypatch.setattr(router, "classify_query", AsyncMock(return_value=("GLOBAL", None)))
    router.cs = SimpleNamespace(get_all_summaries=lambda: "Community 0:\nsomething")

    _, _, metadata = await router.route_query("Summarise the themes.")

    assert "sources" not in metadata
