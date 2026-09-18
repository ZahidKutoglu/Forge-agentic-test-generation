"""Token-bucket rate limiter SUT + PyTest suite synthesizer."""

from __future__ import annotations

from textwrap import dedent

from app.models.schemas import TestCase
from app.services.spec_parser import ParsedSpec


def architect_rate_limiter(parsed: ParsedSpec) -> list[TestCase]:
    burst = int(parsed.numbers.get("burst", 25))
    rps = int(parsed.numbers.get("sustained_rps", 100))
    quota = int(parsed.numbers.get("daily_quota", 100_000))
    max_keys = int(parsed.numbers.get("max_keys", 1000))
    idle_ms = int(parsed.numbers.get("idle_ms", 250))
    return [
        TestCase(
            id="TC-RL-001",
            title="Admit requests within burst capacity",
            category="happy_path",
            priority="critical",
            preconditions=[f"Limiter configured with burst={burst}, rps={rps}"],
            steps=[f"Issue {burst} cost-1 requests for a fresh key"],
            assertions=["All decisions.allowed is True", "reason is ok", "remaining ends at 0"],
            failure_modes=["Silent reject inside burst"],
            tags=["token-bucket", "admit"],
        ),
        TestCase(
            id="TC-RL-002",
            title="Reject the request that exhausts the bucket",
            category="edge_case",
            priority="critical",
            preconditions=["Fresh key with a full burst"],
            steps=[f"Issue {burst + 1} cost-1 requests with no elapsed time"],
            assertions=["Last decision is rejected", "reason is burst_exhausted", "retry_after_ms > 0"],
            failure_modes=["Silent admission after burst exhaustion"],
            tags=["burst"],
        ),
        TestCase(
            id="TC-RL-003",
            title="Refill clamps to burst after idle time",
            category="edge_case",
            priority="high",
            preconditions=["Empty bucket", f"Idle {idle_ms} ms at {rps} rps"],
            steps=["Advance injected clock", "Observe remaining tokens"],
            assertions=[f"Remaining equals burst ({burst}), never more"],
            failure_modes=["Unbounded refill"],
            tags=["refill"],
        ),
        TestCase(
            id="TC-RL-004",
            title="Per-key isolation",
            category="failure_mode",
            priority="critical",
            preconditions=["Two distinct API keys"],
            steps=["Exhaust key A", "Admit key B"],
            assertions=["Key B remains allowed", "Key A remains rejected"],
            failure_modes=["Shared token state across API keys"],
            tags=["isolation"],
        ),
        TestCase(
            id="TC-RL-005",
            title="Daily quota overrides remaining burst",
            category="failure_mode",
            priority="high",
            preconditions=[f"Daily quota set to a small N << {quota}"],
            steps=["Consume daily quota", "Attempt another request with tokens remaining"],
            assertions=["Rejected with reason daily_quota", "retry_after_ms points at next UTC midnight"],
            failure_modes=["Daily quota leaking across UTC day boundaries"],
            tags=["quota"],
        ),
        TestCase(
            id="TC-RL-006",
            title="Admin bypass never consumes budget",
            category="security",
            priority="high",
            preconditions=[f"Admin keys: {', '.join(parsed.admin_keys)}"],
            steps=["Issue many requests as an admin key"],
            assertions=["Always allowed", "reason is admin_bypass", "remaining unchanged"],
            failure_modes=["Admin keys consuming tenant budget"],
            tags=["admin"],
        ),
        TestCase(
            id="TC-RL-007",
            title="Cost greater than burst is a no-op reject",
            category="edge_case",
            priority="medium",
            steps=[f"Request cost={burst + 5} on a full bucket"],
            assertions=["Rejected", "remaining still equals burst"],
            failure_modes=["Partial consume of illegal cost"],
            tags=["cost"],
        ),
        TestCase(
            id="TC-RL-008",
            title="Invalid API key and cost raise ValueError",
            category="edge_case",
            priority="medium",
            steps=["Call allow with blank key", "Call allow with negative cost"],
            assertions=["ValueError in both cases"],
            failure_modes=["Coercing invalid input into a decision"],
            tags=["validation"],
        ),
        TestCase(
            id="TC-RL-009",
            title="Retry-After is advertised in milliseconds",
            category="non_functional",
            priority="high",
            steps=["Exhaust burst", "Read retry_after_ms"],
            assertions=["Value is int milliseconds matching missing-token refill time"],
            failure_modes=["Retry-After advertised as seconds"],
            tags=["contract"],
        ),
        TestCase(
            id="TC-RL-010",
            title="Key table capacity evicts idle tenants only",
            category="failure_mode",
            priority="medium",
            preconditions=[f"max_keys={max_keys} (tested with a scaled-down table)"],
            steps=["Fill table with idle full buckets", "Insert one more key", "Fill table with busy keys"],
            assertions=["Idle eviction succeeds", "Busy table yields unknown_key_capacity / 503 semantics"],
            failure_modes=["Evicting an in-budget tenant"],
            tags=["capacity"],
        ),
        TestCase(
            id="TC-RL-011",
            title="Concurrent allow() calls do not lose token updates",
            category="concurrency",
            priority="high",
            steps=["Hammer a single key from several threads"],
            assertions=["Admitted + remaining + rejected accounts for burst exactly"],
            failure_modes=["Lost updates to the token count"],
            tags=["threading"],
        ),
        TestCase(
            id="TC-RL-012",
            title="Injected clock makes decisions deterministic",
            category="non_functional",
            priority="medium",
            steps=["Drive the limiter exclusively with a fake monotonic clock"],
            assertions=["No wall-clock reads; identical traces for identical timestamps"],
            failure_modes=["Hidden time.time() calls"],
            tags=["determinism"],
        ),
    ]


