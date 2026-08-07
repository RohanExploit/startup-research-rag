"""
Hermetic generation tests. Mocks the REAL outbound client
(generation.answer._http_client.post), not the httpx class, and uses the real
generate_answer signature. The API query path is covered in test_api.py.
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))
import generation.answer as answer


@pytest.mark.asyncio
async def test_generate_answer_uses_ollama_response(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock(return_value=None)
    fake_resp.json = MagicMock(return_value={"response": "  Mocked Answer  "})
    monkeypatch.setattr(answer._http_client, "post", AsyncMock(return_value=fake_resp))

    out = await answer.generate_answer("What is this?", "This is a test context.")
    assert out == "Mocked Answer"  # stripped


@pytest.mark.asyncio
async def test_generate_answer_fallback_message_when_ollama_down_and_no_key(monkeypatch):
    # Ollama call raises; no NVIDIA key -> deterministic graceful message (no network).
    monkeypatch.setattr(answer._http_client, "post", AsyncMock(side_effect=RuntimeError("conn refused")))
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    out = await answer.generate_answer("q", "ctx")
    assert "fallback API key is configured" in out
