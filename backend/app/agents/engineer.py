"""Agent 2 — Test Engineer."""

from __future__ import annotations

import time

from app.agents.llm import complete_json
from app.agents.prompts import ENGINEER_SYSTEM, HEALER_SYSTEM
from app.agents.state import PipelineState
from app.core.config import get_settings
from app.models.schemas import AgentEvent, TestCase
from app.services.repair import repair_python, validate_python
from app.services.spec_parser import parse_spec
from app.services.synthesizer import synthesize_suite


def engineer_node(state: PipelineState) -> dict:
    repairing = bool(state.get("repair_context"))
    logs = list(state.get("logs") or [])
    events = list(state.get("events") or [])
    events.append(
        AgentEvent(
            ts=time.time(),
            agent="engineer",
            status="running",
            message="Repairing PyTest suite." if repairing else "Translating cases into executable PyTest.",
        )
    )

    parsed = parse_spec(state["spec"])
    sut_filename, sut_code, test_filename, pytest_code = synthesize_suite(parsed)
    provider = "local"

    if repairing:
        sut_code, pytest_code, provider = _repair(state, sut_code, pytest_code)
        logs.append(f"[engineer] self-heal pass {state.get('repair_count', 0)} via {provider}")
    else:
        llm_code = _llm_generate(state)
        if llm_code:
            sut_filename = llm_code.get("sut_filename") or sut_filename
            test_filename = llm_code.get("test_filename") or test_filename
            sut_code = llm_code.get("sut_code") or sut_code
            pytest_code = llm_code.get("pytest_code") or pytest_code
            provider = get_settings().resolved_provider
            logs.append(f"[engineer] llm authored {test_filename} via {provider}")
        else:
            logs.append(f"[engineer] deterministic synthesizer authored {test_filename}")

    sut_code = _ensure_valid(sut_code)
    pytest_code = _ensure_valid(pytest_code)

    events.append(
        AgentEvent(
            ts=time.time(),
            agent="engineer",
            status="complete",
            message=f"Wrote {test_filename} ({len(pytest_code.splitlines())} lines).",
            detail={
                "sut_filename": sut_filename,
                "test_filename": test_filename,
                "provider": provider,
                "repairing": repairing,
            },
        )
    )
    return {
        "sut_filename": sut_filename,
        "test_filename": test_filename,
        "sut_code": sut_code,
        "pytest_code": pytest_code,
        "provider": provider if not repairing else state.get("provider", provider),
        "logs": logs,
        "events": events,
        "status": "coded",
        "repair_context": "",
    }


def _llm_generate(state: PipelineState) -> dict | None:
    if get_settings().resolved_provider == "local":
        return None
    cases = [case.model_dump() if isinstance(case, TestCase) else case for case in state.get("test_cases") or []]
    payload = complete_json(
        ENGINEER_SYSTEM,
        "SPECIFICATION:\n"
        f"{state['spec']}\n\nTEST CASES JSON:\n{cases}",
    )
    if not payload:
        return None
    if not payload.get("sut_code") or not payload.get("pytest_code"):
        return None
    return payload


def _repair(state: PipelineState, sut_code: str, pytest_code: str) -> tuple[str, str, str]:
    current_sut = state.get("sut_code") or sut_code
    current_tests = state.get("pytest_code") or pytest_code
    traceback = state.get("repair_context") or ""
    provider = "local"
    if get_settings().resolved_provider != "local":
        payload = complete_json(
            HEALER_SYSTEM,
            "TRACEBACK:\n"
            f"{traceback}\n\nSUT:\n{current_sut}\n\nPYTEST:\n{current_tests}\n\nSPEC:\n{state['spec']}",
        )
        if payload and payload.get("sut_code") and payload.get("pytest_code"):
            return str(payload["sut_code"]), str(payload["pytest_code"]), get_settings().resolved_provider

    repaired_sut = repair_python(current_sut, traceback)
    repaired_tests = repair_python(current_tests, traceback)
    if repaired_sut == current_sut and repaired_tests == current_tests:
        return sut_code, pytest_code, provider
    return repaired_sut, repaired_tests, provider


def _ensure_valid(source: str) -> str:
    if validate_python(source) is None:
        return source
    repaired = repair_python(source)
    if validate_python(repaired) is None:
        return repaired
    return source
