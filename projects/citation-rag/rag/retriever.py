"""
Score-floor retrieval.

The one idea that matters here: a retriever must be allowed to return *nothing*. A naive
top-k always hands back its k best chunks even when the best is irrelevant, and that is exactly
how RAG systems produce confident, wrong, uncited answers. Here every hit must clear a
similarity floor. If nothing clears it, the caller gets an empty list and refuses to answer.

The embedder is a dependency-free TF cosine so the whole project runs offline. Swap
`embed()` for a real embedding model and nothing else changes: the score floor, citations, and
eval all keep working.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field


_WORD = re.compile(r"[a-z0-9]+")
# Tokens too common to carry meaning. Without this, two texts "match" just because they both
# say "the policy is that the ...".
_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "be", "to", "of", "and", "or", "in", "on",
    "for", "with", "that", "this", "it", "as", "at", "by", "from", "you", "your", "we", "our",
    "if", "then", "will", "can", "do", "does", "how", "what", "when", "which", "not", "no",
}


def tokenize(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in _STOP and len(t) > 1]


def embed(text: str) -> Counter:
    """Bag-of-words term-frequency 'vector'. Deterministic, offline, good enough to demonstrate
    the mechanism. Replace with a provider embedding call in production."""
    return Counter(tokenize(text))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True)
class Chunk:
    doc_id: str      # e.g. "returns-policy"
    section: str     # e.g. "§2 Timeframe"  — cited back to the user
    text: str

    @property
    def citation(self) -> str:
        return f"{self.doc_id} — {self.section}"


@dataclass
class Hit:
    chunk: Chunk
    score: float


@dataclass
class Retriever:
    chunks: list[Chunk]
    score_floor: float = 0.12
    _index: list[tuple[Chunk, Counter]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._index = [(c, embed(c.text)) for c in self.chunks]

    def search(self, query: str, k: int = 3, score_floor: float | None = None) -> list[Hit]:
        """Return at most k hits, each at or above the score floor. May return []."""
        floor = self.score_floor if score_floor is None else score_floor
        qv = embed(query)
        scored = [Hit(c, round(cosine(qv, cv), 4)) for c, cv in self._index]
        scored.sort(key=lambda h: h.score, reverse=True)
        return [h for h in scored if h.score >= floor][:k]
