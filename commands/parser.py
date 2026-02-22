"""
Command definitions, parser, and permission system
"""

import logging
import re
import shlex
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

logger = logging.getLogger("commands")


class CommandTier(Enum):
    CLASSIC = "classic"   # Instant execution
    MAJOR = "major"       # Requires voting
    ADMIN = "admin"       # Admin/mod only


class Permission(Enum):
    VIEWER = 0
    MEMBER = 1
    MOD = 2
    ADMIN = 3


@dataclass
class ParsedCommand:
    name: str
    args: list
    raw: str
    tier: CommandTier = CommandTier.CLASSIC
    required_permission: Permission = Permission.VIEWER


@dataclass
class CommandDef:
    name: str
    tier: CommandTier
    min_args: int = 0
    max_args: int = 0
    description: str = ""
    required_permission: Permission = Permission.VIEWER
    aliases: list = field(default_factory=list)


# ── Command Registry ──────────────────────────────────────────────────────────

COMMAND_DEFS: list[CommandDef] = [
    # VM Control
    CommandDef("startvm", CommandTier.ADMIN, 0, 0, "Start the VM", Permission.ADMIN),
    CommandDef("fullscreen", CommandTier.CLASSIC, 0, 0, "Toggle fullscreen"),

    # Mouse
    CommandDef("move", CommandTier.CLASSIC, 1, 3, "!move dx dy | !move left/right/up/down [steps]"),
    CommandDef("abs", CommandTier.CLASSIC, 2, 2, "!abs x y - Move mouse to absolute position"),
    CommandDef("drag", CommandTier.CLASSIC, 2, 3, "!drag dx dy [button]"),
    CommandDef("click", CommandTier.CLASSIC, 0, 1, "!click [button] - left/right/middle"),
    CommandDef("rclick", CommandTier.CLASSIC, 0, 0, "Right click"),
    CommandDef("scroll", CommandTier.CLASSIC, 1, 1, "!scroll delta"),

    # Keyboard
    CommandDef("type", CommandTier.CLASSIC, 1, 99, "!type text"),
    CommandDef("send", CommandTier.CLASSIC, 1, 99, "!send text (type + Enter)"),
    CommandDef("key", CommandTier.CLASSIC, 1, 2, "!key keyname [duration]"),
    CommandDef("combo", CommandTier.CLASSIC, 1, 1, "!combo ctrl+c"),
    CommandDef("keydown", CommandTier.CLASSIC, 1, 1, "!keydown key"),
    CommandDef("keyup", CommandTier.CLASSIC, 1, 1, "!keyup key"),
    CommandDef("enter", CommandTier.CLASSIC, 0, 0, "Press Enter"),

    # Utility
    CommandDef("wait", CommandTier.CLASSIC, 1, 1, "!wait seconds (max 10)"),
    CommandDef("stats", CommandTier.CLASSIC, 0, 0, "Your stats"),
    CommandDef("leaderboard", CommandTier.CLASSIC, 0, 0, "Top players"),
    CommandDef("uptime", CommandTier.CLASSIC, 0, 0, "Stream uptime"),
    CommandDef("help", CommandTier.CLASSIC, 0, 1, "List commands"),
    CommandDef("vote", CommandTier.CLASSIC, 1, 1, "!vote command - cast vote"),

    # Major (voting required)
    CommandDef("shutdown", CommandTier.MAJOR, 0, 0, "Graceful ACPI shutdown (vote)"),
    CommandDef("forceshutdown", CommandTier.MAJOR, 0, 0, "Hard power off + restart (vote)"),

    # Admin
    CommandDef("reset", CommandTier.ADMIN, 0, 0, "Restart VM", Permission.ADMIN),
    CommandDef("revert", CommandTier.ADMIN, 0, 0, "Restore snapshot", Permission.ADMIN),
    CommandDef("screenshot", CommandTier.ADMIN, 0, 0, "Take screenshot", Permission.MOD),
    CommandDef("ban", CommandTier.ADMIN, 1, 1, "Ban user from commands", Permission.MOD),
    CommandDef("unban", CommandTier.ADMIN, 1, 1, "Unban user", Permission.MOD),
]

# Build lookup
_CMD_MAP: dict[str, CommandDef] = {}
for _cmd in COMMAND_DEFS:
    _CMD_MAP[_cmd.name] = _cmd
    for _alias in _cmd.aliases:
        _CMD_MAP[_alias] = _cmd


def parse_command(text: str) -> Optional[ParsedCommand]:
    """
    Parse a chat message into a command.
    Returns None if the message is not a valid command.
    """
    text = text.strip()
    if not text.startswith("!"):
        return None

    # Split preserving quoted strings
    try:
        parts = shlex.split(text[1:])
    except ValueError:
        # Fallback: simple split
        parts = text[1:].split()

    if not parts:
        return None

    name = parts[0].lower()
    args = parts[1:]

    cmd_def = _CMD_MAP.get(name)
    if cmd_def is None:
        return None

    # Validate arg count (for type/send, we rejoin remaining args)
    if name in ("type", "send") and args:
        # Rejoin all args as one string
        args = [" ".join(parts[1:])]

    if len(args) < cmd_def.min_args:
        return None  # Not enough args — silently ignore

    return ParsedCommand(
        name=name,
        args=args,
        raw=text,
        tier=cmd_def.tier,
        required_permission=cmd_def.required_permission,
    )


def get_help_text(command: Optional[str] = None) -> str:
    if command:
        cmd = _CMD_MAP.get(command.lower())
        if cmd:
            return f"!{cmd.name}: {cmd.description}"
        return f"Unknown command: {command}"

    classic = [f"!{c.name}" for c in COMMAND_DEFS if c.tier == CommandTier.CLASSIC and c.required_permission == Permission.VIEWER]
    major = [f"!{c.name}" for c in COMMAND_DEFS if c.tier == CommandTier.MAJOR]
    return (
        f"🟢 Instant: {', '.join(classic[:12])}... "
        f"| 🟡 Vote needed: {', '.join(major)} "
        f"| Type !help <cmd> for details"
    )
