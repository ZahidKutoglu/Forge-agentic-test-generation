"""Agent 1 — Test Architect."""

from __future__ import annotations

import time

from app.agents.llm import complete_json
from app.agents.prompts import ARCHITECT_SYSTEM
from app.agents.state import PipelineState, append_event, append_log
from app.core.config import get_settings
from app.models.schemas import AgentEvent, TestCase
from app.services.spec_parser import parse_spec
from app.services.synthesizer import architect_cases


def architect_node(state: PipelineState) -> dict:
    spec = state["spec"]
    parsed = parse_spec(spec)
    provider = get_settings().resolved_provider
    logs = append_log(state, f"[architect] parsed domain={parsed.domain} title={parsed.title!r}")
    events = append_event(state, "architect", "running", "Ingesting specification and drafting test cases.")

    cases = architect_cases(parsed)
    used_provider = "local"
    llm_payload = None
    if provider != "local":
        llm_payload = complete_json(
            ARCHITECT_SYSTEM,
            f"TITLE HINT: {state.get('title') or parsed.title}\n\nSPECIFICATION:\n{spec}",
        )
        llm_cases = _cases_from_llm(llm_payload)
        if llm_cases:
            cases = llm_cases
            used_provider = provider
            logs.append(f"[architect] llm returned {len(cases)} cases via {provider}")
        else:
            logs.append("[architect] llm unavailable or invalid JSON; using deterministic architect")

    title = parsed.title
    if llm_payload and isinstance(llm_payload.get("title"), str) and llm_payload["title"].strip():
        title = llm_payload["title"].strip()

    events.append(
        AgentEvent(
            ts=time.time(),
            agent="architect",
            status="complete",
            message=f"Drafted {len(cases)} test cases for {parsed.domain}.",
            detail={"count": len(cases), "domain": parsed.domain, "provider": used_provider},
        )
    )
    logs.append(f"[architect] {len(cases)} structured cases ready")

    return {
        "title": title,
        "domain": parsed.domain,
        "provider": used_provider,
        "parsed": {
            "title": parsed.title,
            "domain": parsed.domain,
            "numbers": parsed.numbers,
            "requirements": parsed.requirements,
            "failure_modes": parsed.failure_modes,
            "admin_keys": parsed.admin_keys,
        },
        "test_cases": cases,
        "logs": logs,
        "events": events,
        "status": "architected",
    }


def _cases_from_llm(payload: dict | None) -> list[TestCase]:
    if not payload:
        return []
    raw = payload.get("test_cases")
    if not isinstance(raw, list):
        return []
    cases: list[TestCase] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            cases.append(TestCase.model_validate(item))
        except Exception:
            continue
    return cases
