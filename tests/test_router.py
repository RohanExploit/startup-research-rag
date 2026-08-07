"""
Hermetic router-classification tests. Patches the real module-level client
(retrieval.router._http_client) and the heavy retrieval deps so construction is
instant and no model/Ollama is needed. classify_query returns (qtype, reason).
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))
import retrieval.router as router_mod


@pytest.fixture
def router(monkeypatch):
    # avoid loading SentenceTransformer / graph / summaries
    monkeypatch.setattr(router_mod, "VectorSearch", lambda tid: object())
    monkeypatch.setattr(router_mod, "GraphSearch", lambda tid: object())
    monkeypatch.setattr(router_mod, "CommunitySearch", lambda tid: object())
    return router_mod.QueryRouter("tenant_1")


def _mock_ollama(monkeypatch, category: str):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value={"response": category})
    monkeypatch.setattr(router_mod._http_client, "post", AsyncMock(return_value=resp))


@pytest.mark.asyncio
async def test_classify_fact(router, monkeypatch):
    _mock_ollama(monkeypatch, "FACT")
    qtype, reason = await router.classify_query("What is the speed of light?")
    assert qtype == "FACT"


@pytest.mark.asyncio
async def test_classify_local(router, monkeypatch):
    _mock_ollama(monkeypatch, "LOCAL")
    qtype, reason = await router.classify_query("Who does Alice collaborate with?")
    assert qtype == "LOCAL"


@pytest.mark.asyncio
async def test_deterministic_tabular_override_skips_llm(router, monkeypatch):
    # student-shaped queries must route to TABULAR WITHOUT any Ollama call
    monkeypatch.setattr(
        router_mod._http_client, "post",
        AsyncMock(side_effect=AssertionError("classify must not call Ollama for student queries")),
    )
    qtype, reason = await router.classify_query("search for Gaikwad Rohan")
    assert qtype == "TABULAR"


@pytest.mark.asyncio
async def test_classify_ollama_down_falls_back_to_fact(router, monkeypatch):
    import httpx
    monkeypatch.setattr(
        router_mod._http_client, "post",
        AsyncMock(side_effect=httpx.ConnectError("refused")),
    )
    qtype, reason = await router.classify_query("Explain the architecture broadly")
    assert qtype == "FACT"
    assert reason and "ollama_exception" in reason
