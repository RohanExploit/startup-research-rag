import asyncio
import sys
import httpx
import logging

sys.path.insert(0, "R:/Startup research/Start up V2")
from retrieval.router import QueryRouter
import retrieval.router

# Mock the URL to force a failure
retrieval.router.OLLAMA_API_URL = "http://127.0.0.1:9999/api/generate"

async def main():
    print("Testing router fallback...")
    router = QueryRouter()
    qtype, context, metadata = await router.route_query("Test query")
    print("\n--- Fallback Results ---")
    print(f"QType: {qtype}")
    print(f"Metadata: {metadata}")
    
if __name__ == "__main__":
    asyncio.run(main())
