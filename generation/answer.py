import logging
import os
import sys
import httpx
from pathlib import Path
from openai import AsyncOpenAI
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import API_TIMEOUT

logging.basicConfig(level=logging.INFO)

# Ollama Configuration
OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen3:4b-instruct-2507-q4_K_M"
OLLAMA_KEEP_ALIVE = "10m"

# Lazily create the shared client on first use so it binds to the running event
# loop (creating it at import time leaks a client tied to the import-time loop and
# produces "Event loop is closed" noise on Windows teardown). Closed on app
# shutdown via aclose_http_client() (wired in api/main.py's lifespan).
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=API_TIMEOUT)
    return _http_client


async def aclose_http_client() -> None:
    """Close the shared Ollama client. Idempotent; safe to call on shutdown."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
    _http_client = None

async def generate_answer(query: str, context: str, qtype: str = "LOCAL") -> str:
    if qtype == "GLOBAL":
        prompt = f"""
You are the "Company Brain", a helpful internal AI assistant answering a decision-assisting or broad query.
Answer the user's query based ONLY on the provided context. If the answer is not in the context, say "I don't have enough information to answer that."

You MUST format your answer using the following strict Markdown structure:
### 1. Recommendation / Summary
[Your high-level answer or recommendation]

### 2. Supporting Evidence
[Detailed points extracted from the context supporting the summary]

### 3. Citations / Sources
[List the document sources or community references]

Context:
{context}

Query: {query}
Answer:
        """
    else:
        prompt = f"""
You are the "Company Brain", a helpful internal AI assistant.
Answer the user's query based ONLY on the provided context. If the answer is not in the context, say "I don't have enough information to answer that."

Context:
{context}

Query: {query}
Answer:
        """
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"num_ctx": 2048, "num_predict": 512}
    }

    try:
        response = await _get_http_client().post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        return response.json()["response"].strip()
    except Exception as e:
        logging.warning(f"Local Ollama generation failed: {e}. Attempting NVIDIA API fallback...")
        nvidia_api_key = os.environ.get("NVIDIA_API_KEY")
        if not nvidia_api_key:
            logging.error("NVIDIA_API_KEY not found in environment variables. Fallback aborted.")
            return "Sorry, the local generation engine encountered an error and no fallback API key is configured."
            
        try:
            # async-with so the fallback client's connection pool is closed even
            # on error (it was previously created per call and never closed).
            async with AsyncOpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=nvidia_api_key,
                timeout=API_TIMEOUT,
            ) as client:
                completion = await client.chat.completions.create(
                    model="meta/llama-3.1-70b-instruct",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=1024,
                )
            fallback_answer = completion.choices[0].message.content.strip()
            logging.info("Successfully generated answer using NVIDIA API fallback.")
            return fallback_answer
        except Exception as fallback_e:
            logging.error(f"NVIDIA API fallback also failed: {fallback_e}")
            return "Sorry, both local generation and the fallback API encountered an error."

if __name__ == "__main__":
    import asyncio
    ctx = "RAG-MicroSim is a hybrid framework."
    q = "What is RAG-MicroSim?"
    # generate_answer is a coroutine — must be awaited, not printed directly.
    print(asyncio.run(generate_answer(q, ctx)))
