"""
agent_harness.py  —  one codebase, N agents, agent #11 is a config file not a commit.

A trimmed but real slice of the shared harness described in the brief. It shows the
five things that decide whether "add an agent = add a config" actually holds:

  1. Provider abstraction        -> swap the model without touching agent code
  2. Config-defined agents       -> prompt, doc set, tools, output schema live in YAML
  3. The model-call loop         -> retries, timeout, rate-limit backoff, token accounting
  4. Schema-validated output     -> with a defined repair path when the model won't comply
  5. Retrieval + a tiny eval     -> return the *right* passages, and prove it against gold cases

Retrieval here uses a cosine index over an injected embedder so the file runs with no
external services. Swap _LocalEmbedder for your provider's embeddings and the rest is unchanged.
Deliberately no framework: LangChain/LlamaIndex hide exactly the loop the brief cares about.
"""

from __future__ import annotations

import json
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("harness")


# --------------------------------------------------------------------------- #
# 1. Provider abstraction. Agents never import a vendor SDK. One place to swap. #
# --------------------------------------------------------------------------- #
class ChatProvider(Protocol):
    def complete(self, system: str, messages: list[dict], *, temperature: float) -> "LLMResponse": ...


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int


@dataclass
class TokenLedger:
    prompt: int = 0
    completion: int = 0

    def add(self, r: LLMResponse) -> None:
        self.prompt += r.prompt_tokens
        self.completion += r.completion_tokens

    def cost_usd(self, in_rate: float, out_rate: float) -> float:
        return self.prompt / 1e6 * in_rate + self.completion / 1e6 * out_rate


# --------------------------------------------------------------------------- #
# 2. Retrieval. The screening question: right context, not plausible context.  #
#    Answer: chunk with provenance, retrieve top-k, then apply a score floor so #
#    "nothing good enough" returns nothing instead of the least-bad guess.      #
# --------------------------------------------------------------------------- #
@dataclass
class Chunk:
    doc_id: str
    page: int
    text: str
    vector: list[float] = field(default_factory=list)