def synthesize_rate_limiter(parsed: ParsedSpec) -> tuple[str, str, str, str]:
    burst = int(parsed.numbers.get("burst", 25))
    rps = float(parsed.numbers.get("sustained_rps", 100))
    quota = int(parsed.numbers.get("daily_quota", 100_000))
    max_keys = int(parsed.numbers.get("max_keys", 1000))
    idle_ms = int(parsed.numbers.get("idle_ms", 250))
    admin = parsed.admin_keys or ["ops-root", "noc-pager"]
    admin_lit = ", ".join(repr(item) for item in admin)

    sut = dedent(
        f'''
        """Token-bucket API rate limiter generated from the specification."""
        from __future__ import annotations

        import threading
        from dataclasses import dataclass
        from datetime import datetime, timezone
        from typing import Callable, Dict, Optional, Set


        @dataclass(frozen=True)
        class RateLimitDecision:
            allowed: bool
            remaining: int
            retry_after_ms: int
            reason: str


        @dataclass
        class _Bucket:
            tokens: float
            last_refill: float
            last_used: float
            daily_count: int
            day_id: int


        class RateLimiter:
            """In-process limiter with per-key isolation and an injected clock."""

            def __init__(
                self,
                sustained_rps: float = {rps},
                burst: int = {burst},
                daily_quota: int = {quota},
                max_keys: int = {max_keys},
                admin_keys: Optional[Set[str]] = None,
                clock: Optional[Callable[[], float]] = None,
                utcnow: Optional[Callable[[], datetime]] = None,
            ) -> None:
                if sustained_rps <= 0 or burst <= 0 or daily_quota <= 0 or max_keys <= 0:
                    raise ValueError("limiter capacities must be positive")
                self.sustained_rps = float(sustained_rps)
                self.burst = int(burst)
                self.daily_quota = int(daily_quota)
                self.max_keys = int(max_keys)
                self.admin_keys = set(admin_keys or [{admin_lit}])
                self._clock = clock or _monotonic
                self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))
                self._lock = threading.RLock()
                self._buckets: Dict[str, _Bucket] = {{}}

            def allow(self, api_key: str, cost: int = 1) -> RateLimitDecision:
                if not isinstance(api_key, str) or not api_key.strip():
                    raise ValueError("api_key must be a non-empty string")
                if not isinstance(cost, int) or cost < 0:
                    raise ValueError("cost must be a non-negative integer")

                key = api_key.strip()
                now = float(self._clock())
                utc = self._utcnow()
                day_id = utc.year * 10000 + utc.month * 100 + utc.day

                with self._lock:
                    if key in self.admin_keys:
                        bucket = self._buckets.get(key)
                        remaining = self.burst if bucket is None else int(bucket.tokens)
                        return RateLimitDecision(True, remaining, 0, "admin_bypass")

                    if cost > self.burst:
                        bucket = self._ensure_bucket(key, now, day_id)
                        self._refill(bucket, now, day_id)
                        return RateLimitDecision(False, int(bucket.tokens), 0, "burst_exhausted")

                    bucket = self._ensure_bucket(key, now, day_id)
                    self._refill(bucket, now, day_id)

                    if bucket.daily_count + cost > self.daily_quota:
                        retry = _ms_until_next_midnight(utc)
                        return RateLimitDecision(False, int(bucket.tokens), retry, "daily_quota")

                    if bucket.tokens + 1e-9 < cost:
                        missing = cost - bucket.tokens
                        retry = int(round((missing / self.sustained_rps) * 1000))
                        return RateLimitDecision(False, int(bucket.tokens), max(retry, 1), "burst_exhausted")

                    bucket.tokens -= cost
                    bucket.daily_count += cost
                    bucket.last_used = now
                    return RateLimitDecision(True, int(bucket.tokens), 0, "ok")

            def _ensure_bucket(self, key: str, now: float, day_id: int) -> _Bucket:
                existing = self._buckets.get(key)
                if existing is not None:
                    return existing
                if len(self._buckets) >= self.max_keys:
                    victim = self._lru_idle_full(now)
                    if victim is None:
                        raise KeyTableFull(key)
                    del self._buckets[victim]
                bucket = _Bucket(float(self.burst), now, now, 0, day_id)
                self._buckets[key] = bucket
                return bucket

            def _lru_idle_full(self, now: float) -> Optional[str]:
                idle = [
                    (bucket.last_used, key)
                    for key, bucket in self._buckets.items()
                    if bucket.tokens >= self.burst - 1e-9
                ]
                if not idle:
                    return None
                idle.sort()
                return idle[0][1]

            def _refill(self, bucket: _Bucket, now: float, day_id: int) -> None:
                if day_id != bucket.day_id:
                    bucket.daily_count = 0
                    bucket.day_id = day_id
                elapsed = max(0.0, now - bucket.last_refill)
                bucket.tokens = min(self.burst, bucket.tokens + elapsed * self.sustained_rps)
                bucket.last_refill = now


        class KeyTableFull(Exception):
            def __init__(self, api_key: str) -> None:
                super().__init__(api_key)
                self.api_key = api_key
                self.reason = "unknown_key_capacity"


        def _monotonic() -> float:
            import time
            return time.monotonic()


        def _ms_until_next_midnight(utc: datetime) -> int:
            tomorrow = utc.replace(hour=0, minute=0, second=0, microsecond=0)
            from datetime import timedelta
            tomorrow = tomorrow + timedelta(days=1)
            return max(int((tomorrow - utc).total_seconds() * 1000), 1)


        def decision_or_capacity(limiter: RateLimiter, api_key: str, cost: int = 1) -> RateLimitDecision:
            try:
                return limiter.allow(api_key, cost)
            except KeyTableFull:
                return RateLimitDecision(False, 0, 0, "unknown_key_capacity")
        '''
    ).strip() + "\n"

    tests = dedent(
        f'''
        """Executable PyTest suite for the generated rate limiter."""
        from __future__ import annotations

        import threading
        from datetime import datetime, timezone
        from unittest.mock import Mock

        import pytest

        from sut import KeyTableFull, RateLimiter, decision_or_capacity


        BURST = {burst}
        RPS = {rps}
        IDLE_MS = {idle_ms}
        ADMIN = {admin!r}


        class FakeClock:
            def __init__(self, t: float = 0.0) -> None:
                self.t = t

            def __call__(self) -> float:
                return self.t

            def advance(self, seconds: float) -> None:
                self.t += seconds


        @pytest.fixture
        def clock() -> FakeClock:
            return FakeClock()


        @pytest.fixture
        def limiter(clock: FakeClock) -> RateLimiter:
            return RateLimiter(clock=clock)


        def test_admits_requests_within_burst_capacity(limiter: RateLimiter) -> None:
            last = None
            for _ in range(BURST):
                last = limiter.allow("tenant-a")
                assert last.allowed is True
                assert last.reason == "ok"
            assert last is not None
            assert last.remaining == 0


        def test_rejects_request_that_exhausts_the_bucket(limiter: RateLimiter) -> None:
            for _ in range(BURST):
                limiter.allow("tenant-a")
            decision = limiter.allow("tenant-a")
            assert decision.allowed is False
            assert decision.reason == "burst_exhausted"
            assert decision.retry_after_ms > 0
            assert isinstance(decision.retry_after_ms, int)


        def test_refill_clamps_to_burst(limiter: RateLimiter, clock: FakeClock) -> None:
            for _ in range(BURST):
                limiter.allow("tenant-a")
            clock.advance(IDLE_MS / 1000)
            refilled = limiter.allow("tenant-a", cost=0)
            assert refilled.remaining == min(BURST, int((IDLE_MS / 1000) * RPS))
            clock.advance(30)
            clamped = limiter.allow("tenant-a", cost=0)
            assert clamped.remaining == BURST


        def test_per_key_isolation(limiter: RateLimiter) -> None:
            for _ in range(BURST):
                limiter.allow("alpha")
            blocked = limiter.allow("alpha")
            admitted = limiter.allow("bravo")
            assert blocked.allowed is False
            assert admitted.allowed is True
            assert admitted.remaining == BURST - 1


        def test_daily_quota_overrides_burst(clock: FakeClock) -> None:
            utc = Mock(return_value=datetime(2026, 9, 17, 23, 59, 0, tzinfo=timezone.utc))
            limiter = RateLimiter(daily_quota=3, clock=clock, utcnow=utc)
            assert limiter.allow("quota-key").allowed is True
            assert limiter.allow("quota-key").allowed is True
            assert limiter.allow("quota-key").allowed is True
            decision = limiter.allow("quota-key")
            assert decision.allowed is False
            assert decision.reason == "daily_quota"
            assert decision.retry_after_ms == 60_000


        def test_daily_quota_resets_on_utc_day_boundary(clock: FakeClock) -> None:
            utc = Mock(side_effect=[
                datetime(2026, 9, 17, 23, 59, 0, tzinfo=timezone.utc),
                datetime(2026, 9, 17, 23, 59, 0, tzinfo=timezone.utc),
                datetime(2026, 9, 18, 0, 0, 1, tzinfo=timezone.utc),
            ])
            limiter = RateLimiter(daily_quota=1, clock=clock, utcnow=utc)
            assert limiter.allow("quota-key").allowed is True
            assert limiter.allow("quota-key").reason == "daily_quota"
            assert limiter.allow("quota-key").allowed is True


        @pytest.mark.parametrize("admin_key", ADMIN)
        def test_admin_bypass_never_consumes_budget(limiter: RateLimiter, admin_key: str) -> None:
            first = limiter.allow(admin_key)
            many = [limiter.allow(admin_key) for _ in range(BURST * 3)]
            assert first.reason == "admin_bypass"
            assert first.allowed is True
            assert all(item.allowed and item.reason == "admin_bypass" for item in many)
            tenant = limiter.allow("tenant-z")
            assert tenant.remaining == BURST - 1


        def test_cost_greater_than_burst_is_noop_reject(limiter: RateLimiter) -> None:
            decision = limiter.allow("tenant-a", cost=BURST + 5)
            assert decision.allowed is False
            probe = limiter.allow("tenant-a")
            assert probe.allowed is True
            assert probe.remaining == BURST - 1


        def test_invalid_api_key_and_cost_raise_value_error(limiter: RateLimiter) -> None:
            with pytest.raises(ValueError):
                limiter.allow("   ")
            with pytest.raises(ValueError):
                limiter.allow("tenant-a", cost=-1)


        def test_retry_after_is_milliseconds_for_missing_tokens(limiter: RateLimiter) -> None:
            for _ in range(BURST):
                limiter.allow("tenant-a")
            decision = limiter.allow("tenant-a")
            expected = int(round((1 / RPS) * 1000))
            assert decision.retry_after_ms == max(expected, 1)


        def test_key_table_evicts_idle_full_buckets_only() -> None:
            from sut import _Bucket

            clock = FakeClock()
            limiter = RateLimiter(max_keys=2, clock=clock)
            limiter._buckets["one"] = _Bucket(float(BURST), clock.t, 1.0, 0, 20260917)
            limiter._buckets["two"] = _Bucket(float(BURST), clock.t, 2.0, 0, 20260917)
            admitted = limiter.allow("three")
            assert admitted.allowed is True
            assert "one" not in limiter._buckets
            assert "three" in limiter._buckets

            busy = RateLimiter(max_keys=2, clock=clock)
            busy._buckets["one"] = _Bucket(0.0, clock.t, clock.t, 0, 20260917)
            busy._buckets["two"] = _Bucket(0.0, clock.t, clock.t, 0, 20260917)
            decision = decision_or_capacity(busy, "three")
            assert decision.reason == "unknown_key_capacity"
            with pytest.raises(KeyTableFull):
                busy.allow("three")


        def test_concurrent_allow_does_not_lose_updates() -> None:
            limiter = RateLimiter()
            admitted = []
            lock = threading.Lock()

            def worker() -> None:
                for _ in range(BURST):
                    decision = limiter.allow("shared")
                    if decision.allowed:
                        with lock:
                            admitted.append(1)

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            leftover = limiter.allow("shared")
            assert leftover.allowed is False
            assert sum(admitted) == BURST


        def test_injected_clock_is_used_instead_of_wall_clock() -> None:
            clock = FakeClock(t=10.0)
            limiter = RateLimiter(clock=clock)
            for _ in range(BURST):
                limiter.allow("tenant-a")
            clock.advance(1 / RPS)
            decision = limiter.allow("tenant-a")
            assert decision.allowed is True
        '''
    ).strip() + "\n"

    return "sut.py", sut, "test_rate_limiter.py", tests
