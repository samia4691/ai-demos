"""
The orchestrator. Every message runs the same safe pipeline:

  1. Guardrail: scan the incoming message for prompt injection. If found -> escalate, do nothing.
  2. Route by intent (rule-based here; an LLM classifier in production).
  3. Policy question -> grounded RAG answer, or an honest refusal if the KB doesn't cover it.
  4. Read tool (order status) -> runs within scope; its output is re-scanned for injection.
  5. Write tool (refund) -> NEVER auto-executed. Returns a pending action for a human to approve.
  6. Redact PII/secrets from whatever goes back to the customer.

The safety properties are enforced in code, not left to a prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import guardrails as g
from .retrieval import KBRetriever
from .tools import REGISTRY


@dataclass
class Result:
    type: str                     # answer | action_pending | refusal | escalation
    text: str
    citations: list[str] = field(default_factory=list)
    action: dict | None = None    # for action_pending: the tool call awaiting approval

    def render(self) -> str:
        out = [f"[{self.type}] {self.text}"]
        if self.citations:
            out.append("Sources: " + ", ".join(self.citations))
        if self.action:
            out.append(f"Pending approval: {self.action}")
        return "\n".join(out)


_ORDER_RE = re.compile(r"\b([A-Z]\d{4})\b")


class SupportAgent:
    def __init__(self, granted_scopes: set[str] | None = None, retriever: KBRetriever | None = None):
        # By default the agent can read orders but NOT issue refunds. Grant write:refunds only
        # to an agent instance that is wired to a human-approval queue.
        self.scopes = granted_scopes if granted_scopes is not None else {"read:orders"}
        self.kb = retriever or KBRetriever()

    def handle(self, message: str, *, approval_token: str | None = None) -> Result:
        # 1. Injection guardrail on untrusted user input
        hit = g.detect_injection(message)
        if hit:
            return Result("escalation",
                          f"This message was flagged for a possible prompt-injection attempt "
                          f"(\"{hit}\") and was routed to a human. No tools were run.")

        low = message.lower()

        # 2/5. Refund intent -> human-approval gate (money moves)
        if "refund" in low:
            return self._refund(message, approval_token)

        # 2/4. Order-status intent -> read tool
        if "order" in low or "status" in low or _ORDER_RE.search(message):
            return self._order_status(message)

        # 2/3. Everything else -> grounded policy answer or refuse
        return self._policy_answer(message)

    # --- read tool -----------------------------------------------------------
    def _order_status(self, message: str) -> Result:
        m = _ORDER_RE.search(message)
        if not m:
            return Result("answer", "Sure — what's your order number? It looks like A followed by four digits.")
        tool = REGISTRY["get_order_status"]
        try:
            g.require_scope(tool.scope, self.scopes)
        except g.ScopeError as e:
            return Result("escalation", f"I can't look that up ({e}). Escalating to a human.")
        out = tool.fn(m.group(1))
        # Tool output is untrusted too — re-scan before using it.
        if g.detect_injection(str(out)):
            return Result("escalation", "The record contained suspicious content; routed to a human.")
        if not out["found"]:
            return Result("answer", g.redact(f"I couldn't find order {m.group(1)}. Can you double-check the number?"))
        return Result("answer", g.redact(
            f"Order {out['order_id']} is {out['status']}, estimated to arrive {out['eta']}."))

    # --- write tool (guarded) ------------------------------------------------
    def _refund(self, message: str, approval_token: str | None) -> Result:
        tool = REGISTRY["issue_refund"]
        m = _ORDER_RE.search(message)
        order_id = m.group(1) if m else None
        # A refund never runs on the agent's decision alone.
        if tool.requires_approval and not approval_token:
            return Result(
                "action_pending",
                "A refund needs a teammate to approve it. I've prepared the request and put it "
                "in the approval queue.",
                action={"tool": "issue_refund", "order_id": order_id, "status": "awaiting_human_approval"})
        # With an approval token, the agent still must hold the write scope.
        try:
            g.require_scope(tool.scope, self.scopes)
        except g.ScopeError as e:
            return Result("escalation", f"Refund not executed ({e}).")
        out = tool.fn(order_id, 0.0)  # amount filled from the approved request in production
        return Result("answer", f"Refund processed for {order_id}." if out["ok"]
                      else f"Refund could not be processed: {out['reason']}.")

    # --- grounded answer -----------------------------------------------------
    def _policy_answer(self, message: str) -> Result:
        hit = self.kb.top(message)
        if not hit:
            return Result("refusal",
                          "I don't have that in our help docs, so I don't want to guess. "
                          "I'll pass you to a teammate who can confirm.")
        doc, _score = hit
        return Result("answer", g.redact(doc.text), citations=[doc.doc_id])
