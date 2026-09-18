# Wireless Intra-Frequency Handover Controller

## Overview

The UE handover controller evaluates serving and neighbor cells on the same
frequency and decides whether to stay, prepare, execute, or declare radio link
failure. The algorithm follows an A3-style event with hysteresis, time-to-trigger,
candidate ranking, and ping-pong suppression.

## Radio Model

- RSRP is measured in dBm. RSRQ is measured in dB.
- Radio link failure (RLF) SHALL be declared when serving RSRP is **strictly below -110 dBm**.
- At most **3 neighbor cells** are considered. Extra neighbors are discarded after ranking.

## A3 Event

Event A3 is true when:

```
Mn + Ofn + Ocn - Hys > Mp + Ofp + Ocp + Off
```

Where:

- `Mn` / `Mp` are neighbor / serving RSRP.
- `Ofn`, `Ofp` are frequency offsets (0 dB for intra-frequency).
- `Ocn`, `Ocp` are cell individual offsets (CIO), default 0 dB.
- `Hys` (hysteresis) = **3.0 dB**.
- `Off` (A3 offset) = **2.0 dB**.

A3 must remain true continuously for **TTT = 320 ms** before HO prepare is armed.

## Procedure

`evaluate(serving: Cell, neighbors: list[Cell], now_ms: int) -> HandoverDecision`

`HandoverDecision.action` is one of:

- `stay` — no A3, radio link healthy
- `prepare` — A3 held for TTT, target reserved
- `execute` — prepare succeeded and target still best
- `complete` — execute acknowledged; serving cell becomes the target
- `rollback` — execute failed or target dropped out; revert to previous serving
- `rlf` — serving below RLF threshold

## Rules

1. Candidate ranking uses RSRP descending, then RSRQ descending, then cell id ascending.
2. The chosen target MUST be the highest-ranked neighbor that currently satisfies A3.
3. Ping-pong guard: after a successful `complete`, no new prepare toward the
   **previous** serving cell is allowed for **2000 ms**.
4. If serving RSRP < -110 dBm, action is `rlf` immediately; A3 is not evaluated.
5. An empty neighbor list yields `stay` unless RLF applies.
6. During `prepare`, if the target no longer satisfies A3, action returns to `stay`
   and the TTT timer is cleared.
7. `execute` MUST fail (rollback) if the target cell id is unknown in the current
   neighbor list.
8. Cell identifiers are strings; blank cell ids are illegal and MUST raise `ValueError`.

## Failure Modes

- Handover executing on a neighbor that never held A3 for the full TTT.
- Ping-pong oscillations between two cells faster than 2 seconds.
- Ranking by cell id only, ignoring RSRP.
- RLF ignored when a neighbor looks attractive.
- TTT satisfied by summing non-contiguous A3 glimpses.

## Determinism

The controller is a pure state machine. `now_ms` is always injected; wall clocks
are forbidden inside the decision path.
