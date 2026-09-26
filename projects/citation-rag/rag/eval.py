"""
Evaluation + regression gate.

Retrieval quality is not "it looked good in a demo." It is measured on a gold set, and a config
change ships only if it does not make things worse. Two things are scored separately:

  - answerability: when the answer IS in the corpus we must answer; when it is NOT we must refuse.
    (Refusing when you should answer, and answering when you should refuse, are both failures.)
  - citation validity: when we answer, the expected source document must be among the citations.

`regression_gate` compares a candidate against a baseline and blocks a drop.
"""
from __future__ import annotations

from dataclasses import dataclass

from .answer import answer
from .retriever import Retriever


@dataclass
class GoldCase:
    query: str
    answerable: bool          # is the answer present in the corpus at all?
    expected_doc: str | None = None   # which doc_id should be cited (when answerable)


GOLD: list[GoldCase] = [
    GoldCase("How long do I have to return an item?", True, "returns-policy"),
    GoldCase("How are refunds paid back?", True, "returns-policy"),
    GoldCase("How is data encrypted at rest?", True, "security-whitepaper"),
    GoldCase("How often are encryption keys rotated?", True, "security-whitepaper"),
    GoldCase("What is the uptime target?", True, "sla"),
    GoldCase("How fast is the first response for a critical incident?", True, "sla"),
    # Out-of-corpus: the system MUST refuse, not improvise.
    GoldCase("Do you offer a student discount?", False),
    GoldCase("What is your CEO's home address?", False),
]


@dataclass
class Report:
    answerability: float
    citation_validity: float
    n: int
    failures: list[str]

    @property
    def overall(self) -> float:
        return round((self.answerability + self.citation_validity) / 2, 4)


def evaluate(retriever: Retriever, gold: list[GoldCase] = GOLD) -> Report:
    ans_ok = 0
    cite_total = 0
    cite_ok = 0
    failures: list[str] = []

    for case in gold:
        a = answer(case.query, retriever)
        if a.grounded == case.answerable:
            ans_ok += 1
        else:
            want = "answer" if case.answerable else "refuse"
            got = "answered" if a.grounded else "refused"
            failures.append(f"answerability: '{case.query}' -> wanted {want}, {got}")

        if case.answerable:
            cite_total += 1
            cited_docs = {c.split(" — ")[0] for c in a.citations}
            if case.expected_doc in cited_docs:
                cite_ok += 1
            else:
                failures.append(
                    f"citation: '{case.query}' -> expected {case.expected_doc}, got {sorted(cited_docs) or 'none'}")

    return Report(
        answerability=round(ans_ok / len(gold), 4),
        citation_validity=round((cite_ok / cite_total) if cite_total else 1.0, 4),
        n=len(gold),
        failures=failures,
    )


def regression_gate(baseline: Report, candidate: Report, tolerance: float = 0.0) -> tuple[bool, str]:
    """Ship the candidate only if neither metric drops below baseline (minus tolerance)."""
    drops = []
    if candidate.answerability < baseline.answerability - tolerance:
        drops.append(f"answerability {baseline.answerability} -> {candidate.answerability}")
    if candidate.citation_validity < baseline.citation_validity - tolerance:
        drops.append(f"citation_validity {baseline.citation_validity} -> {candidate.citation_validity}")
    if drops:
        return False, "BLOCKED: " + "; ".join(drops)
    return True, "PASS: no regression"
