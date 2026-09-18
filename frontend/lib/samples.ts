import type { SampleSpec } from "./types";

export const FALLBACK_SAMPLES: SampleSpec[] = [
  {
    id: "telecom-api-rate-limiter",
    title: "Telecom API Rate Limiter",
    spec: `# Telecom Edge API Rate Limiter

## Overview

The edge API gateway protecting the subscriber charging and policy control plane
must enforce a token-bucket rate limiter with a secondary daily quota window.
Every public request is identified by an API key. Isolation between keys is
mandatory: one noisy neighbor must never starve another tenant.

## Capacity

- Sustained throughput SHALL be limited to **100 requests per second** per API key.
- Burst capacity SHALL be **25 tokens**. A client may spend the full burst instantly.
- Tokens refill continuously at the sustained rate (100 token/s).
- Each API key also has a **daily quota of 100,000** requests, tracked on UTC day boundaries.
- The gateway SHALL track at most **1,000 concurrent API keys**. Inserting a 1,001st
  distinct key MUST evict the least-recently-used idle key only if that key has a
  full token bucket; otherwise the new key is rejected with \`503\`.

## Decision Contract

\`allow(api_key: str, cost: int = 1) -> RateLimitDecision\`

A \`RateLimitDecision\` contains:

| Field          | Type    | Meaning                                      |
|----------------|---------|----------------------------------------------|
| allowed        | bool    | Whether the request may proceed              |
| remaining      | int     | Whole tokens remaining after the decision    |
| retry_after_ms | int     | 0 if allowed; otherwise milliseconds to wait |
| reason         | str     | \`ok\`, \`burst_exhausted\`, \`daily_quota\`, \`unknown_key_capacity\`, \`admin_bypass\` |

## Behavioral Requirements

1. A request that would drive the bucket below zero MUST be rejected with
   \`reason="burst_exhausted"\` and \`retry_after_ms\` equal to the time required
   to refill the missing tokens at the sustained rate.
2. When the daily quota is exhausted, subsequent requests MUST be rejected with
   \`reason="daily_quota"\` even if burst tokens remain. \`retry_after_ms\` SHALL
   point at the next UTC midnight.
3. API keys in the **admin bypass set** (\`ops-root\`, \`noc-pager\`) MUST always
   be allowed, must not consume tokens, and MUST report \`reason="admin_bypass"\`.
4. \`cost\` greater than the burst size MUST be rejected without consuming tokens.
5. Concurrent calls for the same API key MUST be serialized; lost updates to
   the token count are a failure mode.
6. A zero-length or whitespace-only API key MUST raise \`ValueError\`.
7. Negative \`cost\` MUST raise \`ValueError\`.
8. After 250 ms of idle time at 100 rps, a bucket that started empty SHALL
   hold 25 tokens (clamped to burst), never more.

## Failure Modes

- Silent admission after burst exhaustion.
- Shared token state across API keys.
- Daily quota leaking across UTC day boundaries.
- Retry-After advertised as seconds when the contract requires milliseconds.
- Admin keys consuming tenant budget.

## Non-Functional

- Decision path MUST complete in-process with no I/O.
- The implementation MUST be deterministic when a monotonic clock is injected.
`,
  },
  {
    id: "wireless-handover-logic",
    title: "Wireless Handover Logic",
    spec: `# Wireless Intra-Frequency Handover Controller

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

\`\`\`
Mn + Ofn + Ocn - Hys > Mp + Ofp + Ocp + Off
\`\`\`

Where:

- \`Mn\` / \`Mp\` are neighbor / serving RSRP.
- \`Ofn\`, \`Ofp\` are frequency offsets (0 dB for intra-frequency).
- \`Ocn\`, \`Ocp\` are cell individual offsets (CIO), default 0 dB.
- \`Hys\` (hysteresis) = **3.0 dB**.
- \`Off\` (A3 offset) = **2.0 dB**.

A3 must remain true continuously for **TTT = 320 ms** before HO prepare is armed.

## Procedure

\`evaluate(serving: Cell, neighbors: list[Cell], now_ms: int) -> HandoverDecision\`

\`HandoverDecision.action\` is one of:

- \`stay\` — no A3, radio link healthy
- \`prepare\` — A3 held for TTT, target reserved
- \`execute\` — prepare succeeded and target still best
- \`complete\` — execute acknowledged; serving cell becomes the target
- \`rollback\` — execute failed or target dropped out; revert to previous serving
- \`rlf\` — serving below RLF threshold

## Rules

1. Candidate ranking uses RSRP descending, then RSRQ descending, then cell id ascending.
2. The chosen target MUST be the highest-ranked neighbor that currently satisfies A3.
3. Ping-pong guard: after a successful \`complete\`, no new prepare toward the
   **previous** serving cell is allowed for **2000 ms**.
4. If serving RSRP < -110 dBm, action is \`rlf\` immediately; A3 is not evaluated.
5. An empty neighbor list yields \`stay\` unless RLF applies.
6. During \`prepare\`, if the target no longer satisfies A3, action returns to \`stay\`
   and the TTT timer is cleared.
7. \`execute\` MUST fail (rollback) if the target cell id is unknown in the current
   neighbor list.
8. Cell identifiers are strings; blank cell ids are illegal and MUST raise \`ValueError\`.

## Failure Modes

- Handover executing on a neighbor that never held A3 for the full TTT.
- Ping-pong oscillations between two cells faster than 2 seconds.
- Ranking by cell id only, ignoring RSRP.
- RLF ignored when a neighbor looks attractive.
- TTT satisfied by summing non-contiguous A3 glimpses.

## Determinism

The controller is a pure state machine. \`now_ms\` is always injected; wall clocks
are forbidden inside the decision path.
`,
  },
];
