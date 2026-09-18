import type { TestCase } from "@/lib/types";
import { intNum, py, type ParsedSpec } from "./parse";
import type { GeneratedSuite } from "./rateLimiter";

const CATEGORIES: TestCase["category"][] = [
  "happy_path",
  "edge_case",
  "failure_mode",
  "security",
  "concurrency",
  "non_functional",
];

export function architectGeneric(parsed: ParsedSpec): TestCase[] {
  const reqs = parsed.requirements.length
    ? parsed.requirements
    : [
        "The system SHALL reject empty identifiers.",
        "The system SHALL enforce the documented numeric limit.",
        "The system SHALL surface failure modes as typed errors.",
      ];
  const cases: TestCase[] = reqs.slice(0, 12).map((requirement, index) => {
    const n = index + 1;
    return {
      id: `TC-GEN-${String(n).padStart(3, "0")}`,
      title: titleFromRequirement(requirement),
      category: CATEGORIES[(n - 1) % CATEGORIES.length],
      priority: n <= 4 ? "high" : "medium",
      preconditions: [parsed.title],
      steps: [`Exercise rule R${String(n).padStart(2, "0")} derived from the specification`],
      assertions: [requirement],
      failure_modes: parsed.failureModes.slice(0, 2),
      tags: ["spec", `R${String(n).padStart(2, "0")}`],
    };
  });
  if (cases.length < 8) {
    cases.push(
      {
        id: "TC-GEN-080",
        title: "Unknown rule identifiers are rejected",
        category: "edge_case",
        priority: "medium",
        preconditions: [],
        steps: ["Query a rule id that was never parsed"],
        assertions: ["KeyError or typed SpecViolation"],
        failure_modes: ["Silent True for unknown rules"],
        tags: ["validation"],
      },
      {
        id: "TC-GEN-081",
        title: "Rule evaluation is deterministic",
        category: "non_functional",
        priority: "medium",
        preconditions: [],
        steps: ["Evaluate the same facts twice"],
        assertions: ["Identical decisions"],
        failure_modes: ["Hidden entropy"],
        tags: ["determinism"],
      },
    );
  }
  return cases;
}

