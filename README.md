# AI Engineering — runnable demos

Small, self-contained slices of production patterns I build for clients: retrieval that refuses
to guess, an agent harness where a new agent is a config file, a secure MCP server, and evaluation
that measures correctness. Every Python file runs on its own with no external services or API keys —
the model/embedder calls are stubbed so you can read the *mechanism*, not a framework hiding it.

| File | What it shows | Run |
|---|---|---|
| [`rag_citations.py`](rag_citations.py) | Citation-grounded RAG. Retrieval with a score floor so weak matches return **nothing** instead of a confident-wrong answer. Answer accuracy and citation validity scored separately, plus a regression gate for new ingests. | `python rag_citations.py` |
| [`agent_harness.py`](agent_harness.py) | One codebase, N agents. Provider abstraction, config-defined agents, model-call loop with retries + token accounting, schema validation with a repair path, and a small eval harness. Agent #11 is a block of YAML, not a commit. | `python agent_harness.py` |
| [`mcp_server.py`](mcp_server.py) | A production-shaped MCP server slice. Every tool call resolves a JWT to a tenant + scope, denied by default. Read vs write scopes, tenant isolation, idempotent writes, validated args. Prints a read-only token being blocked from a write. | `python mcp_server.py` |
| [`finance_eval_rubric.md`](finance_eval_rubric.md) | A personal-finance LLM scoring rubric with hard auto-fail rules, plus graded cases separating a correct answer from a plausible-but-wrong one. | read |
| [`redcrown_eval_plan.md`](redcrown_eval_plan.md) | How I design a head-to-head model eval: real task, hand-labeled ground truth, cost-per-correct-answer as the decision metric. | read |

## Background
AI / LLM engineer, 8+ years. Production RAG, agent systems, model evaluation, and Python/FastAPI
backends. These demos are the shape of what I ship, trimmed to fit in one readable file each.
