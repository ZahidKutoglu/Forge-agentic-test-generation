"""Select a domain synthesizer and emit SUT + PyTest sources."""

from __future__ import annotations

from app.models.schemas import TestCase
from app.services.domains.generic import architect_generic, synthesize_generic
from app.services.domains.handover import architect_handover, synthesize_handover
from app.services.domains.rate_limiter import architect_rate_limiter, synthesize_rate_limiter
from app.services.spec_parser import ParsedSpec


def architect_cases(parsed: ParsedSpec) -> list[TestCase]:
    if parsed.domain == "rate_limiter":
        return architect_rate_limiter(parsed)
    if parsed.domain == "handover":
        return architect_handover(parsed)
    return architect_generic(parsed)


def synthesize_suite(parsed: ParsedSpec) -> tuple[str, str, str, str]:
    if parsed.domain == "rate_limiter":
        return synthesize_rate_limiter(parsed)
    if parsed.domain == "handover":
        return synthesize_handover(parsed)
    return synthesize_generic(parsed)
