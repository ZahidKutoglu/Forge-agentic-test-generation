"""Self-healing router."""

from __future__ import annotations

import time

from app.agents.state import PipelineState
from app.models.schemas import AgentEvent
from app.services.repair import needs_repair


def healer_node(state: PipelineState) -> dict:
    execution = state.get("execution")
    traceback = ""
    if execution is not None:
        traceback = execution.traceback or execution.stdout or ""
    iteration = int(state.get("repair_count") or 0) + 1
    events = list(state.get("events") or [])
    logs = list(state.get("logs") or [])
    events.append(
        AgentEvent(
            ts=time.time(),
            agent="healer",
            status="running",
            message=f"Capturing traceback and opening repair loop {iteration}/3.",
            detail={"iteration": iteration},
        )
    )
    logs.append(f"[healer] routing failure back to engineer (iteration {iteration})")
    events.append(
        AgentEvent(
            ts=time.time(),
            agent="healer",
            status="complete",
            message="Repair context attached.",
            detail={"iteration": iteration},
        )
    )
    return {
        "repair_count": iteration,
        "repair_context": traceback[-8000:],
        "logs": logs,
        "events": events,
        "status": "healing",
    }


def route_after_executor(state: PipelineState) -> str:
    if not state.get("execute", True):
        return "done"
    execution = state.get("execution")
    if execution is None or execution.passed:
        return "done"
    repair_count = int(state.get("repair_count") or 0)
    max_repairs = int(state.get("max_repairs") or 3)
    if repair_count >= max_repairs:
        return "done"
    traceback = (execution.traceback or execution.stdout or "") if execution else ""
    if needs_repair(traceback, state.get("pytest_code") or "", state.get("sut_code") or ""):
        return "repair"
    return "done"
