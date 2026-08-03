from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DocumentChunk

EMBED_DIM = 768


def _simple_embed(text: str) -> list[float]:
    """Deterministic pseudo-embedding for MVP (no external embedding API required)."""
    vec = [0.0] * EMBED_DIM
    tokens = re.findall(r"\w+", text.lower())
    for token in tokens:
        h = hashlib.sha256(token.encode()).digest()
        for i in range(0, min(len(h), 32), 4):
            idx = int.from_bytes(h[i : i + 4], "big") % EMBED_DIM
            vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _chunk_text(text: str, chunk_size: int = 400) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) < chunk_size:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks or [text]


def _docs_dir() -> Path:
    base = Path(__file__).resolve()
    for candidate in (
        base.parents[2] / "content" / "docs",
        base.parents[3] / "content" / "docs",
    ):
        if candidate.exists():
            return candidate
    return base.parents[3] / "content" / "docs"


class RAGService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ingest_documents(self) -> int:
        await self.session.execute(delete(DocumentChunk))
        count = 0
        docs_dir = _docs_dir()
        if not docs_dir.exists():
            return 0
        for doc_path in sorted(docs_dir.glob("*.md")):
            text = doc_path.read_text(encoding="utf-8")
            for idx, chunk in enumerate(_chunk_text(text)):
                self.session.add(
                    DocumentChunk(
                        document_name=doc_path.name,
                        chunk_index=idx,
                        content=chunk,
                        embedding=_simple_embed(chunk),
                    )
                )
                count += 1
        await self.session.commit()
        return count

    async def query(self, question: str, top_k: int = 3) -> list[dict]:
        q_emb = _simple_embed(question)
        rows = (await self.session.execute(select(DocumentChunk))).scalars().all()
        scored = []
        for row in rows:
            if row.embedding is None:
                continue
            score = _cosine(q_emb, list(row.embedding))
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "document_name": row.document_name,
                "content": row.content,
                "score": round(score, 4),
            }
            for score, row in scored[:top_k]
        ]

    async def answer(self, question: str) -> dict:
        chunks = await self.query(question)
        context = "\n\n---\n\n".join(c["content"] for c in chunks)
        return {"question": question, "sources": chunks, "context": context}
