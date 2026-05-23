"""Input/output guardrails applied around agent LLM calls.

Currently supports PII redaction (email, phone, credit card, IPv4).
Extend by adding new mode handlers to ``apply_input_guardrails``.
"""

import re
from dataclasses import dataclass

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{7,}\d)(?!\d)")
_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


@dataclass
class GuardrailOutcome:
    text: str
    triggered: list[str]
    counts: dict[str, int]


def _redact(text: str, pattern: re.Pattern, label: str, counts: dict[str, int]) -> str:
    def _sub(match: re.Match) -> str:
        counts[label] = counts.get(label, 0) + 1
        return f"[REDACTED_{label}]"

    return pattern.sub(_sub, text)


def redact_pii(text: str) -> GuardrailOutcome:
    counts: dict[str, int] = {}
    redacted = text
    redacted = _redact(redacted, _CC_RE, "CC", counts)
    redacted = _redact(redacted, _EMAIL_RE, "EMAIL", counts)
    redacted = _redact(redacted, _PHONE_RE, "PHONE", counts)
    redacted = _redact(redacted, _IPV4_RE, "IP", counts)
    triggered = [label for label, n in counts.items() if n > 0]
    return GuardrailOutcome(text=redacted, triggered=triggered, counts=counts)


def apply_input_guardrails(text: str, guardrails: dict | None) -> GuardrailOutcome:
    """Return possibly-redacted text plus a list of triggered guard labels."""
    if not guardrails:
        return GuardrailOutcome(text=text, triggered=[], counts={})
    pii_mode = guardrails.get("pii")
    if pii_mode == "redact":
        return redact_pii(text)
    return GuardrailOutcome(text=text, triggered=[], counts={})
