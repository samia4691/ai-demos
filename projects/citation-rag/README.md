# citation-rag — retrieval that cites its sources and refuses to guess

A small, complete RAG project built around one non-negotiable rule: **if no source clears the
relevance floor, the system refuses to answer.** That single guarantee is the difference between
a knowledge assistant a business can trust and one that invents policy under load.

Runs offline with **no dependencies and no API keys** — the embedder and generation step are
stubbed so you can read the mechanism, not a framework hiding it. Swap the stubs for a real
embedding model and an LLM call and the surrounding logic (score floor, citations, evaluation,
regression gate) is unchanged.

## What it demonstrates

- **Score-floor retrieval** (`rag/retriever.py`) — every hit must clear a similarity floor; the
  retriever is allowed to return nothing.
- **Grounded-or-refuse answering** (`rag/answer.py`) — an answer is either backed by cited
  chunks or it is an honest "I don't have that in the provided documents."
- **Separated evaluation** (`rag/eval.py`) — *answerability* (answer when you can, refuse when
  you can't) and *citation validity* (did we cite the right document) are scored independently on
  a gold set.
- **A regression gate** — a config change ships only if neither metric drops. The demo shows the
  gate catching a tempting "just lower the floor so we always answer" change that quietly breaks
  the refusal behavior.

## Layout

```
citation-rag/
  rag/
    retriever.py   # score-floor TF-cosine retrieval (swap embed() for a real model)
    answer.py      # grounded-or-refuse contract
    eval.py        # gold set, answerability + citation metrics, regression gate
    corpus.py      # tiny sample corpus (returns policy, security, SLA)
  tests/test_rag.py
  run.py           # end-to-end demo
```

## Run it

```bash
cd citation-rag
python run.py        # grounded answer, a refusal, the eval report, and the gate in action
pytest -q            # 5 tests: citation present, refusal works, floor matters, gate blocks a drop
```

Expected: an in-corpus question returns a cited answer, an out-of-corpus question is refused,
the gold-set eval reports 1.0 answerability, and dropping the score floor to 0 is **blocked** by
the regression gate.

## Taking it to production

- Replace `embed()` with your embedding provider and store vectors in a real index
  (pgvector/Qdrant/Pinecone). The score floor still applies.
- Replace the extractive step in `answer.py` with a generation call whose system prompt says
  "answer only from the context; if it is not there, say you don't know" — the code-level refusal
  stays as the backstop the model can't override.
- Keep the gold set in version control and run `eval.py` in CI so retrieval quality can't
  silently drift.

---
Samia M. — AI / LLM Engineer · [portfolio](https://samia4691.github.io/) ·
representative reference project
