"""BM25 keyword ranking combined with vector ranking using reciprocal ranks."""

import re

from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from .chunking import GuideChunk


TOP_K = 3
RRF_CONSTANT = 60


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


class Ranking(BaseModel):
    vector_rank: int
    keyword_rank: int | None
    keyword_score: float
    rrf_score: float


class KeywordIndex:
    def __init__(self, chunks: list[GuideChunk]):
        if not chunks:
            raise ValueError("The product guide has no chunks")
        self.ids = [chunk.section_id for chunk in chunks]
        self.bm25 = BM25Okapi([tokenize(chunk.embedding_text) for chunk in chunks])

    def fuse(self, query: str, vector_ids: list[str]) -> list[tuple[str, Ranking]]:
        scores = dict(zip(self.ids, map(float, self.bm25.get_scores(tokenize(query))), strict=True))
        keyword_ids = sorted((key for key, score in scores.items() if score > 0),
                             key=lambda key: (-scores[key], key))
        keyword_ranks = {key: rank for rank, key in enumerate(keyword_ids, 1)}
        rankings = {}
        for vector_rank, key in enumerate(vector_ids, 1):
            keyword_rank = keyword_ranks.get(key)
            score = 1 / (RRF_CONSTANT + vector_rank)
            if keyword_rank is not None:
                score += 1 / (RRF_CONSTANT + keyword_rank)
            rankings[key] = Ranking(vector_rank=vector_rank, keyword_rank=keyword_rank,
                                    keyword_score=scores[key], rrf_score=score)
        # On a fusion tie, keep vector order. No keyword matches means vector-only order.
        ordered = sorted(vector_ids, key=lambda key: (-rankings[key].rrf_score, rankings[key].vector_rank))
        return [(key, rankings[key]) for key in ordered[:TOP_K]]
