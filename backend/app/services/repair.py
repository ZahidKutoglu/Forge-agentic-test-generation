"""Deterministic repairs for generated PyTest suites."""

from __future__ import annotations

import ast
import re
import textwrap


def validate_python(source: str) -> str | None:
    try:
        ast.parse(source)
        return None
    except SyntaxError as exc:
        return f"{exc.msg} (line {exc.lineno})"


def repair_python(source: str, traceback: str = "") -> str:
    repaired = source.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    repaired = repaired.replace("\ufeff", "")
    if validate_python(repaired) and repaired[:1].isspace():
        stripped = textwrap.dedent(repaired)
        if validate_python(stripped) is None:
            repaired = stripped
    if repaired.count('"""') % 2 == 1:
        repaired += "\n\"\"\"\n"
    if repaired.count("'''") % 2 == 1:
        repaired += "\n'''\n"

    error = validate_python(repaired)
    if error and "unterminated" in error.lower():
        repaired = repaired + "\n"

    if "ModuleNotFoundError" in traceback or "ImportError" in traceback:
        missing = re.findall(r"No module named '([^']+)'", traceback)
        for name in missing:
            if name in {"sut", "pytest"}:
                continue
            stub = f"\nclass {name.title().replace('_', '')}:\n    pass\n"
            if stub not in repaired:
                repaired += stub

    if "NameError" in traceback:
        names = re.findall(r"NameError: name '([^']+)' is not defined", traceback)
        imports = {
            "pytest": "import pytest",
            "Mock": "from unittest.mock import Mock",
            "threading": "import threading",
            "datetime": "from datetime import datetime, timezone",
        }
        for name in names:
            line = imports.get(name)
            if line and line not in repaired:
                repaired = line + "\n" + repaired

    return repaired


def needs_repair(traceback: str, pytest_code: str, sut_code: str) -> bool:
    if not traceback.strip():
        return False
    if validate_python(pytest_code) or validate_python(sut_code):
        return True
    markers = (
        "SyntaxError",
        "IndentationError",
        "ImportError",
        "ModuleNotFoundError",
        "NameError",
        "AttributeError",
        "FAILED",
        "ERROR",
        "AssertionError",
    )
    return any(marker in traceback for marker in markers)
