"""
Rate limiting and cooldown tracking
"""

import time
from collections import defaultdict
from typing import Optional


class RateLimiter:
    """Per-user cooldown + global command rate limit."""

    def __init__(self, user_cooldown: float = 3.0, global_cooldown: float = 0.5):
        self.user_cooldown = user_cooldown
        self.global_cooldown = global_cooldown
        self._user_last: dict[str, float] = defaultdict(float)
        self._global_last: float = 0.0
        self._command_cooldowns: dict[str, float] = {}     # command -> last execution time
        self._command_intervals: dict[str, float] = {}     # command -> min interval

    def set_command_cooldown(self, command: str, interval: float):
        self._command_intervals[command] = interval

    def check(self, user_id: str, command: str = "") -> tuple[bool, str]:
        """
        Returns (allowed, reason_if_denied)
        """
        now = time.time()

        # Global rate limit
        elapsed_global = now - self._global_last
        if elapsed_global < self.global_cooldown:
            wait = self.global_cooldown - elapsed_global
            return False, f"Server busy, wait {wait:.1f}s"

        # Per-user cooldown
        elapsed_user = now - self._user_last[user_id]
        if elapsed_user < self.user_cooldown:
            wait = self.user_cooldown - elapsed_user
            return False, f"Cooldown: {wait:.1f}s remaining"

        # Per-command cooldown
        if command and command in self._command_intervals:
            elapsed_cmd = now - self._command_cooldowns.get(command, 0)
            if elapsed_cmd < self._command_intervals[command]:
                wait = self._command_intervals[command] - elapsed_cmd
                return False, f"!{command} on cooldown: {wait:.0f}s"

        return True, ""

    def record(self, user_id: str, command: str = ""):
        now = time.time()
        self._user_last[user_id] = now
        self._global_last = now
        if command:
            self._command_cooldowns[command] = now

    def get_user_wait(self, user_id: str) -> float:
        return max(0, self.user_cooldown - (time.time() - self._user_last[user_id]))


class ExecutionQueue:
    """Async execution queue to prevent command flooding."""

    def __init__(self, max_size: int = 50):
        import asyncio
        self._queue = asyncio.Queue(maxsize=max_size)
        self.dropped = 0

    async def put(self, item) -> bool:
        try:
            self._queue.put_nowait(item)
            return True
        except Exception:
            self.dropped += 1
            return False

    async def get(self):
        return await self._queue.get()

    def task_done(self):
        self._queue.task_done()

    @property
    def size(self) -> int:
        return self._queue.qsize()
