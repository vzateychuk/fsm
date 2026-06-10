"""Ingest CLI — process markdown documents into knowledge base."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import typer

from common.upload_filename import sanitize_upload_filename
from src.api.factory import create_app_context
from src.common.logging_config import setup_logging
from src.services.errors import IngestFailedError

app = typer.Typer(add_completion=False)


@app.command()
def ingest(
    file: Path = typer.Argument(..., help="Path to the .md file to ingest"),  # noqa: B008
    db: Path = typer.Option(Path(".data/db/ingest.db"), "--db", help="Path to SQLite DB"),  # noqa: B008
) -> None:
    """Ingest a single markdown document into the knowledge base pipeline.

    Examples:
        uv run advisor .data/ingest/some_doc.md
        uv run advisor .data/ingest/some_doc.md --db ./data/custom.db
    """
    file = file.resolve()
    db = db.resolve()
    filename = sanitize_upload_filename(file.name)

    log_file = Path("logs/ingest.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    setup_logging(level=logging.DEBUG, log_file=str(log_file))
    logger = logging.getLogger(__name__)

    if not file.exists():
        logger.error("Document file not found: %s", file)
        sys.exit(1)

    os.environ["DB_PATH"] = str(db)

    content = file.read_text(encoding="utf-8")
    logger.info("Ingesting file: %s filename=%s (%d chars)", file, filename, len(content))

    async def _run() -> None:
        ctx = await create_app_context()
        try:
            doc = await ctx.ingest_service.ingest_document(
                content, original_filename=filename
            )
            logger.info(
                "Ingest completed: document_id=%s category=%s date=%s filename=%s",
                doc.document_id,
                doc.category,
                doc.document_date,
                doc.source_path,
            )
        except IngestFailedError as e:
            logger.error("Ingest failed filename=%s: %s", filename, e)
            sys.exit(1)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
