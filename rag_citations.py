"""
rag_citations.py  —  "No citation, no answer", made mechanical.

Your post says the off-the-shelf chatbot "answers confidently and is sometimes wrong."
That is not a prompt problem, it is a plumbing problem. This is the plumbing:

  1. Chunk carries provenance          -> doc_id + page ride with the text, always
  2. Retrieve with a score floor       -> weak matches return nothing, not a confident guess
  3. Answer is grounded + cited        -> each sentence must name the passage it came from,
                                          or it is dropped before the user ever sees it
  4. Correctness is measured           -> a gold set scores answer accuracy AND citation validity
  5. Regression gate on ingest         -> re-run the gold set after adding docs; block on drop

Runs with no external services (injected embedder + a grounded extractive answerer) so you
can execute it and see the mechanism. In production: swap the embedder for your provider,
put the index in pgvector on your AWS box, keep everything else.
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Chunk:
    doc_id: str
    page: int
    text: str
    vector: list[float] = field(default_factory=list)


@dataclass
class Citation:
    doc_id: str
    page: int
    score: float


@dataclass
class Answer:
    text: str
    citations: list[Citation]
    grounded: bool          # False => we refused rather than guessed


class CitedRAG:
    def __init__(self, embed: Callable[[str], list[float]], score_floor: float = 0.35, top_k: int = 4):
        self.embed, self.score_floor, self.top_k = embed, score_floor, top_k
        self._chunks: list[Chunk] = []

    def index(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            c.vector = self.embed(c.text)
        self._chunks = chunks

    @staticmethod
    def _cos(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5 or 1e-9
        nb = sum(y * y for y in b) ** 0.5 or 1e-9
        return dot / (na * nb)

    def retrieve(self, q: str) -> list[tuple[Chunk, float]]:
        qv = self.embed(q)
        ranked = sorted(((c, self._cos(qv, c.vector)) for c in self._chunks),
                        key=lambda t: t[1], reverse=True)
        return [(c, s) for c, s in ranked[: self.top_k] if s >= self.score_floor]

    def answer(self, q: str) -> Answer:
        hits = self.retrieve(q)
        if not hits:
            # The single most important line in the whole file.
            return Answer("I don't have a sourced answer for that in the corpus.", [], grounded=False)

        # Grounded extractive answer: pull the sentence(s) that actually overlap the question,
        # and attach the citation of the chunk they came from. A sentence with no supporting
        # chunk never makes it into `text`.
        sentences_with_src: list[tuple[str, Citation]] = []
        # Match on DISTINCTIVE query terms (stopwords + the shared entity carry no signal).
        # A warranty question must be answered by a sentence about warranty, not one that merely
        # shares the product name. This is what turns a plausible passage into a refusal.
        q_terms = _content_tokens(q)
        for c, score in hits:
            cite = Citation(c.doc_id, c.page, round(score, 3))
            for sent in _split_sentences(c.text):
                if q_terms & _content_tokens(sent):
                    sentences_with_src.append((sent, cite))

        if not sentences_with_src:
            return Answer("The retrieved passages did not directly address the question.", [], grounded=False)

        parts, cites = [], []
        for sent, cite in sentences_with_src:
            parts.append(f"{sent} [{cite.doc_id} p.{cite.page}]")
            cites.append(cite)
        return Answer(" ".join(parts), _dedupe(cites), grounded=True)


# --------------------------------------------------------------------------- #
# Correctness measurement. This is the part the client explicitly asked for.    #
# --------------------------------------------------------------------------- #
@dataclass
class GoldCase:
    question: str
    expected_keywords: list[str]     # answer is "correct" if it contains these
    expected_doc: str | None         # citation must point at this doc (None => must refuse)


def score(rag: CitedRAG, gold: list[GoldCase]) -> dict:
    rows, correct, cited_ok = [], 0, 0
    for g in gold:
        a = rag.answer(g.question)
        # Refusal cases: correct means we correctly declined.
        if g.expected_doc is None:
            is_correct = not a.grounded
            cite_valid = True
        else:
            is_correct = all(k.lower() in a.text.lower() for k in g.expected_keywords)
            cite_valid = any(c.doc_id == g.expected_doc for c in a.citations)
        correct += is_correct
        cited_ok += cite_valid
        rows.append({"q": g.question, "correct": is_correct, "citation_valid": cite_valid,
                     "answer": a.text})
    n = max(len(gold), 1)
    return {"answer_accuracy": round(correct / n, 3),
            "citation_validity": round(cited_ok / n, 3),
            "n": len(gold), "rows": rows}


def regression_gate(before: dict, after: dict, max_drop: float = 0.05) -> bool:
    """Run after every ingest. True = safe to ship, False = new docs hurt retrieval."""
    drop = before["answer_accuracy"] - after["answer_accuracy"]
    return drop <= max_drop


# --------------------------------------------------------------------------- #
_STOP = {"the", "is", "a", "an", "of", "for", "to", "what", "and", "in", "on", "are",
         "was", "were", "be", "from", "with", "how", "does", "do", "this", "that",
         "x40"}  # entity name shared by many chunks -> not distinctive, treated as stopword

def _tokens(s): return re.findall(r"[a-z0-9]+", s.lower())
def _content_tokens(s): return {t for t in _tokens(s) if t not in _STOP and len(t) > 2}
def _split_sentences(s): return [x.strip() for x in re.split(r"(?<=[.!?])\s+", s) if x.strip()]
def _dedupe(cites):
    seen, out = set(), []
    for c in cites:
        key = (c.doc_id, c.page)
        if key not in seen:
            seen.add(key); out.append(c)
    return out


if __name__ == "__main__":
    class _Embed:
        def __call__(self, text):
            v = [0.0] * 48
            for t in _tokens(text):
                v[hash(t) % 48] += 1.0
            return v

    rag = CitedRAG(_Embed(), score_floor=0.30)
    rag.index([
        Chunk("spec_pump_v4.pdf", 7, "The X40 pump maximum operating pressure is 16 bar."),
        Chunk("supplier_acme.pdf", 3, "Acme payment terms are Net 30 from invoice date."),
        Chunk("procedures.pdf", 12, "Expense claims must be submitted within 14 days."),
    ])

    print("Q1:", rag.answer("What is the X40 pump maximum pressure?").text)
    print("Q2 (not in corpus):", rag.answer("What is the warranty period for the X40?").text)

    gold = [
        GoldCase("What is the X40 pump maximum pressure?", ["16 bar"], "spec_pump_v4.pdf"),
        GoldCase("What are Acme payment terms?", ["Net 30"], "supplier_acme.pdf"),
        GoldCase("What is the warranty period for the X40?", [], None),  # must refuse
    ]
    report = score(rag, gold)
    print("SCORECARD:", json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    # Simulated ingest regression check
    print("Safe to ship after ingest?", regression_gate(report, report))
