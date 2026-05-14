import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

from fsm.core import RunContext
from pipelines.ingest.models import IngestInput, IngestData


@dataclass(slots=True)
class LoadSource:
    """S1: Load markdown file from source path"""

    id = "load_source"
    desc = "Load markdown file from source"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Loading document from source"
        try:
            text = await asyncio.to_thread(Path(ctx.input.source_path).read_text, encoding="utf-8")
            ctx.data.raw_content = text
            ctx.data.desc = f"Loaded {len(ctx.data.raw_content)} characters"
        except Exception as e:
            ctx.data.desc = f"Error loading file: {e}"
            raise


@dataclass(slots=True)
class PreprocessText:
    """S2: Normalize text and compute SHA256 hash"""

    id = "preprocess_text"
    desc = "Normalize text and compute SHA256 hash"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Preprocessing text and computing hash"
        # Remove BOM, normalize line breaks
        content = ctx.data.raw_content.lstrip("﻿")
        content = content.replace("\r\n", "\n")
        ctx.data.raw_content = content
        # Compute SHA256
        ctx.data.file_hash = hashlib.sha256(content.encode()).hexdigest()
        ctx.data.desc = f"Preprocessed, hash={ctx.data.file_hash[:16]}..."


@dataclass(slots=True)
class DetectTargetSchema:
    """S3: Detect target schema from document"""

    id = "detect_target_schema"
    desc = "Detect target schema from document header"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Detecting target schema"
        # Simple parser: first line may contain schema in format %%schema_name
        lines = ctx.data.raw_content.split("\n")
        if lines and lines[0].startswith("%%"):
            ctx.data.target_schema = lines[0][2:].strip()
        else:
            ctx.data.target_schema = "default"
        ctx.data.desc = f"Schema detected: {ctx.data.target_schema}"


@dataclass(slots=True)
class SplitControlBlocks:
    """S4: Split into schema line, metadata block, and markdown body"""

    id = "split_control_blocks"
    desc = "Split document into control blocks (schema, metadata, body)"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Splitting control blocks"
        lines = ctx.data.raw_content.split("\n")
        idx = 0

        # Schema line
        if lines and lines[0].startswith("%%"):
            ctx.data.schema_line = lines[0]
            idx = 1

        # Metadata block (between --- markers)
        metadata_lines = []
        if idx < len(lines) and lines[idx].strip() == "---":
            idx += 1
            while idx < len(lines) and lines[idx].strip() != "---":
                metadata_lines.append(lines[idx])
                idx += 1
            if idx < len(lines) and lines[idx].strip() == "---":
                idx += 1
            ctx.data.metadata_block = "\n".join(metadata_lines)

        # Markdown body (rest)
        ctx.data.md_body = "\n".join(lines[idx:])
        ctx.data.desc = f"Split: schema_line={bool(ctx.data.schema_line)}, metadata={bool(ctx.data.metadata_block)}, body_lines={len(ctx.data.md_body.split(chr(10)))}"


@dataclass(slots=True)
class ParseToTokens:
    """S5: Parse markdown body to tokens"""

    id = "parse_to_tokens"
    desc = "Parse markdown to tokens for stable chunking"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Parsing markdown to tokens"
        # Simple parser: each non-empty line is a token
        tokens = []
        for line in ctx.data.md_body.split("\n"):
            line = line.strip()
            if line:
                token_type = "heading" if line.startswith("#") else "paragraph"
                tokens.append({
                    "type": token_type,
                    "content": line,
                    "level": len(line) - len(line.lstrip("#")) if token_type == "heading" else 0
                })
        ctx.data.tokens = tokens
        ctx.data.desc = f"Parsed {len(tokens)} tokens"


@dataclass(slots=True)
class ChunkifyBlocks:
    """S6: Group tokens into logical chunks with hierarchical section path"""

    id = "chunkify_blocks"
    desc = "Convert markdown blocks into atomic chunks with breadcrumb context for RAG"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Chunkifying blocks with section paths"
        chunks = []
        current_chunk = {"heading": "", "section_path": [], "content": [], "tokens": []}
        section_path = []

        for token in ctx.data.tokens:
            if token["type"] == "heading":
                level = token["level"]
                # Trim path to correct depth
                section_path = section_path[:level - 1]
                section_path.append(token["content"].lstrip("#").strip())

                if level <= 2:
                    # Major heading — start new chunk
                    if current_chunk["content"]:
                        chunks.append(current_chunk)
                    current_chunk = {
                        "heading": token["content"].lstrip("#").strip(),
                        "section_path": list(section_path),
                        "content": [],
                        "tokens": [token]
                    }
            else:
                current_chunk["content"].append(token["content"])
                current_chunk["tokens"].append(token)

        if current_chunk["content"]:
            chunks.append(current_chunk)

        ctx.data.chunks = chunks
        ctx.data.desc = f"Created {len(chunks)} chunks with breadcrumbs"


@dataclass(slots=True)
class Tagging:
    """S8: Tag chunks deterministically"""

    id = "tagging"
    desc = "Extract meaningful terms for FTS boosting"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Tagging chunks"
        tagged_chunks = []

        for chunk in ctx.data.chunks:
            # Simple tagging: first words from heading (skip numbers and short words)
            heading = chunk["heading"]
            tags = []
            for word in heading.split():
                # Skip numbers and short words
                if word and not word[0].isdigit() and len(word) > 2:
                    tags.append(word.lower())

            tagged_chunks.append({
                **chunk,
                "tags": tags[:5],
                "tags_text": " ".join(tags[:5])
            })

        ctx.data.tagged_chunks = tagged_chunks
        ctx.data.desc = f"Tagged {len(tagged_chunks)} chunks"


@dataclass(slots=True)
class PersistDocument:
    """S9: Save document metadata to database"""

    id = "persist_document"
    desc = "Save document metadata to database"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Persisting document metadata"
        # Simulation: generate ID based on hash
        ctx.data.document_id = ctx.data.file_hash[:16]
        ctx.data.desc = f"Document persisted with ID: {ctx.data.document_id}"


@dataclass(slots=True)
class PersistChunks:
    """S10: Save all chunks to database"""

    id = "persist_chunks"
    desc = "Save all chunks to database"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Persisting chunks to database"
        # Simulation: generate IDs for chunks
        ctx.data.chunk_ids = [f"{ctx.data.document_id}_{i}" for i in range(len(ctx.data.tagged_chunks))]
        ctx.data.desc = f"Persisted {len(ctx.data.chunk_ids)} chunks"


@dataclass(slots=True)
class UpdateFTS:
    """S11: Update FTS5 index with chunks"""

    id = "update_fts"
    desc = "Update FTS5 search index"

    async def run(self, ctx: RunContext[IngestInput, IngestData]) -> None:
        ctx.data.desc = "Updating FTS5 index"
        # Simulation: mark FTS as updated
        ctx.data.fts_updated = True
        ctx.data.desc = f"FTS5 index updated with {len(ctx.data.chunk_ids)} entries"
