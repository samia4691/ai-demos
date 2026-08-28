"""
llm_profiler.py  —  find why an LLM pipeline is slow, before changing a line.

The recurring "our AI pipeline is slow / expensive" job. The trap is guessing. This measures
each stage, then flags the real bottleneck and names the fix. It reproduces the classic finding:
the model call itself is fast, but the pipeline around it (serial work, model reloads, idle GPU)
is where the wall-clock goes.

Deterministic timings via an injected clock so the demo is reproducible (no real sleeping).
In production, wrap real stages with `profile()` and feed wall-clock times.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Stage:
    name: str
    ms: float
    parallelizable: bool = False   # could this run concurrently across items?
    note: str = ""


@dataclass
class Report:
    stages: list[Stage]
    n_items: int

    @property
    def per_item_ms(self): return sum(s.ms for s in self.stages)

    def serial_total_ms(self): return self.per_item_ms * self.n_items

    def optimized_total_ms(self, concurrency=8):
        """Parallelizable stages amortize across concurrency; serial stages do not."""
        par = sum(s.ms for s in self.stages if s.parallelizable)
        ser = sum(s.ms for s in self.stages if not s.parallelizable)
        return ser * self.n_items + (par * self.n_items) / concurrency

    def bottleneck(self):
        return max(self.stages, key=lambda s: s.ms)

    def findings(self):
        out = []
        b = self.bottleneck()
        out.append(f"Bottleneck stage: '{b.name}' at {b.ms:.0f} ms/item ({b.ms/self.per_item_ms:.0%} of per-item time).")
        reloady = [s for s in self.stages if "reload" in s.note.lower()]
        if reloady:
            out.append("Model reload detected between calls — set keep_alive so the model stays resident. "
                       "This alone can remove the largest fixed cost.")
        serial_par = [s for s in self.stages if s.parallelizable]
        if serial_par:
            names = ", ".join(s.name for s in serial_par)
            out.append(f"Stages that are parallelizable but appear to run serially: {names}. "
                       f"Process items concurrently instead of one at a time.")
        return out


def summarize(r: Report, concurrency=8) -> dict:
    serial = r.serial_total_ms()
    opt = r.optimized_total_ms(concurrency)
    return {
        "items": r.n_items,
        "per_item_ms": round(r.per_item_ms, 1),
        "current_total_s": round(serial / 1000, 1),
        "optimized_total_s": round(opt / 1000, 1),
        "speedup": f"{serial/opt:.1f}x" if opt else "n/a",
        "findings": r.findings(),
    }


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import json
    # Measured (or simulated) per-item stage timings for a PDF -> LLM pipeline.
    stages = [
        Stage("file_discovery",   15,  parallelizable=True),
        Stage("ocr_extract",     900,  parallelizable=True),
        Stage("prompt_prep",      20,  parallelizable=True),
        Stage("model_load",     1200,  parallelizable=False, note="model reloaded each call"),
        Stage("ollama_call",     400,  parallelizable=True),
        Stage("json_parse",       10,  parallelizable=True),
        Stage("db_write",         60,  parallelizable=False),
    ]
    report = Report(stages=stages, n_items=100)
    result = summarize(report, concurrency=8)
    print(json.dumps({k: v for k, v in result.items() if k != "findings"}, indent=2))
    print("\nFindings:")
    for f in result["findings"]:
        print(" -", f)
