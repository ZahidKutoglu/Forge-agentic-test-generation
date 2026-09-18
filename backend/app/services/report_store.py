"""Persisted execution reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import Lock

from app.core.config import get_settings
from app.models.schemas import ExecutionSummary, ReportListResponse, ReportSummary


class ReportStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[str, ReportSummary] = {}
        self._load()

    def _load(self) -> None:
        settings = get_settings()
        for path in sorted(settings.data_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                report = ReportSummary.model_validate(payload)
                self._items[report.id] = report
            except (OSError, ValueError):
                continue

    def save(self, report: ReportSummary) -> ReportSummary:
        with self._lock:
            self._items[report.id] = report
            path = get_settings().data_dir / f"{report.id}.json"
            path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            xml_path = get_settings().data_dir / f"{report.id}.xml"
            if report.junit_xml:
                xml_path.write_text(report.junit_xml, encoding="utf-8")
            return report

    def get(self, report_id: str) -> ReportSummary | None:
        with self._lock:
            return self._items.get(report_id)

    def list(self) -> ReportListResponse:
        with self._lock:
            reports = sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)
            return ReportListResponse(reports=reports, count=len(reports))


def coverage_score(cases_count: int, execution: ExecutionSummary) -> float:
    if execution.total <= 0:
        return 0.0
    pass_rate = execution.passed_count / max(execution.total, 1)
    density = min(1.0, execution.total / max(cases_count, 8))
    penalty = 0.08 * execution.error_count
    score = 100.0 * (0.75 * pass_rate + 0.25 * density) - penalty
    return round(max(0.0, min(100.0, score)), 1)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


store = ReportStore()
