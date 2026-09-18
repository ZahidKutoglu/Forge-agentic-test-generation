"""Isolated PyTest execution."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import ExecutionSummary, TestResult

LineCallback = Callable[[str], None]


def run_pytest_suite(
    *,
    sut_code: str,
    pytest_code: str,
    sut_filename: str = "sut.py",
    test_filename: str = "test_generated.py",
    timeout: int | None = None,
    on_line: LineCallback | None = None,
) -> ExecutionSummary:
    settings = get_settings()
    timeout_s = timeout or settings.pytest_timeout_seconds
    started = time.monotonic()

    with tempfile.TemporaryDirectory(prefix="forge-pytest-") as raw_dir:
        workdir = Path(raw_dir)
        (workdir / sut_filename).write_text(sut_code, encoding="utf-8")
        (workdir / test_filename).write_text(pytest_code, encoding="utf-8")
        junit_path = workdir / "junit.xml"
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(workdir)
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

        command = [
            sys.executable,
            "-m",
            "pytest",
            test_filename,
            "-v",
            "--tb=short",
            "--color=no",
            "-p",
            "no:cacheprovider",
            f"--junitxml={junit_path.name}",
        ]
        process = subprocess.Popen(
            command,
            cwd=workdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        chunks: list[str] = []
        timed_out = False
        try:
            assert process.stdout is not None
            while True:
                if time.monotonic() - started > timeout_s:
                    timed_out = True
                    process.kill()
                    break
                line = process.stdout.readline()
                if line == "" and process.poll() is not None:
                    break
                if line:
                    chunks.append(line)
                    if on_line:
                        on_line(line.rstrip("\n"))
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()

        stdout = "".join(chunks)
        if timed_out:
            stdout += "\nERROR: pytest killed after timeout\n"
            if on_line:
                on_line("ERROR: pytest killed after timeout")

        junit_xml = junit_path.read_text(encoding="utf-8") if junit_path.exists() else ""
        results, counts = _parse_junit(junit_xml)
        if not results:
            results, counts = _parse_pytest_output(stdout)

        duration_ms = (time.monotonic() - started) * 1000
        traceback = _extract_traceback(stdout)
        exit_code = process.returncode if process.returncode is not None else 1
        if timed_out:
            exit_code = 124

        passed = exit_code == 0 and counts["failed"] == 0 and counts["error"] == 0
        return ExecutionSummary(
            passed=passed,
            total=counts["total"] or len(results),
            passed_count=counts["passed"],
            failed_count=counts["failed"],
            skipped_count=counts["skipped"],
            error_count=counts["error"],
            duration_ms=round(duration_ms, 2),
            exit_code=exit_code,
            stdout=stdout[-20_000:],
            stderr="",
            traceback=traceback[-12_000:],
            results=results,
            junit_xml=junit_xml[-50_000:],
        )


def _parse_junit(xml_text: str) -> tuple[list[TestResult], dict[str, int]]:
    counts = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "error": 0}
    results: list[TestResult] = []
    if not xml_text.strip():
        return results, counts
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return results, counts

    suites = root.findall(".//testsuite")
    if root.tag == "testsuite":
        suites = [root]
    for suite in suites:
        for case in suite.findall("testcase"):
            classname = case.get("classname") or ""
            name = case.get("name") or "unnamed"
            nodeid = f"{classname}::{name}" if classname else name
            duration_ms = float(case.get("time") or 0) * 1000
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            if failure is not None:
                outcome = "failed"
                message = (failure.get("message") or "") + "\n" + (failure.text or "")
            elif error is not None:
                outcome = "error"
                message = (error.get("message") or "") + "\n" + (error.text or "")
            elif skipped is not None:
                outcome = "skipped"
                message = skipped.get("message") or ""
            else:
                outcome = "passed"
                message = ""
            counts[outcome if outcome != "error" else "error"] += 1
            counts["total"] += 1
            results.append(
                TestResult(
                    nodeid=nodeid,
                    outcome=outcome,  # type: ignore[arg-type]
                    duration_ms=round(duration_ms, 3),
                    message=message.strip()[:4000],
                )
            )
    return results, counts


def _parse_pytest_output(stdout: str) -> tuple[list[TestResult], dict[str, int]]:
    results: list[TestResult] = []
    counts = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "error": 0}
    for line in stdout.splitlines():
        outcome = None
        if " PASSED" in line:
            outcome = "passed"
        elif " FAILED" in line:
            outcome = "failed"
        elif " SKIPPED" in line:
            outcome = "skipped"
        elif " ERROR" in line:
            outcome = "error"
        if not outcome:
            continue
        nodeid = line.split()[0]
        counts[outcome] += 1
        counts["total"] += 1
        results.append(TestResult(nodeid=nodeid, outcome=outcome))  # type: ignore[arg-type]
    return results, counts


def _extract_traceback(stdout: str) -> str:
    markers = ("E   ", "Traceback (most recent call last)", "======= FAILURES", "======= ERRORS")
    if not any(marker in stdout for marker in markers):
        return ""
    lines = stdout.splitlines()
    start = 0
    for index, line in enumerate(lines):
        if "FAILURES" in line or "ERRORS" in line or line.startswith("Traceback"):
            start = index
            break
    return "\n".join(lines[start:])
