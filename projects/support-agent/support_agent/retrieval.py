"""
Compact score-floor retrieval over the support knowledge base, so policy answers are grounded
and cited, and the agent refuses when the policy does not cover the question (instead of
inventing a policy — the classic support-bot failure).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "is", "are", "to", "of", "and", "or", "in", "on", "for", "with",
         "that", "this", "it", "as", "at", "by", "from", "your", "you", "we", "our", "do",
         "does", "how", "what", "can", "i", "my", "if"}


def _tok(t: str) -> list[str]:
    return [w for w in _WORD.findall(t.lower()) if w not in _STOP and len(w) > 1]


def _vec(t: str) -> Counter:
    return Counter(_tok(t))


def _cos(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


@dataclass(frozen=True)
class Doc:
    doc_id: str
    text: str


KB = [
    Doc("returns §2", "Customers may request a return within 30 days of delivery."),
    Doc("returns §3", "Approved refunds go to the original payment method within 5 to 7 business days."),
    Doc("shipping §1", "Standard shipping takes 3 to 5 business days. Express is next business day."),
    Doc("warranty §4", "Hardware carries a 12 month limited warranty against manufacturing defects."),
]


class KBRetriever:
    def __init__(self, docs: list[Doc] = KB, score_floor: float = 0.12):
        self.docs = docs
        self.floor = score_floor
        self._idx = [(d, _vec(d.text)) for d in docs]

    def top(self, query: str) -> tuple[Doc, float] | None:
        qv = _vec(query)
        best, best_s = None, 0.0
        for d, dv in self._idx:
            s = _cos(qv, dv)
            if s > best_s:
                best, best_s = d, s
        if best is None or best_s < self.floor:
            return None
        return best, round(best_s, 4)
