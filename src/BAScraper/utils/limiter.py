import asyncio
import time
from aiolimiter import AsyncLimiter


class AdaptiveRateLimiter:
    """
    One-process, multi-task safe limiter using:
      ratelimit-remaining (tokens left)
      ratelimit-reset     (seconds until refill/reset)

      Token gate: never allow more than locally-tracked remaining tokens before reset.
      Pacing: also apply a smooth AsyncLimiter to spread requests out.
    """

    def __init__(self, *, safety_margin: int = 1, max_pace_period: float = 60.0):
        self._lock = asyncio.Lock()
        self._cv = asyncio.Condition(self._lock)

        self._tokens = None  # locally reserved remaining tokens
        self._reset_at = 0.0  # monotonic time when tokens reset
        self._pace = AsyncLimiter(1000, 1)  # permissive until first update

        self._safety_margin = max(0, int(safety_margin))
        self._max_pace_period = float(max_pace_period)

    async def acquire(self) -> None:
        # 1) Token gate (prevents overspend under concurrency)
        async with self._cv:
            while True:
                now = time.monotonic()

                # If we have token info and we've passed reset, clear tokens
                if self._tokens is not None and now >= self._reset_at:
                    # We don't know the new window size until next response.
                    # Treat as "unknown" and allow pacing only until updated.
                    self._tokens = None

                # If tokens unknown, don't block on token gate.
                if self._tokens is None:
                    break

                # If tokens available, reserve one and proceed.
                if self._tokens > 0:
                    self._tokens -= 1
                    break

                # tokens == 0 and reset not reached: wait until reset
                sleep_for = self._reset_at - now
                if sleep_for <= 0:
                    continue
                try:
                    await asyncio.wait_for(self._cv.wait(), timeout=sleep_for)
                except asyncio.TimeoutError:
                    # loop re-check after timeout
                    pass

            pace = self._pace  # snapshot under lock

        # 2) Smooth pacing (spreads requests out)
        await pace.acquire()

    async def update(self, remaining: int, reset_seconds: float) -> None:
        remaining = int(remaining)
        reset_seconds = float(reset_seconds)
        reset_seconds = max(0.001, reset_seconds)

        effective = max(0, remaining - self._safety_margin)
        reset_at = time.monotonic() + reset_seconds

        # Compute smooth pacing: ~1 request per (reset / max(1,effective)) seconds.
        # Clamp to avoid absurd periods.
        if effective <= 0:
            pace = AsyncLimiter(1, min(self._max_pace_period, max(1.0, reset_seconds)))
        else:
            spacing = reset_seconds / max(1, effective)
            spacing = min(self._max_pace_period, max(0.0, spacing))
            pace = AsyncLimiter(1, max(spacing, 0.0))

        async with self._cv:
            self._tokens = effective
            self._reset_at = reset_at
            self._pace = pace
            self._cv.notify_all()
