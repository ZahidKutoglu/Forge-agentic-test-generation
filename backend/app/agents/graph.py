"""LangGraph orchestration for the three-agent pipeline."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.architect import architect_node
from app.agents.engineer import engineer_node
from app.agents.executor import executor_node
from app.agents.healer import healer_node, route_after_executor
from app.agents.state import PipelineState, initial_state
from app.core.config import get_settings
from app.models.schemas import GenerateResponse
from app.services.report_store import coverage_score, store, utcnow
from app.models.schemas import ReportSummary

try:
    from langgraph.graph import START
except ImportError:  # pragma: no cover
    START = None


def build_graph():
    builder = StateGraph(PipelineState)
    builder.add_node("architect", architect_node)
    builder.add_node("engineer", engineer_node)
    builder.add_node("executor", executor_node)
    builder.add_node("healer", healer_node)
    if START is not None:
        builder.add_edge(START, "architect")
    else:
        builder.set_entry_point("architect")
    builder.add_edge("architect", "engineer")
    builder.add_edge("engineer", "executor")
    builder.add_conditional_edges(
        "executor",
        route_after_executor,
        {"repair": "healer", "done": END},
    )
    builder.add_edge("healer", "engineer")
    return builder.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run_pipeline(spec: str, max_repairs: int | None = None, execute: bool = True, title: str | None = None) -> GenerateResponse:
    settings = get_settings()
    repairs = settings.max_repair_loops if max_repairs is None else max_repairs
    state = get_graph().invoke(initial_state(spec, repairs, execute, title))
    return persist_state(state)


def stream_pipeline(
    spec: str,
    max_repairs: int | None = None,
    execute: bool = True,
    title: str | None = None,
) -> Iterator[dict[str, Any]]:
    settings = get_settings()
    repairs = settings.max_repair_loops if max_repairs is None else max_repairs
    seed = initial_state(spec, repairs, execute, title)
    yield {
        "type": "agent",
        "agent": "system",
        "status": "running",
        "message": "Pipeline started.",
    }
    final: PipelineState = dict(seed)
    for update in get_graph().stream(seed, stream_mode="updates"):
        for node, payload in update.items():
            if not isinstance(payload, dict):
                continue
            final.update(payload)
            message = ""
            events = payload.get("events") or []
            if events:
                message = getattr(events[-1], "message", "") or ""
            yield {
                "type": "agent",
                "agent": node,
                "status": payload.get("status") or "running",
                "message": message,
                "detail": {
                    "domain": final.get("domain"),
                    "test_cases": len(final.get("test_cases") or []),
                    "heal_iterations": final.get("repair_count") or 0,
                },
            }
            if payload.get("pytest_code"):
                yield {
                    "type": "code",
                    "sut_filename": final.get("sut_filename"),
                    "test_filename": final.get("test_filename"),
                    "sut_code": final.get("sut_code"),
                    "pytest_code": final.get("pytest_code"),
                }
            for line in payload.get("logs") or []:
                if str(line).startswith("[pytest]"):
                    yield {"type": "log", "line": str(line)[9:].lstrip()}
            execution = payload.get("execution")
            if execution is not None:
                yield {
                    "type": "execution",
                    "execution": execution.model_dump(),
                    "heal_iterations": final.get("repair_count") or 0,
                }
    response = persist_state(final)
    yield {"type": "complete", "result": response.model_dump(mode="json")}


def persist_state(state: PipelineState) -> GenerateResponse:
    import uuid

    execution = state.get("execution")
    if execution is None:
        from app.models.schemas import ExecutionSummary

        execution = ExecutionSummary(passed=False)
    run_id = uuid.uuid4().hex[:12]
    created = utcnow()
    duration_ms = max(0.0, (created.timestamp() - float(state.get("started_at") or created.timestamp())) * 1000)
    cases = state.get("test_cases") or []
    score = coverage_score(len(cases), execution)
    response = GenerateResponse(
        run_id=run_id,
        title=state.get("title") or "Generated suite",
        domain=state.get("domain") or "generic",
        status=state.get("status") or "complete",
        provider=state.get("provider") or get_settings().resolved_provider,
        test_cases=cases,
        sut_filename=state.get("sut_filename") or "sut.py",
        test_filename=state.get("test_filename") or "test_generated.py",
        sut_code=state.get("sut_code") or "",
        pytest_code=state.get("pytest_code") or "",
        execution=execution,
        heal_iterations=int(state.get("repair_count") or 0),
        coverage_score=score,
        logs=list(state.get("logs") or []),
        events=list(state.get("events") or []),
        duration_ms=round(duration_ms, 2),
        created_at=created,
    )
    store.save(
        ReportSummary(
            id=run_id,
            created_at=created,
            title=response.title,
            domain=response.domain,
            status=response.status,
            total=execution.total,
            passed=execution.passed_count,
            failed=execution.failed_count,
            skipped=execution.skipped_count,
            duration_ms=execution.duration_ms,
            heal_iterations=response.heal_iterations,
            coverage_score=score,
            junit_xml=execution.junit_xml,
            execution=execution,
            pytest_code=response.pytest_code,
            sut_code=response.sut_code,
            test_filename=response.test_filename,
            sut_filename=response.sut_filename,
            provider=response.provider,
            logs=response.logs,
        )
    )
    return response
