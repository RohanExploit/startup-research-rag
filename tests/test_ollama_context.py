import requests
import time
import json
import re

text = """High-frequency trading (HFT) methods work on sub-second time scales and often cause complicated market dynamics that are difficult to explain. Retrieval-Augmented Generation (RAG) has evolved as a strategy to ground large language models (LLMs) with factual context, including domain-specific financial data[1][2]. However, RAG systems often rely on historical records or textual data and can struggle with rare or hypothetical scenarios[3]. We present RAG-MicroSim, a novel hybrid architecture that augments RAG with an integrated micro-simulation engine. RAG-MicroSim dynamically generates synthetic limit order book (LOB) states and trade events on demand, which are used alongside retrieved historical data. real-time risk assessment and anomaly identification, and permits testing of possible algorithmic behaviors not apparent in past logs.We go into detail on RAG-MicroSim's architecture, market microstructure simulation techniques, and integration plan with the RAG pipeline. In conclusion,"""

prompt = f"Extract entities and relations as JSON from this text: {text}"

payload = {
    "model": "qwen3:4b-instruct-2507-q4_K_M",
    "prompt": prompt,
    "stream": False,
    "format": "json",
    "options": {
        "num_ctx": 2048
    }
}

start_time = time.time()
print("Starting request...")
try:
    response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=600)
    response.raise_for_status()
    end_time = time.time()
    
    data = response.json()
    raw_response = data.get("response", "")
    
    print(f"Time taken: {end_time - start_time:.2f} seconds")
    print("----- RAW RESPONSE -----")
    print(raw_response)
    print("------------------------")
    
except Exception as e:
    print(f"Error: {e}")
