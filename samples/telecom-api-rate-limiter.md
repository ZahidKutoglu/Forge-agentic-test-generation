# Telecom Edge API Rate Limiter

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
  full token bucket; otherwise the new key is rejected with `503`.

## Decision Contract

`allow(api_key: str, cost: int = 1) -> RateLimitDecision`

A `RateLimitDecision` contains:

| Field          | Type    | Meaning                                      |
|----------------|---------|----------------------------------------------|
| allowed        | bool    | Whether the request may proceed              |
| remaining      | int     | Whole tokens remaining after the decision    |
| retry_after_ms | int     | 0 if allowed; otherwise milliseconds to wait |
| reason         | str     | `ok`, `burst_exhausted`, `daily_quota`, `unknown_key_capacity`, `admin_bypass` |

## Behavioral Requirements

1. A request that would drive the bucket below zero MUST be rejected with
   `reason="burst_exhausted"` and `retry_after_ms` equal to the time required
   to refill the missing tokens at the sustained rate.
2. When the daily quota is exhausted, subsequent requests MUST be rejected with
   `reason="daily_quota"` even if burst tokens remain. `retry_after_ms` SHALL
   point at the next UTC midnight.
3. API keys in the **admin bypass set** (`ops-root`, `noc-pager`) MUST always
   be allowed, must not consume tokens, and MUST report `reason="admin_bypass"`.
4. `cost` greater than the burst size MUST be rejected without consuming tokens.
5. Concurrent calls for the same API key MUST be serialized; lost updates to
   the token count are a failure mode.
6. A zero-length or whitespace-only API key MUST raise `ValueError`.
7. Negative `cost` MUST raise `ValueError`.
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
