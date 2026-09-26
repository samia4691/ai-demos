# safe-support-agent — a support agent that deflects safely

Most support bots get switched off because they invent policy, leak customer data, or take an
action they shouldn't. This project is the opposite: an agent where **every risky thing is
blocked in code**, so it can actually be pointed at customers.

It ties four of my building blocks into one deployable system:

- **Grounded answers** — policy questions are answered from the knowledge base *with a citation*,
  and if the KB doesn't cover it the agent **refuses and escalates** instead of guessing.
- **Prompt-injection detection** — on the customer message *and* on tool output (a poisoned CRM
  note is a real attack). A flagged message is escalated and **no tools run**.
- **Scoped tools** — reading an order status is allowed; issuing a refund needs the `write:refunds`
  scope, which the default agent does not hold.
- **Human approval on money** — a refund is never executed by the agent. It returns a pending
  action for a teammate to approve.
- **PII redaction** — emails, phone numbers, card and SSN patterns are stripped from anything the
  agent sends back or logs.

Runs offline, no dependencies, no API keys — the model calls and datastore are stubbed so the
*safety contract* is what you read, not a framework.

## The pipeline (every message)

```
message
  -> injection scan (user text)        -- flagged? escalate, run nothing
  -> route intent
       refund?      -> human-approval gate (never auto-executed)
       order?       -> read tool (scope-checked) -> re-scan tool output -> redact
       otherwise    -> grounded KB answer (cite) or refuse+escalate
  -> PII/secret redaction on the reply
```

## Run it

```bash
cd support-agent
python run.py      # five messages: grounded answer, order lookup, refund gate, refusal, injection
pytest -q          # 7 tests covering each safety property
```

Expected: a cited policy answer, an order status from the read tool, a refund held for human
approval, a refusal on an out-of-scope question, and an injection attempt escalated with no tools
run.

## Layout

```
support-agent/
  support_agent/
    agent.py        # the safe orchestration pipeline
    guardrails.py   # injection detection, scope enforcement, PII redaction
    tools.py        # scoped read/write tools (refund requires approval)
    retrieval.py    # score-floor KB retrieval (cite or refuse)
  tests/test_agent.py
  run.py
```

## Production notes

- Swap the rule-based router for an LLM intent classifier, and the extractive KB answer for a
  generation call grounded on the retrieved chunk. The code-level guarantees (approval gate,
  scope checks, injection escalation, redaction) stay as the backstop the model can't override.
- Wire `issue_refund` to your real approval queue; grant `write:refunds` only to the agent
  instance behind it.

---
Samia M. — AI / LLM Engineer · [portfolio](https://samia4691.github.io/) ·
representative reference project
