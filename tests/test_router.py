import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, patch

sys.path.append(str(Path(__file__).resolve().parent.parent))
from retrieval.router import QueryRouter

@pytest.mark.asyncio
async def test_router_classify_fact():
    router = QueryRouter(tenant_id="tenant_1")
    # Mock httpx.AsyncClient.post to return "FACT"
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.json.return_value = {"response": "FACT"}
        mock_post.return_value.raise_for_status = AsyncMock()
        
        qtype = await router.classify_query("What is the speed of light?")
        assert qtype == "FACT"

@pytest.mark.asyncio
async def test_router_classify_local():
    router = QueryRouter(tenant_id="tenant_1")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.json.return_value = {"response": "LOCAL"}
        mock_post.return_value.raise_for_status = AsyncMock()
        
        qtype = await router.classify_query("Who does Alice work with?")
        assert qtype == "LOCAL"
