"""RAG Engine — Retrieval-Augmented Generation with LangChain.

Supports:
  • Pinecone vector store (production)
  • FAISS in-memory fallback (local development)
  • OpenAI text-embedding-3-small embeddings
  • Hybrid retrieval: vector similarity + keyword matching
  • Re-ranking of results by combined score
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger("ai-brain.rag")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "voiceai-knowledge")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
USE_PINECONE = os.getenv("USE_PINECONE", "false").lower() == "true"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Base path for knowledge-base documents
KB_DIR = Path(os.getenv("KB_DIR", os.path.join(os.path.dirname(__file__), "knowledge-base")))


class RAGEngine:
    """Retrieval-Augmented Generation engine."""

    def __init__(self) -> None:
        self._embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=OPENAI_API_KEY,
        )
        self._vector_store: Any = None
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self._documents: list[dict[str, Any]] = []  # in-memory fallback store

    async def initialize(self) -> None:
        """Initialize the vector store backend."""
        if USE_PINECONE and PINECONE_API_KEY:
            await self._init_pinecone()
        else:
            await self._init_faiss()

    # ── Pinecone backend ──

    async def _init_pinecone(self) -> None:
        """Connect to an existing Pinecone index."""
        try:
            from langchain_community.vectorstores import Pinecone as PineconeVectorStore
            from pinecone import Pinecone

            pc = Pinecone(api_key=PINECONE_API_KEY)
            index = pc.Index(PINECONE_INDEX_NAME)

            self._vector_store = PineconeVectorStore(
                index=index,
                embedding=self._embeddings,
                text_key="text",
            )
            logger.info("Pinecone vector store initialized (index=%s)", PINECONE_INDEX_NAME)
        except Exception as exc:
            logger.warning("Pinecone init failed (%s), falling back to FAISS", exc)
            await self._init_faiss()

    # ── FAISS backend ──

    async def _init_faiss(self) -> None:
        """Initialize an in-memory FAISS index, optionally loading docs from disk."""
        try:
            from langchain_community.vectorstores import FAISS

            # Try to load existing index from disk
            faiss_path = Path(os.path.dirname(__file__)) / ".faiss_index"
            if faiss_path.exists():
                self._vector_store = FAISS.load_local(
                    str(faiss_path),
                    self._embeddings,
                    allow_dangerous_deserialization=True,
                )
                logger.info("FAISS index loaded from disk")
            else:
                # Create an empty index with a dummy document (FAISS requires ≥1)
                self._vector_store = FAISS.from_texts(
                    texts=["Placeholder document for initialization."],
                    embedding=self._embeddings,
                    metadatas=[{"source": "init", "org_id": "system"}],
                )
                logger.info("Empty FAISS index created")
        except Exception as exc:
            logger.error("FAISS initialization failed: %s", exc)
            self._vector_store = None

    # ── Public API ──

    async def search(
        self,
        query: str,
        org_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search the knowledge base for relevant chunks.

        Uses vector similarity search with optional keyword re-ranking.
        """
        if self._vector_store is None:
            logger.warning("Vector store not initialized — returning empty results")
            return []

        try:
            # Vector similarity search
            vector_results = await self._vector_search(query, top_k=top_k * 2)

            # Keyword matching boost
            keyword_results = self._keyword_search(query, top_k=top_k)

            # Merge and re-rank
            merged = self._rerank(vector_results, keyword_results, top_k=top_k)
            return merged
        except Exception as exc:
            logger.error("Search failed: %s", exc)
            return []

    async def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add new document chunks to the vector store."""
        if self._vector_store is None:
            logger.warning("Vector store not initialized — cannot add documents")
            return

        chunks = []
        chunk_metas = []
        for i, text in enumerate(texts):
            splits = self._text_splitter.split_text(text)
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            for j, chunk in enumerate(splits):
                chunks.append(chunk)
                chunk_metas.append({**meta, "chunk_index": j})

        if chunks:
            self._vector_store.add_texts(texts=chunks, metadatas=chunk_metas)
            # Also store in memory for keyword search
            for chunk, meta in zip(chunks, chunk_metas):
                self._documents.append({"content": chunk, "metadata": meta})

            logger.info("Added %d chunks to the vector store", len(chunks))

    def save_index(self, path: str | None = None) -> None:
        """Persist the FAISS index to disk (no-op for Pinecone)."""
        if self._vector_store is None:
            return
        save_path = path or str(Path(os.path.dirname(__file__)) / ".faiss_index")
        try:
            self._vector_store.save_local(save_path)
            logger.info("FAISS index saved to %s", save_path)
        except AttributeError:
            pass  # Pinecone doesn't have save_local

    # ── Internal helpers ──

    async def _vector_search(
        self, query: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Run vector similarity search."""
        try:
            docs_with_scores = self._vector_store.similarity_search_with_score(
                query, k=top_k
            )
            results = []
            for doc, score in docs_with_scores:
                results.append({
                    "content": doc.page_content,
                    "score": float(1 - score) if score <= 1 else float(1 / (1 + score)),
                    "metadata": doc.metadata,
                    "source": "vector",
                })
            return results
        except Exception as exc:
            logger.error("Vector search failed: %s", exc)
            return []

    def _keyword_search(
        self, query: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Simple keyword matching across in-memory documents."""
        query_terms = set(query.lower().split())
        scored: list[tuple[float, dict[str, Any]]] = []

        for doc in self._documents:
            content_lower = doc["content"].lower()
            matches = sum(1 for term in query_terms if term in content_lower)
            if matches > 0:
                score = matches / max(len(query_terms), 1)
                scored.append((score, {
                    "content": doc["content"],
                    "score": score,
                    "metadata": doc.get("metadata", {}),
                    "source": "keyword",
                }))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def _rerank(
        self,
        vector_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Merge vector and keyword results with weighted scoring.

        Vector results weighted at 0.7, keyword at 0.3.
        Duplicates are merged by summing scores.
        """
        VECTOR_WEIGHT = 0.7
        KEYWORD_WEIGHT = 0.3

        # Track by content hash to merge duplicates
        seen: dict[str, dict[str, Any]] = {}

        for r in vector_results:
            key = r["content"][:100]  # use prefix as dedup key
            if key in seen:
                seen[key]["score"] += r["score"] * VECTOR_WEIGHT
            else:
                seen[key] = {
                    "content": r["content"],
                    "score": r["score"] * VECTOR_WEIGHT,
                    "metadata": r.get("metadata", {}),
                }

        for r in keyword_results:
            key = r["content"][:100]
            if key in seen:
                seen[key]["score"] += r["score"] * KEYWORD_WEIGHT
            else:
                seen[key] = {
                    "content": r["content"],
                    "score": r["score"] * KEYWORD_WEIGHT,
                    "metadata": r.get("metadata", {}),
                }

        ranked = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]
