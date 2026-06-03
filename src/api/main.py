"""Uvicorn entry point for the Med AI Adviser API server.

Ensures src/ is in sys.path so inner modules that use non-prefixed imports
(e.g. `from common.types import ChunkKind`) resolve correctly alongside the
`from src.xxx` style used by the API layer.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    # Project root is already in sys.path when invoked via `python -m` or installed script.
    # Also add src/ so inner modules (common, fsm, pipelines, store) resolve without prefix.
    src_dir = str(Path(__file__).resolve().parent.parent)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from src.common.logging_config import setup_logging

    setup_logging()

    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() in ("1", "true", "yes")

    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
