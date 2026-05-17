from typing import Protocol


class FileStore(Protocol):
    """Protocol for persisting source documents to file storage."""

    async def save_source(
        self,
        *,
        document_id: str,
        source_path: str,
        content: str,
    ) -> None:
        """Save source document to file storage.

        Args:
            document_id: Unique document identifier
            source_path: Original file path (for logging/audit)
            content: Source document content
        """
        ...
