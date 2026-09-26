# Lead Capture → Qualify → CRM — a reliable n8n workflow

An importable n8n workflow that takes an inbound lead, **de-duplicates it, qualifies it with an
AI step, writes it to a CRM, and alerts sales** — built the way it has to be to survive
production, not a demo that breaks next week.

The point of this reference is not "n8n can call an LLM." Everyone can wire that. The point is
the stuff around it that stops leads from silently disappearing:

- **De-duplication before anything else.** Incoming leads are normalized (lower-cased email,
  digits-only phone) into a stable `dedupe_key`. A lead with neither email nor phone is rejected
  early instead of flowing downstream as junk. A Redis `seen:` check with a 30-day TTL means the
  same person filling the form twice never triggers double outreach.
- **The AI step is schema-checked, not trusted.** The model runs at temperature 0 with JSON
  output and is asked for `{tier, intent, reason}`. A dedicated **Validate AI Output** node then
  checks the tier against an allow-list. If the model returns anything unexpected, the lead is
  downgraded to `warm` and flagged `needs_review` — it is never dropped and never written as
  garbage.
- **Every external call retries.** The AI node and the CRM write both retry up to 3× with
  backoff, so a transient API hiccup doesn't lose a real lead.
- **The CRM write is idempotent.** It sends an `Idempotency-Key` equal to the dedupe key, so even
  if a retry fires after a partial success, you get one contact, not two.
- **Failures degrade, they don't cascade.** The Redis lookup and the Slack alert are
  `continueOnFail` — a Redis blip or a Slack outage can't block a lead that otherwise qualified,
  because the CRM write already succeeded.

## Flow

```
Webhook  ->  Normalize + dedupe key  ->  Seen before? (Redis)  ->  IF new
                                                                     |         \
                                                              (new) yes      (dup) no -> Respond 200
                                                                     v
                                              AI Qualify (temp 0, JSON, retry x3)
                                                                     v
                                              Validate AI output (allow-list, fallback)
                                                                     v
                                              Route by tier (hot / warm / cold)
                                                                     v
                                              Upsert CRM (idempotent, retry x3)
                                                                     v
                                              Mark seen (Redis, 30d TTL)
                                                                     v
                                              Slack alert (continueOnFail) -> Respond 200
```

## Import it

1. n8n → **Workflows → Import from File** → choose `workflow.json`.
2. Set credentials: an **OpenAI** credential for the AI node, a **Redis** credential for the two
   Redis nodes, and a **Slack** credential for the alert. Add `CRM_API_KEY` as an environment
   variable (referenced as `{{$env.CRM_API_KEY}}`), and point the CRM node's URL at your CRM.
3. Runs the same on **n8n Cloud or self-hosted (Docker/VPS)**. If self-hosting without Redis, the
   dedupe check can be swapped for a CRM "find contact" lookup — the surrounding logic is
   unchanged.
4. `POST` a test lead to the webhook path `/lead-intake`:

```json
{ "name": "Dana Lee", "email": "dana@acme.example", "company": "Acme", "message": "Need pricing for 40 seats this quarter", "source": "pricing-page" }
```

## Adapting it

- **Different CRM (HubSpot, GoHighLevel, Pipedrive):** only the *Upsert CRM* node changes; keep
  the idempotency key.
- **More tiers or different routing:** edit the *Route by Tier* switch; the validation allow-list
  lives in one place in *Validate AI Output*.
- **Add outbound follow-up:** hang an email/SMS branch off the `hot` and `warm` outputs.

---
Samia M. — AI Automation & LLM Engineer · reference workflow, adapt to your stack ·
[portfolio](https://samia4691.github.io/)
