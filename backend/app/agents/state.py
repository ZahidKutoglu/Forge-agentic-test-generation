"""LangGraph pipeline state."""

from __future__ import annotations

import time
from typing import Any, TypedDict

from app.models.schemas import AgentEvent, ExecutionSummary, TestCase


class PipelineState(TypedDict, total=False):
    spec: str
    title: str
    domain: str
    provider: str
    parsed: dict[str, Any]
    test_cases: list[TestCase]
    sut_filename: str
    test_filename: str
    sut_code: str
    pytest_code: str
    execution: ExecutionSummary
    repair_count: int
    max_repairs: int
    repair_context: str
    logs: list[str]
    events: list[AgentEvent]
    status: str
    error: str
    started_at: float
    execute: bool


def initial_state(spec: str, max_repairs: int, execute: bool, title: str | None = None) -> PipelineState:
    return PipelineState(
        spec=spec,
        title=title or "",
        domain="generic",
        provider="local",
        parsed={},
        test_cases=[],
        sut_filename="sut.py",
        test_filename="test_generated.py",
        sut_code="",
        pytest_code="",
        execution=ExecutionSummary(passed=False),
        repair_count=0,
        max_repairs=max_repairs,
        repair_context="",
        logs=[],
        events=[],
        status="queued",
        error="",
        started_at=time.time(),
        execute=execute,
    )


def append_event(
    state: PipelineState,
    agent: str,
    status: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> list[AgentEvent]:
    event = AgentEvent(
        ts=time.time(),
        agent=agent,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        message=message,
        detail=detail or {},
    )
    return list(state.get("events") or []) + [event]


def append_log(state: PipelineState, line: str) -> list[str]:
    return list(state.get("logs") or []) + [line]
