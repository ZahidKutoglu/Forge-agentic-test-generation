import type { TestCase } from "@/lib/types";
import { intNum, type ParsedSpec } from "./parse";
import type { GeneratedSuite } from "./rateLimiter";

export function architectHandover(parsed: ParsedSpec): TestCase[] {
  const hys = parsed.numbers.hysteresis_db ?? 3.0;
  const off = parsed.numbers.a3_offset_db ?? 2.0;
  const ttt = intNum(parsed.numbers, "ttt_ms", 320);
  const ping = intNum(parsed.numbers, "ping_pong_ms", 2000);
  const rlf = parsed.numbers.rlf_rsrp ?? -110;
  const maxN = intNum(parsed.numbers, "max_neighbors", 3);
  return [
    caseOf("TC-HO-001", "Stay when neighbor does not satisfy A3", "happy_path", "critical", [`Hys=${hys} dB, Off=${off} dB`], ["Evaluate serving vs a slightly stronger neighbor"], ["action is stay"], ["Handover executing on a neighbor that never held A3"], ["a3"]),
    caseOf("TC-HO-002", "A3 must hold continuously for TTT before prepare", "edge_case", "critical", [`TTT=${ttt} ms`], ["Satisfy A3 for TTT-1 ms", "Then for TTT ms"], ["First evaluate stays", "Second evaluate prepares"], ["TTT satisfied by summing non-contiguous A3 glimpses"], ["ttt"]),
    caseOf("TC-HO-003", "Non-contiguous A3 resets the TTT timer", "failure_mode", "high", [], ["A3 true, A3 false, A3 true for TTT-1 ms"], ["action remains stay"], ["TTT satisfied by summing non-contiguous A3 glimpses"], ["ttt"]),
    caseOf("TC-HO-004", "Radio link failure short-circuits A3", "failure_mode", "critical", [`RLF threshold ${rlf} dBm`], ["Serving RSRP below threshold with an attractive neighbor"], ["action is rlf", "A3 is not evaluated"], ["RLF ignored when a neighbor looks attractive"], ["rlf"]),
    caseOf("TC-HO-005", "Empty neighbor list stays unless RLF", "edge_case", "medium", [], ["Evaluate with no neighbors", "Repeat with serving below RLF"], ["stay then rlf"], ["Spurious prepare with no candidates"], ["neighbors"]),
    caseOf("TC-HO-006", "Candidates are ranked by RSRP, then RSRQ, then cell id", "happy_path", "high", [`At most ${maxN} neighbors retained`], ["Feed four neighbors with mixed metrics"], ["Target is the highest ranked A3 cell", "Fourth neighbor discarded"], ["Ranking by cell id only, ignoring RSRP"], ["ranking"]),
    caseOf("TC-HO-007", "Prepare, execute, complete transfers serving cell", "happy_path", "critical", [], ["Hold A3 for TTT", "execute", "complete"], ["actions are prepare, execute, complete", "serving becomes the target"], ["Complete without execute"], ["procedure"]),
    caseOf("TC-HO-008", "Ping-pong guard blocks return to previous serving", "failure_mode", "high", [`Guard=${ping} ms`], ["Complete HO to cell B", "Immediately try A3 back to A"], ["prepare toward previous serving is denied until guard expires"], ["Ping-pong oscillations between two cells faster than 2 seconds"], ["ping-pong"]),
    caseOf("TC-HO-009", "Target dropping A3 during prepare returns to stay", "edge_case", "high", [], ["Enter prepare", "Degrade neighbor below A3"], ["action is stay", "TTT timer cleared"], ["Execute after A3 vanished"], ["prepare"]),
    caseOf("TC-HO-010", "Execute of an unknown target rolls back", "failure_mode", "high", [], ["Prepare on target T", "Evaluate with T missing from neighbors"], ["action is rollback"], ["Execute against a vanished cell"], ["rollback"]),
    caseOf("TC-HO-011", "Blank cell identifiers are illegal", "edge_case", "medium", [], ["Construct a cell with a blank id"], ["ValueError"], ["Coercing blank ids"], ["validation"]),
    caseOf("TC-HO-012", "Decision path uses injected now_ms only", "non_functional", "medium", [], ["Drive the controller with explicit timestamps"], ["Identical traces for identical now_ms sequences"], ["Hidden wall-clock reads"], ["determinism"]),
  ];
}

