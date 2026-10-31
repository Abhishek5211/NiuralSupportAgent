"""Hybrid BM25 and Chroma vector retrieval for product-guide sections."""

import argparse
import asyncio
import json
from hashlib import sha256
from pathlib import Path
from time import perf_counter

import chromadb
from chromadb.config import Settings
from chromadb.errors import NotFoundError
from openai import AsyncOpenAI
from pydantic import BaseModel

from .chunking import GuideChunk, chunk_product_guide
from .config import Config, PROJECT_DIR
from .hybrid import KeywordIndex, Ranking, RRF_CONSTANT


INDEX_DIR = PROJECT_DIR / ".chroma"
COLLECTION = "niural_product_guide"
BUILD_COMMAND = "python -m niural_support_agent.retrieval build"


class IndexNotReadyError(RuntimeError):
    pass


class SearchMatch(GuideChunk):
    distance: float
    ranking: Ranking


class SearchResult(BaseModel):
    matches: list[SearchMatch]
    embedding_tokens: int
    embedding_ms: float
    search_ms: float
    latency_ms: float


class GuideRetriever:
    def __init__(self, config: Config, client: AsyncOpenAI, *, index_dir: Path = INDEX_DIR):
        self.config = config
        self.client = client
        self.index_dir = index_dir
        self.chunks = chunk_product_guide()
        self.keywords = KeywordIndex(self.chunks)
        self.search_metadata = {"retrieval_method": "hybrid-bm25-rrf", "rrf_constant": RRF_CONSTANT,
                                "candidate_count": len(self.chunks), "keyword_tokenizer": "unicode-word-casefold"}
        content = json.dumps([c.embedding_text for c in self.chunks], ensure_ascii=False)
        self.metadata = {
            "source_hash": sha256(content.encode("utf-8")).hexdigest(),
            "embedding_model": config.embedding_model,
            "chunk_count": len(self.chunks),
        }
        self._collection = None

    def _store(self):
        return chromadb.PersistentClient(
            path=str(self.index_dir), settings=Settings(anonymized_telemetry=False))

    def open_index(self):
        """Load and validate once; chat never builds or embeds the guide."""
        if self._collection is None:
            if not self.index_dir.exists():
                raise IndexNotReadyError(f"Product guide is not indexed. Run: {BUILD_COMMAND}")
            try:
                collection = self._store().get_collection(COLLECTION, embedding_function=None)
            except NotFoundError:
                raise IndexNotReadyError(f"Product guide is not indexed. Run: {BUILD_COMMAND}") from None
            if collection.metadata != self.metadata or collection.count() != len(self.chunks):
                raise IndexNotReadyError(f"Product guide index is outdated or incomplete. Run: {BUILD_COMMAND}")
            self._collection = collection
        return self._collection

    async def _embed(self, texts: list[str]):
        response = await self.client.embeddings.create(
            model=self.config.embedding_model, input=texts, encoding_format="float")
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        if len(vectors) != len(texts):
            raise ValueError("Embedding response did not match the number of inputs")
        return vectors, response.usage.total_tokens

    async def build(self) -> dict:
        if not self.chunks:
            raise ValueError("The product guide has no chunks")
        try:
            await asyncio.to_thread(self.open_index)
            return {"chunks": len(self.chunks), "embedding_tokens": 0, "status": "already indexed"}
        except IndexNotReadyError:
            pass
        # Embed successfully before replacing this guide's existing collection.
        vectors, tokens = await self._embed([chunk.embedding_text for chunk in self.chunks])
        def save():
            store = self._store()
            try:
                store.delete_collection(COLLECTION)
            except NotFoundError:
                pass
            collection = store.create_collection(
                COLLECTION, embedding_function=None, metadata=self.metadata,
                configuration={"hnsw": {"space": "cosine"}})
            collection.add(
                ids=[c.section_id for c in self.chunks], embeddings=vectors,
                documents=[c.text for c in self.chunks],
                metadatas=[c.model_dump(exclude={"section_id", "text"}) for c in self.chunks])
            self._collection = collection
        await asyncio.to_thread(save)
        return {"chunks": len(self.chunks), "embedding_tokens": tokens, "status": "indexed"}

    async def search(self, query: str) -> SearchResult:
        query = query.strip()
        if not query:
            raise ValueError("Search query cannot be empty")
        started = perf_counter()
        collection = await asyncio.to_thread(self.open_index)
        embedding_started = perf_counter()
        vectors, tokens = await self._embed([query])
        embedding_ms = (perf_counter() - embedding_started) * 1000
        search_started = perf_counter()
        result = await asyncio.to_thread(
            collection.query, query_embeddings=vectors, n_results=len(self.chunks),
            include=["documents", "metadatas", "distances"])
        records = {identifier: (text, metadata, distance)
                   for identifier, text, metadata, distance in zip(result["ids"][0], result["documents"][0],
                       result["metadatas"][0], result["distances"][0], strict=True)}
        matches = []
        for identifier, ranking in self.keywords.fuse(query, result["ids"][0]):
            text, metadata, distance = records[identifier]
            matches.append(SearchMatch(section_id=identifier, text=text, distance=distance,
                                       ranking=ranking, **metadata))
        return SearchResult(
            matches=matches, embedding_tokens=tokens, embedding_ms=round(embedding_ms, 2),
            search_ms=round((perf_counter() - search_started) * 1000, 2),
            latency_ms=round((perf_counter() - started) * 1000, 2))


async def run(command: str, query: str | None):
    config = Config.load()
    async with AsyncOpenAI(api_key=config.api_key, max_retries=0, timeout=45) as client:
        guide = GuideRetriever(config, client)
        result = await guide.build() if command == "build" else (await guide.search(query)).model_dump()
        print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "search"])
    parser.add_argument("query", nargs="?")
    args = parser.parse_args()
    if args.command == "search" and not args.query:
        parser.error("search requires a query")
    asyncio.run(run(args.command, args.query))


if __name__ == "__main__":
    main()
