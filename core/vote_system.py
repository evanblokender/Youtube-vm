"""
Voting system for Tier 3 (major) commands
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger("vote_system")


@dataclass
class VoteSession:
    commands: dict[str, int] = field(default_factory=dict)  # command -> vote count
    voters: dict[str, str] = field(default_factory=dict)    # user_id -> command voted
    started_at: float = field(default_factory=time.time)
    duration: int = 20
    active: bool = True

    def add_vote(self, user_id: str, command: str) -> bool:
        """Returns True if vote was new/changed."""
        if not self.active:
            return False
        command = command.lower()
        if command not in self.commands:
            self.commands[command] = 0

        if user_id in self.voters:
            old = self.voters[user_id]
            if old == command:
                return False
            self.commands[old] = max(0, self.commands[old] - 1)

        self.commands[command] += 1
        self.voters[user_id] = command
        return True

    def get_winner(self) -> Optional[str]:
        if not self.commands:
            return None
        return max(self.commands, key=lambda c: self.commands[c])

    def get_vote_counts(self) -> dict[str, int]:
        return dict(sorted(self.commands.items(), key=lambda x: x[1], reverse=True))

    @property
    def time_remaining(self) -> float:
        return max(0, self.duration - (time.time() - self.started_at))

    @property
    def total_votes(self) -> int:
        return sum(self.commands.values())


class VoteManager:
    def __init__(self, vote_duration: int = 20):
        self.vote_duration = vote_duration
        self._current_session: Optional[VoteSession] = None
        self._session_lock = asyncio.Lock()
        self._on_result_callbacks: list[Callable] = []

    def on_result(self, callback: Callable):
        self._on_result_callbacks.append(callback)

    async def start_vote(self, initial_command: str, initiator_id: str) -> Optional[VoteSession]:
        async with self._session_lock:
            if self._current_session and self._current_session.active:
                # Vote already in progress — just register this command
                self._current_session.add_vote(initiator_id, initial_command)
                return None  # Signal: joined existing vote

            session = VoteSession(
                commands={initial_command: 1},
                voters={initiator_id: initial_command},
                duration=self.vote_duration,
            )
            self._current_session = session
            asyncio.create_task(self._run_vote(session))
            return session

    async def cast_vote(self, user_id: str, command: str) -> bool:
        async with self._session_lock:
            if not self._current_session or not self._current_session.active:
                return False
            return self._current_session.add_vote(user_id, command)

    async def _run_vote(self, session: VoteSession):
        logger.info(f"Vote started, duration={session.duration}s")
        await asyncio.sleep(session.duration)

        async with self._session_lock:
            session.active = False
            winner = session.get_winner()
            counts = session.get_vote_counts()

        logger.info(f"Vote ended. Winner: {winner}, counts: {counts}")
        voter_ids = [uid for uid, cmd in session.voters.items() if cmd == winner]

        for cb in self._on_result_callbacks:
            try:
                await cb(winner, counts, voter_ids)
            except Exception as e:
                logger.error(f"Vote result callback error: {e}")

    def get_current_session(self) -> Optional[VoteSession]:
        return self._current_session if (self._current_session and self._current_session.active) else None

    def get_vote_status(self) -> Optional[dict]:
        s = self.get_current_session()
        if not s:
            return None
        return {
            "counts": s.get_vote_counts(),
            "time_remaining": s.time_remaining,
            "total_votes": s.total_votes,
        }
