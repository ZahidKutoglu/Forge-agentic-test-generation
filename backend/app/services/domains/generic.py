"""Generic specification engine SUT + PyTest suite synthesizer."""

from __future__ import annotations

import hashlib
import re
from textwrap import dedent

from app.models.schemas import TestCase
from app.services.spec_parser import ParsedSpec


def architect_generic(parsed: ParsedSpec) -> list[TestCase]:
    cases: list[TestCase] = []
    reqs = parsed.requirements or [
        "The system SHALL reject empty identifiers.",
        "The system SHALL enforce the documented numeric limit.",
        "The system SHALL surface failure modes as typed errors.",
    ]
    categories = ["happy_path", "edge_case", "failure_mode", "security", "concurrency", "non_functional"]
    for index, requirement in enumerate(reqs[:12], start=1):
        category = categories[(index - 1) % len(categories)]
        cases.append(
            TestCase(
                id=f"TC-GEN-{index:03d}",
                title=_title_from_requirement(requirement),
                category=category,  # type: ignore[arg-type]
                priority="high" if index <= 4 else "medium",
                preconditions=[parsed.title],
                steps=[f"Exercise rule R{index:02d} derived from the specification"],
                assertions=[requirement],
                failure_modes=parsed.failure_modes[:2],
                tags=["spec", f"R{index:02d}"],
            )
        )
    if len(cases) < 8:
        cases.extend(
            [
                TestCase(
                    id="TC-GEN-080",
                    title="Unknown rule identifiers are rejected",
                    category="edge_case",
                    preconditions=[],
                    steps=["Query a rule id that was never parsed"],
                    assertions=["KeyError or typed SpecViolation"],
                    failure_modes=["Silent True for unknown rules"],
                    tags=["validation"],
                ),
                TestCase(
                    id="TC-GEN-081",
                    title="Rule evaluation is deterministic",
                    category="non_functional",
                    preconditions=[],
                    steps=["Evaluate the same facts twice"],
                    assertions=["Identical decisions"],
                    failure_modes=["Hidden entropy"],
                    tags=["determinism"],
                ),
            ]
        )
    return cases


def synthesize_generic(parsed: ParsedSpec) -> tuple[str, str, str, str]:
    reqs = parsed.requirements[:16] or [
        "The system SHALL reject empty identifiers.",
        "The system SHALL enforce the documented numeric limit.",
    ]
    limit = int(parsed.numbers.get("limit", 100))
    timeout = int(parsed.numbers.get("timeout_ms", 1000))
    rule_lines = []
    for i, req in enumerate(reqs, start=1):
        rid = f"R{i:02d}"
        kind = _classify_kind(req)
        threshold = _extract_threshold(req, limit)
        rule_lines.append(f"            Rule({rid!r}, {req!r}, {kind!r}, {threshold!r}),")
    rules_block = "\n".join(rule_lines)
    digest = hashlib.sha256(parsed.body.encode("utf-8")).hexdigest()[:16]
    failure_blob = parsed.failure_modes[:8]

    sut = dedent(
        f'''
        """Specification engine generated from an arbitrary requirements document."""
        from __future__ import annotations

        from dataclasses import dataclass
        from threading import Lock
        from typing import Any, Iterable


        class SpecViolation(Exception):
            def __init__(self, rule_id: str, message: str) -> None:
                self.rule_id = rule_id
                super().__init__(f"{{rule_id}}: {{message}}")


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
{rules_block}
        )


        class SpecificationEngine:
            SPEC_DIGEST = "{digest}"
            LIMIT = {limit}
            TIMEOUT_MS = {timeout}
            FAILURE_MODES = {failure_blob!r}

            def __init__(self) -> None:
                self._lock = Lock()
                self._index = {{rule.rule_id: rule for rule in RULES}}

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
        '''
    ).strip() + "\n"

    rule_ids = [f"R{i:02d}" for i in range(1, len(reqs) + 1)]
    first_id = rule_ids[0]
    tests = dedent(
        f'''
        """Executable PyTest suite for the generated specification engine."""
        from __future__ import annotations

        import threading

        import pytest

        from sut import RULES, SpecViolation, SpecificationEngine


        def test_engine_loads_parsed_rules() -> None:
            engine = SpecificationEngine()
            assert len(engine.rules()) == {len(reqs)}
            assert engine.get({first_id!r}).rule_id == {first_id!r}


        def test_happy_path_admits_well_formed_facts() -> None:
            engine = SpecificationEngine()
            decision = engine.evaluate({first_id!r}, {{"id": "alpha", "value": 1}})
            assert decision.allowed is True
            assert decision.reason == "ok"


        def test_empty_identifier_is_rejected() -> None:
            engine = SpecificationEngine()
            decision = engine.evaluate({first_id!r}, {{"id": "  ", "value": 1}})
            assert decision.allowed is False
            with pytest.raises(SpecViolation):
                engine.assert_holds({first_id!r}, {{"id": "", "value": 1}})


        def test_numeric_limit_is_enforced() -> None:
            engine = SpecificationEngine()
            over = engine.evaluate({first_id!r}, {{"id": "alpha", "value": engine.LIMIT + 1}})
            assert over.allowed is False
            assert over.reason == "limit_exceeded"


        def test_unknown_rule_id_raises_key_error() -> None:
            engine = SpecificationEngine()
            with pytest.raises(KeyError):
                engine.get("R999")


        def test_evaluate_all_covers_every_rule() -> None:
            engine = SpecificationEngine()
            decisions = engine.evaluate_all({{"id": "alpha", "value": 1}})
            assert [item.rule_id for item in decisions] == [rule.rule_id for rule in RULES]


        def test_failure_modes_are_captured_on_the_engine() -> None:
            assert isinstance(SpecificationEngine.FAILURE_MODES, list)


        def test_concurrent_evaluation_is_serialized() -> None:
            engine = SpecificationEngine()
            seen = []

            def worker() -> None:
                for _ in range(50):
                    decision = engine.evaluate({first_id!r}, {{"id": "alpha", "value": 1}})
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
                decision = engine.evaluate(rule.rule_id, {{"id": "alpha", "timeout_ms": rule.threshold + 1}})
                assert decision.allowed is False
            else:
                decision = engine.evaluate(rule.rule_id, {{"id": "alpha", "timeout_ms": 1}})
                assert decision.allowed is True
        '''
    ).strip() + "\n"

    return "sut.py", sut, "test_specification.py", tests


def _title_from_requirement(text: str) -> str:
    cleaned = re.sub(r"[*`]", "", text)
    cleaned = re.sub(r"^(the system\s+)?(shall|must)\s+", "", cleaned, flags=re.I)
    return cleaned[:88].rstrip(".") or "Specification rule"


def _classify_kind(text: str) -> str:
    lowered = text.lower()
    if "empty" in lowered or "whitespace" in lowered or "identifier" in lowered:
        return "reject_empty"
    if "timeout" in lowered:
        return "timeout"
    if "must not" in lowered or "shall not" in lowered or "forbidden" in lowered:
        return "must_not"
    if any(token in lowered for token in ("limit", "quota", "at most", "exceed", "max")):
        return "enforce_limit"
    return "admit"


def _extract_threshold(text: str, default: float) -> float:
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)", text)
    if not match:
        return float(default)
    return float(match.group(1).replace(",", ""))
