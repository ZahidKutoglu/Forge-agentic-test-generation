"""Requirement specification parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "rate_limiter": (
        "rate limit",
        "rate-limit",
        "token-bucket",
        "token bucket",
        "retry-after",
        "burst",
        "rps",
        "quota",
        "429",
        "api key",
    ),
    "handover": (
        "handover",
        "hand-over",
        "a3",
        "rsrp",
        "rsrq",
        "ttt",
        "hysteresis",
        "ping-pong",
        "radio link",
        "neighbor cell",
        "serving cell",
    ),
}


@dataclass
class ParsedSpec:
    title: str
    domain: str
    body: str
    headings: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    numbers: dict[str, float] = field(default_factory=dict)
    admin_keys: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


def parse_spec(text: str) -> ParsedSpec:
    body = text.strip()
    title = _extract_title(body)
    domain = detect_domain(body)
    headings = re.findall(r"(?m)^#{2,3}\s+(.+)$", body)
    requirements = _extract_requirements(body)
    failure_modes = _extract_failure_modes(body)
    numbers = _extract_numbers(body, domain)
    admin_keys = _extract_admin_keys(body)
    actions = _extract_actions(body)
    return ParsedSpec(
        title=title,
        domain=domain,
        body=body,
        headings=headings,
        requirements=requirements,
        failure_modes=failure_modes,
        numbers=numbers,
        admin_keys=admin_keys,
        actions=actions,
    )


def detect_domain(text: str) -> str:
    lowered = text.lower()
    scores: dict[str, int] = {}
    for domain, hints in DOMAIN_HINTS.items():
        scores[domain] = sum(1 for hint in hints if hint in lowered)
    best = max(scores, key=lambda key: scores[key])
    return best if scores[best] >= 2 else "generic"


def _extract_title(text: str) -> str:
    match = re.search(r"(?m)^#\s+(.+)$", text)
    if match:
        return match.group(1).strip()
    first = text.splitlines()[0].strip() if text.splitlines() else "Untitled Specification"
    return first.lstrip("# ").strip() or "Untitled Specification"


def _extract_requirements(text: str) -> list[str]:
    items: list[str] = []
    for match in re.finditer(r"(?m)^\s*(?:\d+[.)]|[-*])\s+(.+)$", text):
        line = match.group(1).strip()
        if len(line) >= 12:
            items.append(re.sub(r"\s+", " ", line))
    for match in re.finditer(r"(?i)((?:shall|must|must not|may not)\b[^.\n]{8,160})", text):
        clause = re.sub(r"\s+", " ", match.group(1).strip())
        if clause not in items:
            items.append(clause)
    return items[:40]


def _extract_failure_modes(text: str) -> list[str]:
    block = re.search(
        r"(?is)(?:failure modes|failure-mode)[^\n]*\n((?:[-*]\s+.+\n?)+)",
        text,
    )
    if not block:
        return []
    return [re.sub(r"\s+", " ", item.strip()) for item in re.findall(r"[-*]\s+(.+)", block.group(1))]


def _extract_admin_keys(text: str) -> list[str]:
    keys = re.findall(r"`([a-z0-9][a-z0-9\-_]{2,32})`", text.lower())
    preferred = [
        key
        for key in keys
        if any(token in key for token in ("ops", "root", "noc", "pager"))
        or (key.startswith("admin") and "bypass" not in key)
    ]
    return list(dict.fromkeys(preferred or ["ops-root", "noc-pager"]))


def _extract_actions(text: str) -> list[str]:
    match = re.search(r"(?is)action[^\n]*\n((?:\s*[-*]\s+`.+`[^\n]*\n?)+)", text)
    if not match:
        return ["stay", "prepare", "execute", "complete", "rollback", "rlf"]
    found = [item.lower() for item in re.findall(r"`([a-z_]+)`", match.group(1))]
    return found or ["stay", "prepare", "execute", "complete", "rollback", "rlf"]


def _extract_numbers(text: str, domain: str) -> dict[str, float]:
    lowered = text.lower()
    numbers: dict[str, float] = {}

    def grab(key: str, patterns: list[str], default: float) -> None:
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                numbers[key] = float(match.group(1).replace(",", ""))
                return
        numbers[key] = default

    if domain == "rate_limiter":
        grab("sustained_rps", [r"(\d+(?:\.\d+)?)\s*(?:requests per second|rps|token/s)"], 100)
        grab("burst", [r"burst(?: capacity)?[^\d]{0,40}(\d+)", r"\*\*(\d+)\s+tokens\*\*"], 25)
        grab("daily_quota", [r"daily quota[^\d]{0,40}(\d[\d,]*)", r"\*\*daily quota of ([0-9,]+)\*\*"], 100000)
        grab("max_keys", [r"(?:at most|track at most)\s+\*\*(\d[\d,]*)", r"(\d[\d,]*)\s+concurrent api keys"], 1000)
        grab("idle_ms", [r"(\d+)\s*ms of idle"], 250)
    elif domain == "handover":
        grab("hysteresis_db", [r"hysteresis[^\d]{0,20}(\d+(?:\.\d+)?)", r"hys[^\d]{0,16}(\d+(?:\.\d+)?)"], 3.0)
        grab("a3_offset_db", [r"a3 offset[^\d]{0,24}(\d+(?:\.\d+)?)", r"off\)[^\d]{0,12}(\d+(?:\.\d+)?)"], 2.0)
        grab("ttt_ms", [r"ttt[^\d]{0,16}(\d+)", r"ttt = \*\*(\d+)"], 320)
        grab("ping_pong_ms", [r"for \*\*(\d+)\s*ms\*\*", r"ping-pong[^\d]{0,48}(\d+)"], 2000)
        grab("rlf_rsrp", [r"(?:below|strictly below)\s+\*\*(-?\d+(?:\.\d+)?)", r"strictly below\s+(-?\d+(?:\.\d+)?)"], -110)
        grab("max_neighbors", [r"at most\s+\*\*(\d+)\*\*\s+neighbor", r"at most\s+(\d+)\s+neighbor"], 3)
    else:
        grab("timeout_ms", [r"(\d+)\s*ms"], 1000)
        grab("limit", [r"(?:limit|max(?:imum)?|at most)\s+(\d[\d,]*)"], 100)
    return numbers
