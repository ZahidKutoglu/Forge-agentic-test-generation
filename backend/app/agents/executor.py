"""Agent 3 — Execution."""

from __future__ import annotations

import time

from app.agents.state import PipelineState
from app.models.schemas import AgentEvent, ExecutionSummary
from app.services.pytest_runner import run_pytest_suite


def executor_node(state: PipelineState) -> dict:
    logs = list(state.get("logs") or [])
    events = list(state.get("events") or [])
    if not state.get("execute", True):
        events.append(
            AgentEvent(
                ts=time.time(),
                agent="executor",
                status="skipped",
                message="Execution skipped by request.",
            )
        )
        return {
            "execution": ExecutionSummary(passed=True),
            "logs": logs + ["[executor] skipped"],
            "events": events,
            "status": "generated",
        }

    events.append(
        AgentEvent(
            ts=time.time(),
            agent="executor",
            status="running",
            message="Launching isolated PyTest subprocess.",
        )
    )
    logs.append("[executor] pytest -v --tb=short --junitxml=junit.xml")

    captured: list[str] = []

    def on_line(line: str) -> None:
        captured.append(line)

    execution = run_pytest_suite(
        sut_code=state.get("sut_code") or "",
        pytest_code=state.get("pytest_code") or "",
        sut_filename=state.get("sut_filename") or "sut.py",
        test_filename=state.get("test_filename") or "test_generated.py",
        on_line=on_line,
    )
    logs.extend(f"[pytest] {line}" for line in captured)
    summary = (
        f"{execution.passed_count} passed, {execution.failed_count} failed, "
        f"{execution.error_count} errors in {execution.duration_ms:.0f} ms"
    )
    events.append(
        AgentEvent(
            ts=time.time(),
            agent="executor",
            status="complete" if execution.passed else "error",
            message=summary,
            detail={
                "passed": execution.passed,
                "total": execution.total,
                "exit_code": execution.exit_code,
            },
        )
    )
    logs.append(f"[executor] {summary}")
    return {
        "execution": execution,
        "logs": logs,
        "events": events,
        "status": "passed" if execution.passed else "failed",
    }
