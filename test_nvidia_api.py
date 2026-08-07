import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path("R:/Startup research/Start up V2")
sys.path.append(str(project_root))
load_dotenv(project_root / ".env")

from generation.answer import generate_answer

async def test_nvidia_api():
    print("Testing NVIDIA API via generate_answer...")
    context = "NVIDIA NIM provides highly optimized inference microservices for LLMs."
    query = "What is NVIDIA NIM?"
    
    try:
        response = await generate_answer(query, context, qtype="LOCAL")
        print(f"API Response:\n{response}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_nvidia_api())
