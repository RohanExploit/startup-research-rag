import uvicorn
import argparse
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start Company Brain API")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP")
    parser.add_argument("--port", type=int, default=8000, help="Port")
    args = parser.parse_args()
    
    # Run FastAPI app
    uvicorn.run("api.main:app", host=args.host, port=args.port, reload=True)
