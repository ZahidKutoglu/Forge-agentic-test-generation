from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.graph import persist_state, run_pipeline, stream_pipeline
from app.agents.state import initial_state
from app.core.config import get_settings
from app.models.schemas import GenerateRequest, GenerateResponse, ReportListResponse, ReportSummary, RunTestsRequest
from app.services.pytest_runner import run_pytest_suite
from app.services.report_store import store

router = APIRouter(prefix="/api")


@router.get("/samples")
def list_samples() -> dict:
    samples_dir = Path(__file__).resolve().parents[3] / "samples"
    items = []
    if samples_dir.exists():
        for path in sorted(samples_dir.glob("*.md")):
            items.append({"id": path.stem, "title": path.stem.replace("-", " "), "spec": path.read_text(encoding="utf-8")})
    return {"samples": items}


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "ok": True,
        "provider": settings.resolved_provider,
        "model": settings.llm_model,
    }


@router.post("/generate-tests", response_model=GenerateResponse)
def generate_tests(payload: GenerateRequest) -> GenerateResponse:
    return run_pipeline(
        spec=payload.spec,
        max_repairs=payload.max_repairs,
        execute=payload.execute,
        title=payload.title,
    )


@router.post("/generate-tests/stream")
def generate_tests_stream(payload: GenerateRequest) -> StreamingResponse:
    def events():
        for item in stream_pipeline(
            spec=payload.spec,
            max_repairs=payload.max_repairs,
            execute=payload.execute,
            title=payload.title,
        ):
            yield f"data: {json.dumps(item, default=str)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/run-tests", response_model=GenerateResponse)
def run_tests(payload: RunTestsRequest) -> GenerateResponse:
    sut_code = payload.sut_code
    pytest_code = payload.pytest_code
    sut_filename = payload.sut_filename or "sut.py"
    test_filename = payload.test_filename or "test_generated.py"
    title = "Manual re-run"

    if payload.run_id:
        existing = store.get(payload.run_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Unknown run_id")
        sut_code = sut_code if sut_code is not None else existing.sut_code
        pytest_code = pytest_code if pytest_code is not None else existing.pytest_code
        sut_filename = payload.sut_filename or existing.sut_filename
        test_filename = payload.test_filename or existing.test_filename
        title = existing.title

    if not sut_code or not pytest_code:
        raise HTTPException(status_code=400, detail="pytest_code and sut_code are required")

    execution = run_pytest_suite(
        sut_code=sut_code,
        pytest_code=pytest_code,
        sut_filename=sut_filename,
        test_filename=test_filename,
    )
    state = initial_state(spec="manual re-run of generated suite", max_repairs=0, execute=True, title=title)
    state.update(
        {
            "title": title,
            "domain": "replay",
            "provider": "local",
            "sut_code": sut_code,
            "pytest_code": pytest_code,
            "sut_filename": sut_filename,
            "test_filename": test_filename,
            "execution": execution,
            "status": "passed" if execution.passed else "failed",
            "logs": [f"[pytest] {line}" for line in execution.stdout.splitlines()],
            "test_cases": [],
        }
    )
    return persist_state(state)


@router.get("/reports", response_model=ReportListResponse)
def list_reports() -> ReportListResponse:
    return store.list()


@router.get("/reports/{run_id}", response_model=ReportSummary)
def get_report(run_id: str) -> ReportSummary:
    report = store.get(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Unknown report")
    return report
