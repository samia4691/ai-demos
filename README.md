# AI Engineering — runnable demos

Self-contained slices of production patterns I build for clients. Every Python file runs on its
own with no external services or API keys — model, embedder, OCR, and judge calls are stubbed so
you can read the *mechanism*, not a framework hiding it. Swap a stub for a real provider call and
the surrounding logic (validation, scoring, safety, gating) is unchanged.

## Core
| File | What it shows | Run |
|---|---|---|
| [`rag_citations.py`](rag_citations.py) | Citation-grounded RAG. Score-floor retrieval so weak matches return **nothing**; answers cite doc+page; accuracy and citation-validity scored separately, with a regression gate. | `python rag_citations.py` |
| [`agent_harness.py`](agent_harness.py) | One codebase, N agents. Provider abstraction, model-call loop with retries + token accounting, schema validation with a repair path, small eval harness. Agent #11 is YAML, not a commit. | `python agent_harness.py` |
| [`mcp_server.py`](mcp_server.py) | Production-shaped MCP server. JWT→tenant+scope, deny by default, read vs write scopes, tenant isolation, idempotent writes. Prints a read-only token blocked from a write. | `python mcp_server.py` |

## Evaluation
| File | What it shows | Run |
|---|---|---|
| [`llm_eval_harness.py`](llm_eval_harness.py) | Three-lens LLM eval: weighted rubric with auto-fails, LLM-as-judge **pairwise** (order-swapped so a win is robust), and reference metrics — plus a regression gate that ships a change only if it doesn't drop pass-rate **and** beats the baseline. | `python llm_eval_harness.py` |
| [`finance_eval_rubric.md`](finance_eval_rubric.md) | A domain scoring rubric with hard auto-fail rules + graded good/bad cases. | read |
| [`redcrown_eval_plan.md`](redcrown_eval_plan.md) | How I design a head-to-head model eval with hand-labeled ground truth and cost-per-correct-answer. | read |

## Automation & data
| File | What it shows | Run |
|---|---|---|
| [`doc_extraction.py`](doc_extraction.py) | Unstructured docs → OCR (per-field confidence) → schema-enforced extraction → validation → business rules → **confidence gate** (auto-approve / human review / reject). Never silently wrong. | `python doc_extraction.py` |
| [`text_to_sql.py`](text_to_sql.py) | Natural language → **safe** SQL: schema validation, read-only enforcement, an always-injected tenant filter, row caps, and parameterized values. "DROP TABLE" stays a harmless SELECT. | `python text_to_sql.py` |

## Reliability, safety & performance
| File | What it shows | Run |
|---|---|---|
| [`guardrails.py`](guardrails.py) | Agent safety in code: prompt-injection detection on user **and tool-returned** text, tool-permission scopes, and secret/PII redaction on the way out. The injection attempt is blocked before it can act. | `python guardrails.py` |
| [`llm_profiler.py`](llm_profiler.py) | Find why an LLM pipeline is slow before changing a line: per-stage timings, the real bottleneck (model reload, serial vs concurrent), and the projected speedup from targeted fixes. | `python llm_profiler.py` |

## Background
AI / LLM engineer, 8+ years. Production RAG, agent systems, model evaluation, MCP servers, AI
automation, and Python/FastAPI backends. I ship reliability and correctness, not demos.