export function synthesizeHandover(parsed: ParsedSpec): GeneratedSuite {
  const hys = parsed.numbers.hysteresis_db ?? 3.0;
  const off = parsed.numbers.a3_offset_db ?? 2.0;
  const ttt = intNum(parsed.numbers, "ttt_ms", 320);
  const ping = intNum(parsed.numbers, "ping_pong_ms", 2000);
  const rlf = parsed.numbers.rlf_rsrp ?? -110;
  const maxN = intNum(parsed.numbers, "max_neighbors", 3);

  const sutCode = `"""Intra-frequency A3 handover controller generated from the specification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class Cell:
    cell_id: str
    rsrp: float
    rsrq: float = 0.0
    cio: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.cell_id, str) or not self.cell_id.strip():
            raise ValueError("cell_id must be a non-empty string")


@dataclass(frozen=True)
class HandoverDecision:
    action: str
    serving_id: str
    target_id: Optional[str]
    reason: str


class HandoverController:
    def __init__(
        self,
        hysteresis_db: float = ${hys},
        a3_offset_db: float = ${off},
        ttt_ms: int = ${ttt},
        ping_pong_ms: int = ${ping},
        rlf_rsrp: float = ${rlf},
        max_neighbors: int = ${maxN},
        ofn: float = 0.0,
        ofp: float = 0.0,
    ) -> None:
        self.hysteresis_db = hysteresis_db
        self.a3_offset_db = a3_offset_db
        self.ttt_ms = ttt_ms
        self.ping_pong_ms = ping_pong_ms
        self.rlf_rsrp = rlf_rsrp
        self.max_neighbors = max_neighbors
        self.ofn = ofn
        self.ofp = ofp
        self._a3_target: Optional[str] = None
        self._a3_since_ms: Optional[int] = None
        self._phase = "idle"
        self._prepared_target: Optional[str] = None
        self._serving_id: Optional[str] = None
        self._previous_serving_id: Optional[str] = None
        self._last_complete_ms: Optional[int] = None

    def a3(self, serving: Cell, neighbor: Cell) -> bool:
        left = neighbor.rsrp + self.ofn + neighbor.cio - self.hysteresis_db
        right = serving.rsrp + self.ofp + serving.cio + self.a3_offset_db
        return left > right

    def rank(self, neighbors: Iterable[Cell]) -> list[Cell]:
        ranked = sorted(
            neighbors,
            key=lambda cell: (-cell.rsrp, -cell.rsrq, cell.cell_id),
        )
        return ranked[: self.max_neighbors]

    def evaluate(self, serving: Cell, neighbors: list[Cell], now_ms: int) -> HandoverDecision:
        if not isinstance(now_ms, int):
            raise ValueError("now_ms must be an integer")
        self._serving_id = serving.cell_id
        if serving.rsrp < self.rlf_rsrp:
            self._clear_ttt()
            self._phase = "idle"
            return HandoverDecision("rlf", serving.cell_id, None, "radio_link_failure")

        ranked = self.rank(neighbors)
        a3_cells = [cell for cell in ranked if self.a3(serving, cell)]
        target = a3_cells[0] if a3_cells else None

        if self._phase == "prepared":
            if target is None or target.cell_id != self._prepared_target:
                if self._prepared_target and all(cell.cell_id != self._prepared_target for cell in ranked):
                    self._phase = "idle"
                    self._prepared_target = None
                    self._clear_ttt()
                    return HandoverDecision("rollback", serving.cell_id, None, "target_missing")
                self._phase = "idle"
                self._prepared_target = None
                self._clear_ttt()
                return HandoverDecision("stay", serving.cell_id, None, "a3_dropped")
            self._phase = "executed"
            return HandoverDecision("execute", serving.cell_id, target.cell_id, "execute_armed")

        if self._phase == "executed":
            if target is None or target.cell_id != self._prepared_target:
                previous = self._prepared_target
                self._phase = "idle"
                self._prepared_target = None
                self._clear_ttt()
                return HandoverDecision("rollback", serving.cell_id, previous, "execute_failed")
            self._previous_serving_id = serving.cell_id
            self._serving_id = target.cell_id
            self._last_complete_ms = now_ms
            self._phase = "idle"
            self._prepared_target = None
            self._clear_ttt()
            return HandoverDecision("complete", target.cell_id, target.cell_id, "ho_complete")

        if target is None:
            self._clear_ttt()
            return HandoverDecision("stay", serving.cell_id, None, "no_a3")

        if self._blocked_by_ping_pong(target.cell_id, now_ms):
            self._clear_ttt()
            return HandoverDecision("stay", serving.cell_id, None, "ping_pong_guard")

        if self._a3_target != target.cell_id or self._a3_since_ms is None:
            self._a3_target = target.cell_id
            self._a3_since_ms = now_ms
            return HandoverDecision("stay", serving.cell_id, target.cell_id, "ttt_running")

        held = now_ms - self._a3_since_ms
        if held < self.ttt_ms:
            return HandoverDecision("stay", serving.cell_id, target.cell_id, "ttt_running")

        self._phase = "prepared"
        self._prepared_target = target.cell_id
        return HandoverDecision("prepare", serving.cell_id, target.cell_id, "ttt_elapsed")

    def _blocked_by_ping_pong(self, target_id: str, now_ms: int) -> bool:
        if self._previous_serving_id is None or self._last_complete_ms is None:
            return False
        if target_id != self._previous_serving_id:
            return False
        return now_ms - self._last_complete_ms < self.ping_pong_ms

    def _clear_ttt(self) -> None:
        self._a3_target = None
        self._a3_since_ms = None
`;

  const pytestCode = `"""Executable PyTest suite for the generated handover controller."""
from __future__ import annotations

import pytest

from sut import Cell, HandoverController


HYS = ${hys}
OFF = ${off}
TTT = ${ttt}
PING = ${ping}
RLF = ${rlf}


def serving(rsrp: float = -80.0, cell_id: str = "A") -> Cell:
    return Cell(cell_id, rsrp, rsrq=-8.0)


def neighbor(cell_id: str, rsrp: float, rsrq: float = -7.0, cio: float = 0.0) -> Cell:
    return Cell(cell_id, rsrp, rsrq, cio)


def margin() -> float:
    return HYS + OFF + 0.1


def test_stay_when_neighbor_does_not_satisfy_a3() -> None:
    ctl = HandoverController()
    decision = ctl.evaluate(serving(), [neighbor("B", -80.0 + HYS + OFF)], 0)
    assert decision.action == "stay"


def test_a3_requires_continuous_ttt() -> None:
    ctl = HandoverController()
    target = neighbor("B", -80.0 + margin())
    start = ctl.evaluate(serving(), [target], 0)
    early = ctl.evaluate(serving(), [target], TTT - 1)
    armed = ctl.evaluate(serving(), [target], TTT)
    assert start.action == "stay"
    assert early.action == "stay"
    assert armed.action == "prepare"
    assert armed.target_id == "B"


def test_non_contiguous_a3_resets_ttt() -> None:
    ctl = HandoverController()
    strong = neighbor("B", -80.0 + margin())
    weak = neighbor("B", -90.0)
    ctl.evaluate(serving(), [strong], 0)
    ctl.evaluate(serving(), [weak], 100)
    later = ctl.evaluate(serving(), [strong], 100 + TTT - 1)
    assert later.action == "stay"
    assert later.reason == "ttt_running"


def test_rlf_short_circuits_a3() -> None:
    ctl = HandoverController()
    decision = ctl.evaluate(serving(RLF - 1), [neighbor("B", 0.0)], 0)
    assert decision.action == "rlf"
    assert decision.target_id is None


def test_empty_neighbors_stay_unless_rlf() -> None:
    ctl = HandoverController()
    assert ctl.evaluate(serving(), [], 0).action == "stay"
    assert ctl.evaluate(serving(RLF - 5), [], 10).action == "rlf"


def test_ranking_prefers_rsrp_then_rsrq_then_cell_id() -> None:
    ctl = HandoverController()
    cells = [
        neighbor("Z", -80.0 + margin(), rsrq=-9.0),
        neighbor("M", -80.0 + margin() + 2, rsrq=-12.0),
        neighbor("C", -80.0 + margin() + 2, rsrq=-3.0),
        neighbor("Q", -80.0 + margin() + 8, rsrq=-1.0),
    ]
    ctl.evaluate(serving(), cells, 0)
    prepared = ctl.evaluate(serving(), cells, TTT)
    assert prepared.target_id == "Q"
    ranked = ctl.rank(cells)
    assert [cell.cell_id for cell in ranked] == ["Q", "C", "M"]


def test_prepare_execute_complete_transfers_serving() -> None:
    ctl = HandoverController()
    target = neighbor("B", -80.0 + margin())
    ctl.evaluate(serving(), [target], 0)
    prepared = ctl.evaluate(serving(), [target], TTT)
    executed = ctl.evaluate(serving(), [target], TTT + 10)
    completed = ctl.evaluate(serving(), [target], TTT + 20)
    assert prepared.action == "prepare"
    assert executed.action == "execute"
    assert completed.action == "complete"
    assert completed.serving_id == "B"


def test_ping_pong_guard_blocks_immediate_return() -> None:
    ctl = HandoverController()
    cell_b = neighbor("B", -80.0 + margin())
    ctl.evaluate(serving(), [cell_b], 0)
    ctl.evaluate(serving(), [cell_b], TTT)
    ctl.evaluate(serving(), [cell_b], TTT + 1)
    complete_at = TTT + 2
    ctl.evaluate(serving(), [cell_b], complete_at)
    back = neighbor("A", -70.0)
    serving_b = serving(rsrp=-80.0, cell_id="B")
    blocked = ctl.evaluate(serving_b, [back], complete_at + 10)
    assert blocked.action == "stay"
    assert blocked.reason == "ping_pong_guard"
    ctl.evaluate(serving_b, [back], complete_at + PING)
    released = ctl.evaluate(serving_b, [back], complete_at + PING + TTT)
    assert released.action == "prepare"
    assert released.target_id == "A"


def test_prepare_drops_back_to_stay_when_a3_vanishes() -> None:
    ctl = HandoverController()
    strong = neighbor("B", -80.0 + margin())
    ctl.evaluate(serving(), [strong], 0)
    assert ctl.evaluate(serving(), [strong], TTT).action == "prepare"
    dropped = ctl.evaluate(serving(), [neighbor("B", -100.0)], TTT + 5)
    assert dropped.action == "stay"
    assert dropped.reason == "a3_dropped"


def test_execute_unknown_target_rolls_back() -> None:
    ctl = HandoverController()
    strong = neighbor("B", -80.0 + margin())
    ctl.evaluate(serving(), [strong], 0)
    ctl.evaluate(serving(), [strong], TTT)
    rolled = ctl.evaluate(serving(), [neighbor("C", -100.0)], TTT + 5)
    assert rolled.action == "rollback"


def test_blank_cell_id_raises_value_error() -> None:
    with pytest.raises(ValueError):
        Cell("  ", -80.0)


def test_injected_now_ms_is_deterministic() -> None:
    target = neighbor("B", -80.0 + margin())
    first = HandoverController()
    second = HandoverController()
    trace_a = [
        first.evaluate(serving(), [target], 0).action,
        first.evaluate(serving(), [target], TTT).action,
    ]
    trace_b = [
        second.evaluate(serving(), [target], 0).action,
        second.evaluate(serving(), [target], TTT).action,
    ]
    assert trace_a == trace_b == ["stay", "prepare"]
`;

  return {
    sutFilename: "sut.py",
    sutCode,
    testFilename: "test_handover.py",
    pytestCode,
  };
}

function caseOf(
  id: string,
  title: string,
  category: TestCase["category"],
  priority: TestCase["priority"],
  preconditions: string[],
  steps: string[],
  assertions: string[],
  failureModes: string[],
  tags: string[],
): TestCase {
  return { id, title, category, priority, preconditions, steps, assertions, failure_modes: failureModes, tags };
}
