"""Run the Goal Planner FastAPI app (PYTHONPATH must include this repo root)."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.env_bootstrap import load_env_files  # noqa: E402

load_env_files()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.app:api",
        host=os.environ.get("GP_HOST", "127.0.0.1"),
        port=int(os.environ.get("GP_PORT", os.environ.get("APP_PORT", "8009"))),
        reload=os.environ.get("GP_RELOAD", "").lower() in ("1", "true", "yes"),
    )
