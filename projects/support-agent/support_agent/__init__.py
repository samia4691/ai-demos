"""safe-support-agent: a customer-support agent that deflects safely.

Grounded answers (cite or refuse) + guardrails (injection / PII) + scoped tools +
human approval on anything that moves money.

    from support_agent import SupportAgent
"""
from .agent import SupportAgent, Result

__all__ = ["SupportAgent", "Result"]
