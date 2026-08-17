"""Chunking and BM25 retrieval over requirements/ and context/.

Pure keyword-based retrieval (LangChain's BM25Retriever) — zero embedding
calls, zero external services. This is a deliberate choice: the whole point
of this project is to need no heavy setup, and BM25 is enough signal for
matching a query built from Intent's extracted keywords against short
requirement chunks.
"""
from __future__ import annotations

import re
from pathlib import Path

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from core.schema import RequirementChunk

_H2_RE = re.compile(r"(?m)^##[ \t]+(.+?)[ \t]*$")


def chunk_text(source_file: str, text: str) -> list[RequirementChunk]:
    """Split markdown on ## headers. No ## headers -> the whole file is one chunk."""
    matches = list(_H2_RE.finditer(text))
    if not matches:
        stripped = text.strip()
        return [RequirementChunk(source_file=source_file, section_title=None, text=stripped)] if stripped else []

    chunks = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        chunks.append(RequirementChunk(source_file=source_file, section_title=None, text=preamble))

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        section_text = f"## {title}\n\n{body}" if body else f"## {title}"
        chunks.append(RequirementChunk(source_file=source_file, section_title=title, text=section_text))
    return chunks


def chunk_file(path: Path) -> list[RequirementChunk]:
    return chunk_text(path.name, path.read_text())


def load_context(dirs: str | Path | list[str | Path]) -> BM25Retriever:
    """Build one BM25Retriever over every .md file in the given directory/directories."""
    if isinstance(dirs, (str, Path)):
        dirs = [dirs]

    chunks: list[RequirementChunk] = []
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.md")):
            chunks.extend(chunk_file(path))

    if not chunks:
        raise ValueError(f"no markdown files found in {dirs}")

    docs = [
        Document(
            page_content=c.text,
            metadata={"source_file": c.source_file, "section_title": c.section_title},
        )
        for c in chunks
    ]
    return BM25Retriever.from_documents(docs)


def retrieve(retriever: BM25Retriever, query: str, k: int = 3) -> list[RequirementChunk]:
    """Top-k chunks for query. First result is what generation uses; the full
    list is what ContextualRelevancyMetric scores retrieval quality against.
    """
    retriever.k = k
    docs = retriever.invoke(query)
    return [
        RequirementChunk(
            source_file=d.metadata["source_file"],
            section_title=d.metadata.get("section_title"),
            text=d.page_content,
        )
        for d in docs
    ]
