"""
User database, points, and leaderboard system
Persisted to JSON file
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("user_db")

RANK_THRESHOLDS = [
    (0,    "Lurker"),
    (10,   "Noob"),
    (50,   "Script Kiddie"),
    (150,  "Hacker"),
    (400,  "Sysadmin"),
    (1000, "Arch Wizard"),
    (2500, "BIOS God"),
    (5000, "Root"),
]


def get_rank(points: int) -> str:
    rank = RANK_THRESHOLDS[0][1]
    for threshold, title in RANK_THRESHOLDS:
        if points >= threshold:
            rank = title
    return rank


@dataclass
class UserRecord:
    user_id: str
    display_name: str
    points: int = 0
    commands_executed: int = 0
    votes_cast: int = 0
    votes_won: int = 0
    joined_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    @property
    def rank(self) -> str:
        return get_rank(self.points)


class UserDatabase:
    def __init__(self, data_dir: str = "data"):
        self.path = Path(data_dir) / "users.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._users: dict[str, UserRecord] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path) as f:
                    data = json.load(f)
                for uid, ud in data.items():
                    self._users[uid] = UserRecord(**ud)
                logger.info(f"Loaded {len(self._users)} users")
            except Exception as e:
                logger.error(f"Failed to load users: {e}")

    def save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(
                    {uid: asdict(u) for uid, u in self._users.items()},
                    f, indent=2
                )
        except Exception as e:
            logger.error(f"Failed to save users: {e}")

    def get_or_create(self, user_id: str, display_name: str) -> UserRecord:
        if user_id not in self._users:
            self._users[user_id] = UserRecord(
                user_id=user_id,
                display_name=display_name
            )
        else:
            # Update display name in case it changed
            self._users[user_id].display_name = display_name
        self._users[user_id].last_active = time.time()
        return self._users[user_id]

    def add_points(self, user_id: str, points: int):
        if user_id in self._users:
            self._users[user_id].points += points

    def increment_commands(self, user_id: str):
        if user_id in self._users:
            self._users[user_id].commands_executed += 1

    def increment_votes_cast(self, user_id: str):
        if user_id in self._users:
            self._users[user_id].votes_cast += 1

    def increment_votes_won(self, user_id: str):
        if user_id in self._users:
            self._users[user_id].votes_won += 1

    def get_leaderboard(self, n: int = 10) -> list[UserRecord]:
        sorted_users = sorted(self._users.values(), key=lambda u: u.points, reverse=True)
        return sorted_users[:n]

    def get_stats(self, user_id: str) -> Optional[UserRecord]:
        return self._users.get(user_id)

    @property
    def total_users(self) -> int:
        return len(self._users)
