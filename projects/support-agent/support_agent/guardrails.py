"""
Guardrails: the parts that make an autonomous support agent safe to point at real customers.

Three independent controls, each enforced in code:

  1. Prompt-injection detection on BOTH user text and tool-returned text. Untrusted content that
     tries to override instructions ("ignore previous instructions", "you are now...") is caught
     before it can steer a tool call. Tool output is treated as untrusted too — a poisoned CRM
     note is a real attack vector.
  2. Scope enforcement. Every tool declares a required scope; a caller only holds the scopes it
     was granted. No scope, no call.
  3. PII / secret redaction on the way out, so the agent never echoes a card number or email
     into a transcript or a log.
"""
from __future__ import annotations

import re

# --- 1. Injection detection -------------------------------------------------
_INJECTION_PATTERNS = [
    r"ignore (all|any|the)? ?(previous|prior|above) (instructions|prompts?)",
    r"disregard (the|all|any)? ?(previous|above|system)",
    r"you are now\b",
    r"forget (everything|all|your) (instructions|rules)",
    r"reveal (your|the) (system prompt|instructions|rules)",
    r"(print|show|repeat) (your|the) (system prompt|instructions)",
    r"act as (an?|the) .* (with no|without) (restrictions|filter|rules)",
    r"developer mode",
    r"</?system>",
]
_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def detect_injection(text: str) -> str | None:
    """Return the matched phrase if the text looks like a prompt-injection attempt, else None."""
    for rx in _INJECTION_RE:
        m = rx.search(text or "")
        if m:
            return m.group(0)
    return None


# --- 2. Scope enforcement ---------------------------------------------------
class ScopeError(PermissionError):
    pass


def require_scope(needed: str, granted: set[str]) -> None:
    if needed not in granted:
        raise ScopeError(f"missing scope '{needed}' (granted: {sorted(granted) or 'none'})")


# --- 3. PII / secret redaction ---------------------------------------------
_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE = re.compile(r"\b(?:\+?\d{1,2}[ -]?)?(?:\(?\d{3}\)?[ -]?)\d{3}[ -]?\d{4}\b")


def redact(text: str) -> str:
    text = _EMAIL.sub("[email redacted]", text or "")
    text = _SSN.sub("[ssn redacted]", text)
    text = _CARD.sub("[card redacted]", text)
    text = _PHONE.sub("[phone redacted]", text)
    return text