class Retriever:
    def __init__(self, embed: Callable[[str], list[float]], score_floor: float = 0.35):
        self.embed = embed
        self.score_floor = score_floor
        self._chunks: list[Chunk] = []

    def index(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            c.vector = self.embed(c.text)
        self._chunks = chunks

    @staticmethod
    def _cos(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5 or 1e-9
        nb = sum(y * y for y in b) ** 0.5 or 1e-9
        return dot / (na * nb)

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        qv = self.embed(query)
        ranked = sorted(((c, self._cos(qv, c.vector)) for c in self._chunks),
                        key=lambda t: t[1], reverse=True)
        hits = [(c, s) for c, s in ranked[:k] if s >= self.score_floor]
        # Returning [] is a feature: a weak match becomes "I don't have that",
        # which is what stops confident-but-wrong answers downstream.
        return hits


# --------------------------------------------------------------------------- #
# 3 + 4. The agent: defined entirely by config, run through the shared loop.    #
# --------------------------------------------------------------------------- #
@dataclass
class AgentConfig:
    name: str
    system_prompt: str
    output_schema: dict          # a minimal JSON-schema-ish contract
    temperature: float = 0.0
    max_attempts: int = 3
    timeout_s: float = 30.0


class SchemaError(ValueError):
    pass


def validate(payload: dict, schema: dict) -> None:
    """Tiny structural validator. In production this is jsonschema.Draft202012Validator."""
    for key, spec in schema.items():
        if key not in payload:
            raise SchemaError(f"missing required field '{key}'")
        want = spec["type"]
        val = payload[key]
        ok = {"string": str, "number": (int, float), "boolean": bool,
              "array": list, "object": dict}[want]
        if not isinstance(val, ok):
            raise SchemaError(f"field '{key}' must be {want}, got {type(val).__name__}")


class Agent:
    def __init__(self, cfg: AgentConfig, provider: ChatProvider, retriever: Retriever | None = None):
        self.cfg, self.provider, self.retriever = cfg, provider, retriever

    def run(self, user_input: str) -> dict:
        ledger = TokenLedger()
        context, citations = self._gather_context(user_input)
        messages = [{"role": "user", "content": self._compose(user_input, context)}]
        last_err: str | None = None

        for attempt in range(1, self.cfg.max_attempts + 1):
            system = self.cfg.system_prompt
            if last_err:  # the repair path: tell the model exactly what it broke
                system += (f"\n\nYour previous reply failed validation: {last_err}. "
                           f"Return ONLY JSON matching the schema. No prose.")
            resp = self._call_with_retry(system, messages, self.cfg.temperature, self.cfg.timeout_s)
            ledger.add(resp)
            try:
                payload = json.loads(_extract_json(resp.text))
                validate(payload, self.cfg.output_schema)
                return {"ok": True, "data": payload, "citations": citations,
                        "attempts": attempt, "tokens": ledger.__dict__}
            except (json.JSONDecodeError, SchemaError) as e:
                last_err = str(e)
                log.warning("[%s] attempt %d rejected: %s", self.cfg.name, attempt, last_err)

        # Defined path when the model never complies: fail loud, never emit junk downstream.
        return {"ok": False, "error": f"schema not satisfied after {self.cfg.max_attempts} attempts: {last_err}",
                "citations": citations, "tokens": ledger.__dict__}

    def _gather_context(self, q: str) -> tuple[str, list[dict]]:
        if not self.retriever:
            return "", []
        hits = self.retriever.search(q)
        if not hits:
            return "", []
        blocks, cites = [], []
        for c, score in hits:
            blocks.append(f"[{c.doc_id} p.{c.page}] {c.text}")
            cites.append({"doc_id": c.doc_id, "page": c.page, "score": round(score, 3)})
        return "\n".join(blocks), cites

    def _compose(self, user_input: str, context: str) -> str:
        if context:
            return (f"Context passages (cite doc_id and page for every claim; "
                    f"if the answer is not here, say so):\n{context}\n\nTask: {user_input}")
        return user_input

    def _call_with_retry(self, system, messages, temp, timeout) -> LLMResponse:
        delay = 1.0
        for i in range(4):
            try:
                return self.provider.complete(system, messages, temperature=temp)
            except (TimeoutError, RateLimitError) as e:
                log.warning("provider transient error (%s), backoff %.1fs", type(e).__name__, delay)
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("provider unavailable after retries")


class RateLimitError(Exception):
    pass


def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end != -1 else text


# --------------------------------------------------------------------------- #
# 5. The eval harness. A change is tested against known-good cases before ship. #
# --------------------------------------------------------------------------- #
@dataclass
class EvalCase:
    input: str
    expect: dict                 # field -> exact-ish expected value
    must_cite: bool = True


def evaluate(agent: Agent, cases: list[EvalCase]) -> dict:
    passed, failures = 0, []
    for case in cases:
        out = agent.run(case.input)
        ok = out["ok"]
        if ok and case.must_cite and not out["citations"]:
            ok = False
        if ok:
            for k, v in case.expect.items():
                if str(out["data"].get(k)).strip().lower() != str(v).strip().lower():
                    ok = False
                    failures.append({"input": case.input, "field": k,
                                     "want": v, "got": out["data"].get(k)})
                    break
        passed += ok
        if not ok and out.get("error"):
            failures.append({"input": case.input, "error": out["error"]})
    return {"passed": passed, "total": len(cases),
            "pass_rate": round(passed / max(len(cases), 1), 3), "failures": failures}


# --------------------------------------------------------------------------- #
# Runnable demo with a fake provider so the harness executes end to end.        #
# Agent #11 = another block of YAML below. No new Python.                        #
# --------------------------------------------------------------------------- #
"""
# agents/extract_supplier_terms.yaml   <-- adding an agent is this, nothing else
name: extract_supplier_terms
system_prompt: |
  Extract payment terms from the supplier agreement. Cite doc_id and page.
output_schema:
  vendor:        {type: string}
  net_days:      {type: number}
  currency:      {type: string}
temperature: 0.0
"""

if __name__ == "__main__":
    class _LocalEmbedder:
        """Bag-of-chars embedding. Stands in for provider embeddings so the demo needs no network."""
        def __call__(self, text: str) -> list[float]:
            v = [0.0] * 32
            for ch in text.lower():
                v[ord(ch) % 32] += 1.0
            return v

    class _FakeProvider:
        def complete(self, system, messages, *, temperature):
            # Pretends to read the injected context and return schema-valid JSON.
            content = messages[-1]["content"]
            net = "30" if "net 30" in content.lower() else "45"
            body = json.dumps({"vendor": "Acme Metals", "net_days": int(net), "currency": "EUR"})
            return LLMResponse(text=body, prompt_tokens=len(content) // 4, completion_tokens=12)

    embed = _LocalEmbedder()
    retr = Retriever(embed, score_floor=0.30)
    retr.index([
        Chunk("supplier_acme.pdf", 3, "Payment terms: Net 30 from invoice date. Currency EUR."),
        Chunk("procedures.pdf", 12, "Staff must submit expenses within 14 days."),
    ])

    cfg = AgentConfig(
        name="extract_supplier_terms",
        system_prompt="Extract payment terms. Cite doc_id and page. JSON only.",
        output_schema={"vendor": {"type": "string"}, "net_days": {"type": "number"},
                       "currency": {"type": "string"}},
    )
    agent = Agent(cfg, _FakeProvider(), retr)

    result = agent.run("What are Acme's payment terms?")
    print("RUN:", json.dumps(result, indent=2))

    report = evaluate(agent, [
        EvalCase("What are Acme's payment terms?", {"net_days": 30, "currency": "EUR"}),
    ])
    print("EVAL:", json.dumps(report, indent=2))
