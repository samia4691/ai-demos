# Samia M. — AI Engineering Portfolio

A reusable asset library for Upwork proposals. Each theme has a one-page architecture diagram (PNG, attach to proposals) and a runnable code demo (link in the proposal). Pick the asset that matches the job.

**Runnable code repo:** https://github.com/samia4691/ai-demos
**Diagrams:** in the `diagrams/` folder (PNG + editable SVG)

---

## The six themes, and when to use each

**1. Citation-Grounded RAG** — `01_citation_grounded_rag.png` + `rag_citations.py`
Use for: RAG jobs, "chatbot over our documents," hallucination complaints, doc Q&A, knowledge bases.
Hook: retrieval with a score floor so weak matches return nothing instead of a confident-wrong answer; every answer cites doc + page; correctness eval with a regression gate on ingest.

**2. Reliable Multi-Agent Harness** — `02_reliable_multi_agent_harness.png` + `agent_harness.py`
Use for: "fix our unstable agents," multi-agent builds, LangGraph/CrewAI work, agent platforms.
Hook: one codebase where a new agent is a config file; provider abstraction, retries + termination, schema validation with repair, tool registry, run logging + eval.

**3. Secure MCP Server** — `03_secure_mcp_server.png` + `mcp_server.py`
Use for: MCP server builds, "expose our platform to ChatGPT/Claude/Cursor," tool integration.
Hook: JWT → tenant + scope, deny by default; read vs write scopes; tenant-filtered queries; idempotent writes; a read-only token is provably blocked from a write.

**4. LLM Evaluation & Regression Gating** — `04_llm_evaluation_gating.png` + `finance_eval_rubric.md` / `redcrown_eval_plan.md`
Use for: model-eval jobs, RLHF/rubric work, agent testing, "which model should we use," QA of AI output.
Hook: gold set, three scoring lenses (exact-match, LLM-as-judge, trajectory), cost/quality/latency, a gate that blocks quality drift.

**5. AI Automation / Document Extraction** — `05_ai_automation_extraction.png` + `rag_citations.py` (extraction pattern)
Use for: document extraction, OCR pipelines, workflow automation, "turn our messy files into structured data."
Hook: unstructured → OCR → schema-enforced LLM extract → validation → business rules → human-in-the-loop → clean output, with async workers so heavy steps never block the API.

**6. LLM Cost & Performance Optimization** — `06_llm_cost_perf_optimization.png`
Use for: "our AI pipeline is slow/expensive," latency debugging, scaling, Ollama/self-hosted LLM perf.
Hook: profile every stage first, find the real bottleneck (model reload, serial vs concurrent, GPU thrash), targeted fixes — not a rewrite.

---

## How to use in a proposal
1. Open on the client's nerve (their specific pain).
2. Reference one concrete detail from their post.
3. Attach the matching diagram PNG + link the matching repo file with a line like "I already built the shape of this."
4. One sharp idea or question. Clear next step. Short, human, no filler.

## Profile one-liner
AI / LLM engineer, 8+ years. Production RAG, agent systems, model evaluation, MCP servers, and Python/FastAPI backends. I ship reliability and correctness, not demos.
