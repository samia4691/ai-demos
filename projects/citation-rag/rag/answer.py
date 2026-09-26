"""
Compose an answer that is either grounded-and-cited or an honest refusal.

There is no LLM call here on purpose: the demo keeps the *contract* visible. In production the
retrieved chunks become the context for a generation call whose system prompt says "answer only
from the context; if it is not there, say you don't know." The guarantee this module encodes —
no supporting chunk above the floor means no answer — is enforced in code, not left to the model.
"""
from __future__ import annotations

from dataclasses import dataclass

from .retriever import Retriever, Hit

REFUSAL = "I don't have that in the provided documents."


@dataclass
class Answer:
    text: str
    citations: list[str]
    grounded: bool
    hits: list[Hit]

    def render(self) -> str:
        if not self.grounded:
            return REFUSAL
        cites = "\n".join(f"  [{i + 1}] {c}" for i, c in enumerate(self.citations))
        return f"{self.text}\n\nSources:\n{cites}"


def answer(query: str, retriever: Retriever, score_floor: float | None = None, k: int = 3) -> Answer:
    hits = retriever.search(query, k=k, score_floor=score_floor)
    if not hits:
        # Nothing cleared the floor -> refuse. This is the whole point.
        return Answer(text=REFUSAL, citations=[], grounded=False, hits=[])
    # Extractive stand-in for generation: lead with the best chunk, cite every chunk used.
    best = hits[0].chunk
    citations = [h.chunk.citation for h in hits]
    return Answer(text=best.text, citations=citations, grounded=True, hits=hits)
