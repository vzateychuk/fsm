from dataclasses import dataclass
from pathlib import Path

from store.filestore import FileStore


@dataclass(slots=True)
class LocalFileStore:
    """Local filesystem-based implementation of FileStore."""

    filestore_dir: str = ".data/filestore"

    async def save_source(
        self,
        *,
        document_id: str,
        source_path: str,
        content: str,
    ) -> None:
        """Save source document to local filestore directory."""
        filestore_path = Path(self.filestore_dir)
        filestore_path.mkdir(parents=True, exist_ok=True)

        doc_file = filestore_path / f"{document_id}.md"
        doc_file.write_text(content, encoding="utf-8")
