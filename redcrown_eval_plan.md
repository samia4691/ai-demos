# RedCrown eval — the real task I'd run through it

Deliberately short. This is a 45-minute beta run, not a build. Here is the task I would put
through RedCrown, so you know the feedback you get back will be about real usage, not a toy prompt.

**The shipped task:** a document-extraction step from a client RAG pipeline — pull `{vendor, net_days,
currency, effective_date}` from supplier PDFs as strict JSON. It runs thousands of times a day, so the
model choice is a real cost decision, not a vibe.

**Ground truth:** 60 documents I've already hand-labeled, so I can score exact-match on all four fields.

**The configs I'd pit head-to-head:**
- The model I default to now (GPT-class, temp 0) — my current production choice.
- A cheaper small model, same prompt — the "can I cut cost without losing accuracy" question.
- A mid-tier model with a stricter JSON-schema prompt — does better prompting close the gap the cheaper model opens.

**What I want RedCrown to tell me:** the cheapest config that holds ≥ 98% field-level exact match at
acceptable latency. That's exactly the proof-page claim, so it's a fair test of whether the number is
trustworthy enough to put in front of *my* client.

**Where I'll be watching for it to fall short:** whether "quality" scoring handles structured/JSON ground
truth as strictly as it handles free-text, and whether the cost figure includes retries on schema failures
— because a cheaper model that retries twice isn't actually cheaper.

---

**Screening answers**

*What LLM feature have you shipped for a paying client?* A citation-grounded RAG system over an internal
document corpus: retrieval with a score floor, every answer tied to a doc+page, and a gold-set eval that
gates ingestion so accuracy can't silently drop when new docs land.

*Which model do you default to today, and why?* A frontier model at temp 0 for extraction and reasoning
where a wrong field is expensive, and a small fast model for classification/routing where errors are cheap
and recoverable. Default is chosen per task by cost-per-correct-answer, not one model for everything — which
is exactly the decision your tool is trying to make measurable.
