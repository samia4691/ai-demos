"""
Scoped tools. Each tool declares the scope it needs and whether it requires human approval.
Read tools run freely (within scope). Write tools that move money never execute on the agent's
say-so — they return a pending action for a human to approve.

The backing data is a stub dict so the project runs offline. Swap the fns for real API calls;
the scope + approval contract is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# Stub datastore
_ORDERS = {
    "A1001": {"status": "shipped", "eta": "2026-09-24", "total": 128.50, "email": "dana@acme.example"},
    "A1002": {"status": "processing", "eta": "2026-09-27", "total": 64.00, "email": "sam@beta.example"},
}


@dataclass
class Tool:
    name: str
    scope: str
    requires_approval: bool
    fn: Callable[..., dict]
    description: str


def _get_order_status(order_id: str) -> dict:
    o = _ORDERS.get(order_id)
    if not o:
        return {"found": False, "order_id": order_id}
    return {"found": True, "order_id": order_id, "status": o["status"], "eta": o["eta"]}


def _issue_refund(order_id: str, amount: float) -> dict:
    o = _ORDERS.get(order_id)
    if not o:
        return {"ok": False, "reason": "order not found"}
    if amount > o["total"]:
        return {"ok": False, "reason": "refund exceeds order total"}
    return {"ok": True, "order_id": order_id, "refunded": amount}


REGISTRY: dict[str, Tool] = {
    "get_order_status": Tool(
        "get_order_status", scope="read:orders", requires_approval=False, fn=_get_order_status,
        description="Look up the status and ETA of an order."),
    "issue_refund": Tool(
        "issue_refund", scope="write:refunds", requires_approval=True, fn=_issue_refund,
        description="Refund money to a customer. Requires human approval."),
}
