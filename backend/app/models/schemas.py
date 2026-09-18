from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AgentName = Literal["architect", "engineer", "executor", "healer"]
AgentStatus = Literal["idle", "running", "complete", "error", "skipped"]
TestCategory = Literal["happy_path", "edge_case", "failure_mode", "security", "concurrency", "non_functional"]


class GenerateRequest(BaseModel):
    spec: str = Field(..., min_length=20, max_length=80_000)
    max_repairs: int = Field(default=3, ge=0, le=8)
    execute: bool = True
    title: str | None = None


class RunTestsRequest(BaseModel):
    run_id: str | None = None
    pytest_code: str | None = None
    sut_code: str | None = None
    test_filename: str | None = None
    sut_filename: str | None = None


class TestCase(BaseModel):
    id: str
    title: str
    category: TestCategory
    priority: Literal["critical", "high", "medium", "low"] = "high"
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    assertions: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class AgentEvent(BaseModel):
    ts: float
    agent: AgentName | Literal["system"]
    status: AgentStatus | Literal["log"]
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class TestResult(BaseModel):
    nodeid: str
    outcome: Literal["passed", "failed", "skipped", "error"]
    duration_ms: float = 0
    message: str = ""


class ExecutionSummary(BaseModel):
    passed: bool
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    duration_ms: float = 0
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    traceback: str = ""
    results: list[TestResult] = Field(default_factory=list)
    junit_xml: str = ""


class GenerateResponse(BaseModel):
    run_id: str
    title: str
    domain: str
    status: str
    provider: str
    test_cases: list[TestCase]
    sut_filename: str
    test_filename: str
    sut_code: str
    pytest_code: str
    execution: ExecutionSummary
    heal_iterations: int
    coverage_score: float
    logs: list[str]
    events: list[AgentEvent]
    duration_ms: float
    created_at: datetime


class ReportSummary(BaseModel):
    id: str
    created_at: datetime
    title: str
    domain: str
    status: str
    total: int
    passed: int
    failed: int
    skipped: int
    duration_ms: float
    heal_iterations: int
    coverage_score: float
    junit_xml: str
    execution: ExecutionSummary
    pytest_code: str
    sut_code: str
    test_filename: str
    sut_filename: str
    provider: str
    logs: list[str]


class ReportListResponse(BaseModel):
    reports: list[ReportSummary]
    count: int
