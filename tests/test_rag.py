import sys
from pathlib import Path
import pytest
from unittest.mock import patch, AsyncMock

sys.path.append(str(Path(__file__).resolve().parent.parent))

from retrieval.router import QueryRouter
from generation.answer import generate_answer
from api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

@pytest.mark.asyncio
async def test_generate_answer():
    # Test generation with mocked HTTP request to Ollama
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.json.return_value = {"response": "Mocked Answer"}
        mock_post.return_value.raise_for_status = AsyncMock()
        
        ans = await generate_answer("What is this?", "This is a test context.")
        assert ans == "Mocked Answer"

def test_api_query_endpoint():
    # Test the API endpoint by mocking the router and answer generator
    with patch("api.main.router.route_query", new_callable=AsyncMock) as mock_route:
        mock_route.return_value = ("FACT", "Mocked context")
        
        with patch("api.main.generate_answer", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "Mocked API Answer"
            
            # Since TestClient works synchronously for FastAPI endpoints, it blocks 
            # and runs the async functions inside the event loop.
            response = client.post("/query", json={
                "query": "Test API query",
                "tenant_id": "tenant_1"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["query_type"] == "FACT"
            assert data["answer"] == "Mocked API Answer"
            assert data["context_used"] == "Mocked context"