export function synthesizeGeneric(parsed: ParsedSpec): GeneratedSuite {
  const reqs = parsed.requirements.slice(0, 16).length
    ? parsed.requirements.slice(0, 16)
    : ["The system SHALL reject empty identifiers.", "The system SHALL enforce the documented numeric limit."];
  const limit = intNum(parsed.numbers, "limit", 100);
  const timeout = intNum(parsed.numbers, "timeout_ms", 1000);
  const rulesBlock = reqs
    .map((req, index) => {
      const rid = `R${String(index + 1).padStart(2, "0")}`;
      return `            Rule(${py(rid)}, ${py(req)}, ${py(classifyKind(req))}, ${extractThreshold(req, limit)}),`;
    })
    .join("\n");
  const digest = digest16(parsed.body);
  const firstId = "R01";

  const sutCode = `"""Specification engine generated from an arbitrary requirements document."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


class SpecViolation(Exception):
    def __init__(self, rule_id: str, message: str) -> None:
        self.rule_id = rule_id
        super().__init__(f"\${rule_id}: \${message}")


@dataclass(frozen=True)
class Rule:
    rule_id: str
    statement: str
    kind: str
    threshold: float


@dataclass(frozen=True)
class Decision:
    allowed: bool
    rule_id: str
    reason: str


RULES: tuple[Rule, ...] = (
${rulesBlock}
)


class SpecificationEngine:
    SPEC_DIGEST = ${py(digest)}
    LIMIT = ${limit}
    TIMEOUT_MS = ${timeout}
    FAILURE_MODES = ${py(parsed.failureModes.slice(0, 8))}

    def __init__(self) -> None:
        self._lock = Lock()
        self._index = {rule.rule_id: rule for rule in RULES}

    def rules(self) -> list[Rule]:
        return list(RULES)

    def get(self, rule_id: str) -> Rule:
        if rule_id not in self._index:
            raise KeyError(rule_id)
        return self._index[rule_id]

    def evaluate(self, rule_id: str, facts: dict[str, Any]) -> Decision:
        rule = self.get(rule_id)
        with self._lock:
            return self._evaluate(rule, facts)

    def evaluate_all(self, facts: dict[str, Any]) -> list[Decision]:
        return [self.evaluate(rule.rule_id, facts) for rule in RULES]

    def assert_holds(self, rule_id: str, facts: dict[str, Any]) -> None:
        decision = self.evaluate(rule_id, facts)
        if not decision.allowed:
            raise SpecViolation(rule_id, decision.reason)

    def _evaluate(self, rule: Rule, facts: dict[str, Any]) -> Decision:
        identifier = str(facts.get("id", facts.get("identifier", "sample")))
        value = float(facts.get("value", facts.get("count", 0)))
        timeout_ms = float(facts.get("timeout_ms", self.TIMEOUT_MS))

        if rule.kind == "reject_empty" and not identifier.strip():
            return Decision(False, rule.rule_id, "empty_identifier")
        if rule.kind == "enforce_limit" and value > rule.threshold:
            return Decision(False, rule.rule_id, "limit_exceeded")
        if rule.kind == "timeout" and timeout_ms > rule.threshold:
            return Decision(False, rule.rule_id, "timeout_exceeded")
        if rule.kind == "must_not" and bool(facts.get("forbidden", False)):
            return Decision(False, rule.rule_id, "forbidden_state")
        if not identifier.strip():
            return Decision(False, rule.rule_id, "empty_identifier")
        if value > self.LIMIT:
            return Decision(False, rule.rule_id, "limit_exceeded")
        return Decision(True, rule.rule_id, "ok")
`;

  const pytestCode = `"""Executable PyTest suite for the generated specification engine."""
from __future__ import annotations

import threading

import pytest

from sut import RULES, SpecViolation, SpecificationEngine


def test_engine_loads_parsed_rules() -> None:
    engine = SpecificationEngine()
    assert len(engine.rules()) == ${reqs.length}
    assert engine.get(${py(firstId)}).rule_id == ${py(firstId)}


def test_happy_path_admits_well_formed_facts() -> None:
    engine = SpecificationEngine()
    decision = engine.evaluate(${py(firstId)}, {"id": "alpha", "value": 1})
    assert decision.allowed is True
    assert decision.reason == "ok"


def test_empty_identifier_is_rejected() -> None:
    engine = SpecificationEngine()
    decision = engine.evaluate(${py(firstId)}, {"id": "  ", "value": 1})
    assert decision.allowed is False
    with pytest.raises(SpecViolation):
        engine.assert_holds(${py(firstId)}, {"id": "", "value": 1})


def test_numeric_limit_is_enforced() -> None:
    engine = SpecificationEngine()
    over = engine.evaluate(${py(firstId)}, {"id": "alpha", "value": engine.LIMIT + 1})
    assert over.allowed is False
    assert over.reason == "limit_exceeded"


def test_unknown_rule_id_raises_key_error() -> None:
    engine = SpecificationEngine()
    with pytest.raises(KeyError):
        engine.get("R999")


def test_evaluate_all_covers_every_rule() -> None:
    engine = SpecificationEngine()
    decisions = engine.evaluate_all({"id": "alpha", "value": 1})
    assert [item.rule_id for item in decisions] == [rule.rule_id for rule in RULES]


def test_failure_modes_are_captured_on_the_engine() -> None:
    assert isinstance(SpecificationEngine.FAILURE_MODES, list)


def test_concurrent_evaluation_is_serialized() -> None:
    engine = SpecificationEngine()
    seen = []

    def worker() -> None:
        for _ in range(50):
            decision = engine.evaluate(${py(firstId)}, {"id": "alpha", "value": 1})
            seen.append(decision.allowed)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(seen)
    assert len(seen) == 400


def test_spec_digest_is_stable() -> None:
    assert len(SpecificationEngine.SPEC_DIGEST) == 16
    assert SpecificationEngine().SPEC_DIGEST == SpecificationEngine.SPEC_DIGEST


def test_timeout_fact_is_honored_when_present() -> None:
    engine = SpecificationEngine()
    rule = next((item for item in RULES if item.kind == "timeout"), RULES[0])
    if rule.kind == "timeout":
        decision = engine.evaluate(rule.rule_id, {"id": "alpha", "timeout_ms": rule.threshold + 1})
        assert decision.allowed is False
    else:
        decision = engine.evaluate(rule.rule_id, {"id": "alpha", "timeout_ms": 1})
        assert decision.allowed is True
`;

  return {
    sutFilename: "sut.py",
    sutCode,
    testFilename: "test_specification.py",
    pytestCode,
  };
}

function titleFromRequirement(text: string): string {
  const cleaned = text
    .replace(/[`*]/g, "")
    .replace(/^(the system\s+)?(shall|must)\s+/i, "")
    .slice(0, 88)
    .replace(/\.$/, "");
  return cleaned || "Specification rule";
}

function classifyKind(text: string): string {
  const lowered = text.toLowerCase();
  if (lowered.includes("empty") || lowered.includes("whitespace") || lowered.includes("identifier")) return "reject_empty";
  if (lowered.includes("timeout")) return "timeout";
  if (lowered.includes("must not") || lowered.includes("shall not") || lowered.includes("forbidden")) return "must_not";
  if (["limit", "quota", "at most", "exceed", "max"].some((token) => lowered.includes(token))) return "enforce_limit";
  return "admit";
}

function extractThreshold(text: string, fallback: number): number {
  const match = text.match(/(\d[\d,]*(?:\.\d+)?)/);
  if (!match) return fallback;
  return Number.parseFloat(match[1].replace(/,/g, ""));
}

function digest16(text: string): string {
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (let i = 0; i < text.length; i += 1) {
    h1 ^= text.charCodeAt(i);
    h1 = Math.imul(h1, 0x01000193);
    h2 = Math.imul(h2 ^ text.charCodeAt(i), 16777619);
  }
  return ((h1 >>> 0).toString(16).padStart(8, "0") + (h2 >>> 0).toString(16).padStart(8, "0")).slice(0, 16);
}
