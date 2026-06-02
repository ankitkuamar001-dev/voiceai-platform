"""Knowledge Ingestion CLI — load documents into the vector store.

Supports: .md, .txt, .pdf, .csv
Reads files from a knowledge-base directory, chunks them, creates
embeddings, and upserts to the configured vector store (Pinecone or
local FAISS).

Usage
-----
    python -m knowledge_ingestion --dir /path/to/docs
    python -m knowledge_ingestion                     # uses default ./knowledge-base/
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Path setup for shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from rag_engine import RAGEngine

logger = logging.getLogger("ai-brain.ingestion")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".csv"}
DEFAULT_KB_DIR = os.path.join(os.path.dirname(__file__), "knowledge-base")


# ── Loaders ──


def load_text_file(path: Path) -> str:
    """Read a plain-text or markdown file."""
    return path.read_text(encoding="utf-8", errors="replace")


def load_pdf_file(path: Path) -> str:
    """Extract text from a PDF file using PyPDF2 (if available)."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)
    except ImportError:
        logger.warning(
            "PyPDF2 not installed — skipping PDF %s. Install with: pip install PyPDF2",
            path.name,
        )
        return ""
    except Exception as exc:
        logger.error("Failed to read PDF %s: %s", path.name, exc)
        return ""


def load_csv_file(path: Path) -> str:
    """Convert CSV rows into a text representation."""
    import csv

    rows: list[str] = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                line = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
                rows.append(line)
    except Exception as exc:
        logger.error("Failed to read CSV %s: %s", path.name, exc)
    return "\n".join(rows)


LOADERS = {
    ".md": load_text_file,
    ".txt": load_text_file,
    ".pdf": load_pdf_file,
    ".csv": load_csv_file,
}


# ── Discovery ──


def discover_files(directory: str) -> list[Path]:
    """Recursively discover supported files in the given directory."""
    root = Path(directory)
    if not root.is_dir():
        logger.error("Directory does not exist: %s", directory)
        return []

    files: list[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(root.rglob(f"*{ext}"))

    files.sort()
    logger.info("Discovered %d files in %s", len(files), directory)
    return files


# ── Ingestion pipeline ──


async def ingest(directory: str, org_id: str = "default") -> dict[str, Any]:
    """Run the full ingestion pipeline.

    1. Discover files
    2. Load and extract text
    3. Initialize RAG engine
    4. Add documents (chunked + embedded)
    5. Persist index

    Returns summary stats.
    """
    files = discover_files(directory)
    if not files:
        logger.warning("No files to ingest from %s", directory)
        return {"files_found": 0, "chunks_added": 0}

    # Extract text from each file
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for file_path in files:
        ext = file_path.suffix.lower()
        loader = LOADERS.get(ext)
        if loader is None:
            continue

        logger.info("Loading %s", file_path.name)
        content = loader(file_path)
        if not content.strip():
            logger.warning("Empty content from %s — skipping", file_path.name)
            continue

        texts.append(content)
        metadatas.append(
            {
                "source": str(file_path),
                "filename": file_path.name,
                "extension": ext,
                "org_id": org_id,
            }
        )

    if not texts:
        logger.warning("No extractable text found")
        return {"files_found": len(files), "chunks_added": 0}

    # Initialize RAG engine and add documents
    rag = RAGEngine()
    await rag.initialize()
    await rag.add_documents(texts=texts, metadatas=metadatas)
    rag.save_index()

    stats = {
        "files_found": len(files),
        "files_loaded": len(texts),
        "chunks_added": len(texts),  # approximate — actual chunks depend on splitting
    }
    logger.info("Ingestion complete: %s", stats)
    return stats


# ── CLI entrypoint ──


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest knowledge-base documents into the vector store."
    )
    parser.add_argument(
        "--dir",
        default=DEFAULT_KB_DIR,
        help="Path to the knowledge-base directory (default: ./knowledge-base/)",
    )
    parser.add_argument(
        "--org-id",
        default="default",
        help="Organization ID to tag documents with",
    )
    args = parser.parse_args()

    asyncio.run(ingest(args.dir, args.org_id))


if __name__ == "__main__":
    main()
