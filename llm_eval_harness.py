"""
llm_eval_harness.py  —  score LLM outputs three honest ways, then gate on drift.

Most "evals" are one number you can game. This is three lenses that disagree usefully:

  1. Rubric scoring     -> weighted criteria with hard auto-fail rules
  2. LLM-as-judge       -> pairwise A/B so a new prompt/model must BEAT the baseline, not just pass
  3. Reference metrics  -> exact-match / contains for the cases where truth is known

Aggregates into a scorecard and a regression gate that blocks a change when quality drops.
Runs offline: the "model" and "judge" are deterministic stubs so you can see the mechanism.
Swap `stub_model` / `stub_judge` for real provider calls and nothing else changes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


# --------------------------------------------------------------------------- #
@dataclass
class Case:
    prompt: str
    reference: str | None = None          # known answer, if any
    must_contain: list[str] = field(default_factory=list)
    auto_fail_if_contains: list[str] = field(default_factory=list)


@dataclass
class Rubric:
    # name -> (weight, scorer(output)->0..1)
    criteria: dict[str, tuple[float, Callable[[str], float]]]
    pass_threshold: float = 0.7

    def score(self, output: str) -> dict:
        total_w = sum(w for w, _ in self.criteria.values()) or 1.0
        parts, weighted = {}, 0.0
        for name, (w, fn) in self.criteria.items():
            s = max(0.0, min(1.0, fn(output)))
            parts[name] = round(s, 3)
            weighted += w * s
        return {"weighted": round(weighted / total_w, 3), "parts": parts}


# --------------------------------------------------------------------------- #
def reference_metrics(output: str, case: Case) -> dict:
    ok_contains = all(k.lower() in output.lower() for k in case.must_contain)
    exact = (case.reference is not None and output.strip().lower() == case.reference.strip().lower())
    auto_fail = any(b.lower() in output.lower() for b in case.auto_fail_if_contains)
    return {"exact_match": exact, "contains_ok": ok_contains, "auto_fail": auto_fail}


def judge_pairwise(judge: Callable[[str, str, str], str], prompt, a, b) -> str:
    """Returns 'A', 'B', or 'tie'. Judge is order-sensitive in reality, so we run both orders."""
    r1 = judge(prompt, a, b)
    r2 = judge(prompt, b, a)  # swapped
    if r1 == "A" and r2 == "B":
        return "A"
    if r1 == "B" and r2 == "A":
        return "B"
    return "tie"  # disagreement under swap => not a robust win


# --------------------------------------------------------------------------- #
def evaluate(model, cases: list[Case], rubric: Rubric) -> dict:
    rows, passed = [], 0
    for c in cases:
        out = model(c.prompt)
        rub = rubric.score(out)
        met = reference_metrics(out, c)
        ok = (rub["weighted"] >= rubric.pass_threshold and met["contains_ok"] and not met["auto_fail"])
        passed += ok
        rows.append({"prompt": c.prompt, "pass": ok, "rubric": rub["weighted"], **met})
    return {"pass_rate": round(passed / max(len(cases), 1), 3), "n": len(cases), "rows": rows}


def regression_gate(baseline: dict, candidate: dict, judge, cases, baseline_model, cand_model,
                    max_drop=0.0) -> dict:
    """Candidate must not drop pass_rate AND must win/tie the pairwise judge on average."""
    drop = baseline["pass_rate"] - candidate["pass_rate"]
    wins = 0
    for c in cases:
        w = judge_pairwise(judge, c.prompt, cand_model(c.prompt), baseline_model(c.prompt))
        wins += 1 if w == "A" else (0.5 if w == "tie" else 0)
    win_rate = wins / max(len(cases), 1)
    ship = (drop <= max_drop) and (win_rate >= 0.5)
    return {"ship": ship, "pass_rate_drop": round(drop, 3), "judge_win_rate": round(win_rate, 3)}


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Stubs: baseline is decent, candidate is better on one case, worse on none.
    def baseline_model(p): return {"capital of france": "Paris.",
                                   "2+2": "4",
                                   "refund policy": "Refunds within 30 days."}.get(p.lower(), "I don't know.")
    def candidate_model(p): return {"capital of france": "The capital of France is Paris.",
                                    "2+2": "4",
                                    "refund policy": "Refunds are available within 30 days of purchase."}.get(p.lower(), "I don't know.")

    def stub_judge(prompt, a, b):  # prefers the longer, more complete answer (toy heuristic)
        return "A" if len(a) >= len(b) else "B"

    cases = [
        Case("Capital of France", reference="Paris.", must_contain=["Paris"]),
        Case("2+2", reference="4", must_contain=["4"]),
        Case("Refund policy", must_contain=["30 days"], auto_fail_if_contains=["no refunds"]),
    ]
    rubric = Rubric(criteria={
        "non_empty": (1.0, lambda o: 1.0 if o.strip() and "don't know" not in o else 0.0),
        "concise":   (0.5, lambda o: 1.0 if len(o) < 120 else 0.5),
    })

    base = evaluate(baseline_model, cases, rubric)
    cand = evaluate(candidate_model, cases, rubric)
    gate = regression_gate(base, cand, stub_judge, cases, baseline_model, candidate_model)
    import json
    print("BASELINE:", json.dumps({k: base[k] for k in ("pass_rate", "n")}))
    print("CANDIDATE:", json.dumps({k: cand[k] for k in ("pass_rate", "n")}))
    print("GATE:", json.dumps(gate))
    print("Ship candidate?", gate["ship"])
