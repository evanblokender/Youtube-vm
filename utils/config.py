"""
Configuration loader and validator
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # YouTube API
    youtube_api_key: str = ""
    youtube_channel_id: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_refresh_token: str = ""
    youtube_live_chat_id: str = ""  # Auto-detected or manual override

    # VirtualBox
    vm_name: str = "ArchLinuxChaos"
    vboxmanage_path: str = "VBoxManage"
    snapshot_name: str = "SafeBase"
    screenshot_interval: float = 1.0  # seconds between screenshots

    # Command system
    vote_duration: int = 20           # seconds for voting window
    command_cooldown: float = 0.5     # seconds between any commands
    user_cooldown: float = 3.0        # seconds per user between commands
    max_wait_seconds: int = 10        # max !wait value
    queue_max_size: int = 50          # max commands in execution queue
    type_max_length: int = 100        # max characters for !type

    # Mouse limits
    mouse_max_delta: int = 300        # max pixels per move
    mouse_abs_x_max: int = 1920
    mouse_abs_y_max: int = 1080

    # Gamification
    points_per_command: int = 1
    points_per_vote_win: int = 5
    leaderboard_size: int = 10

    # Admin
    admin_user_ids: list = field(default_factory=list)
    mod_user_ids: list = field(default_factory=list)

    # Stream
    stream_title: str = "YouTube Chat Controls Arch Linux Install!"
    auto_restart_on_failure: bool = True
    data_dir: str = "data"

    @classmethod
    def load(cls, path: str) -> "Config":
        if not os.path.exists(path):
            # Write default config
            cfg = cls()
            with open(path, "w") as f:
                json.dump(cfg.__dict__, f, indent=2)
            print(f"Created default config at {path}. Please fill in API credentials.")
            return cfg

        with open(path) as f:
            data = json.load(f)

        cfg = cls()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    def validate(self):
        errors = []
        if not self.youtube_api_key:
            errors.append("youtube_api_key is required")
        if not self.youtube_channel_id:
            errors.append("youtube_channel_id is required")
        if not self.vm_name:
            errors.append("vm_name is required")
        if errors:
            raise ValueError("Config errors:\n" + "\n".join(f"  - {e}" for e in errors))
