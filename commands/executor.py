"""
Command executor - maps parsed commands to VM actions
"""

import asyncio
import logging
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.vm_controller import VMController

from commands.parser import ParsedCommand, CommandTier

logger = logging.getLogger("executor")

DIRECTION_MAP = {
    "left": (-100, 0),
    "right": (100, 0),
    "up": (0, -100),
    "down": (0, 100),
}


class CommandResult:
    def __init__(self, success: bool, message: str = "", public: bool = True):
        self.success = success
        self.message = message
        self.public = public  # Whether to announce in chat

    @classmethod
    def ok(cls, msg: str = "", public: bool = True):
        return cls(True, msg, public)

    @classmethod
    def fail(cls, msg: str = ""):
        return cls(False, msg, True)


class CommandExecutor:
    def __init__(self, vm: "VMController", config):
        self.vm = vm
        self.config = config
        self._start_time = time.time()

    async def execute(self, cmd: ParsedCommand, user_display: str) -> CommandResult:
        """Route command to appropriate handler."""
        name = cmd.name
        args = cmd.args

        try:
            if name == "startvm":
                return await self._startvm()
            elif name == "fullscreen":
                return await self._fullscreen()
            elif name == "move":
                return await self._move(args)
            elif name == "abs":
                return await self._abs(args)
            elif name == "drag":
                return await self._drag(args)
            elif name == "click":
                return await self._click(args)
            elif name == "rclick":
                return await self._rclick()
            elif name == "scroll":
                return await self._scroll(args)
            elif name == "type":
                return await self._type(args)
            elif name == "send":
                return await self._send(args)
            elif name == "key":
                return await self._key(args)
            elif name == "combo":
                return await self._combo(args)
            elif name == "keydown":
                return await self._keydown(args)
            elif name == "keyup":
                return await self._keyup(args)
            elif name == "enter":
                return await self._enter()
            elif name == "wait":
                return await self._wait(args)
            elif name == "reset":
                return await self._reset()
            elif name == "revert":
                return await self._revert()
            elif name == "screenshot":
                return await self._screenshot()
            elif name == "shutdown":
                return CommandResult.fail("shutdown requires a vote")
            elif name == "forceshutdown":
                return CommandResult.fail("forceshutdown requires a vote")
            else:
                return CommandResult.fail(f"Unknown command: {name}")
        except Exception as e:
            logger.error(f"Executor error for {name}: {e}", exc_info=True)
            return CommandResult.fail(f"Error executing !{name}")

    # ── VM ────────────────────────────────────────────────────────────────────

    async def _startvm(self) -> CommandResult:
        ok = await self.vm.start_vm(headless=True)
        return CommandResult.ok("✅ VM started!") if ok else CommandResult.fail("❌ VM failed to start")

    async def _fullscreen(self) -> CommandResult:
        await self.vm.toggle_fullscreen()
        return CommandResult.ok("🖥️ Fullscreen toggled", public=False)

    # ── Mouse ─────────────────────────────────────────────────────────────────

    async def _move(self, args) -> CommandResult:
        if not args:
            return CommandResult.fail("Usage: !move dx dy | !move left/right/up/down")

        direction = args[0].lower()
        if direction in DIRECTION_MAP:
            dx, dy = DIRECTION_MAP[direction]
            steps = int(args[1]) if len(args) > 1 and args[1].lstrip("-").isdigit() else 1
            steps = max(1, min(steps, 10))
            dx *= steps
            dy *= steps
        else:
            if len(args) < 2:
                return CommandResult.fail("Usage: !move dx dy")
            try:
                dx = int(float(args[0]))
                dy = int(float(args[1]))
            except ValueError:
                return CommandResult.fail("Invalid coordinates")

        # Clamp
        max_d = self.config.mouse_max_delta
        dx = max(-max_d, min(dx, max_d))
        dy = max(-max_d, min(dy, max_d))

        await self.vm.mouse_move(dx, dy)
        return CommandResult.ok(f"🖱️ Moved ({dx},{dy})", public=False)

    async def _abs(self, args) -> CommandResult:
        try:
            x = int(float(args[0]))
            y = int(float(args[1]))
        except (ValueError, IndexError):
            return CommandResult.fail("Usage: !abs x y")
        x = max(0, min(x, self.config.mouse_abs_x_max))
        y = max(0, min(y, self.config.mouse_abs_y_max))
        await self.vm.mouse_abs(x, y)
        return CommandResult.ok(f"🖱️ Moved to ({x},{y})", public=False)

    async def _drag(self, args) -> CommandResult:
        try:
            dx = int(float(args[0]))
            dy = int(float(args[1]))
        except (ValueError, IndexError):
            return CommandResult.fail("Usage: !drag dx dy [button]")
        button = args[2].lower() if len(args) > 2 else "left"
        if button not in ("left", "right", "middle"):
            button = "left"
        max_d = self.config.mouse_max_delta
        dx = max(-max_d, min(dx, max_d))
        dy = max(-max_d, min(dy, max_d))
        await self.vm.mouse_drag(dx, dy, button)
        return CommandResult.ok(f"🖱️ Dragged ({dx},{dy})", public=False)

    async def _click(self, args) -> CommandResult:
        button = args[0].lower() if args else "left"
        if button not in ("left", "right", "middle"):
            button = "left"
        await self.vm.mouse_click_v2(button)
        return CommandResult.ok(f"🖱️ {button.capitalize()} click", public=False)

    async def _rclick(self) -> CommandResult:
        await self.vm.mouse_click_v2("right")
        return CommandResult.ok("🖱️ Right click", public=False)

    async def _scroll(self, args) -> CommandResult:
        try:
            delta = int(float(args[0]))
        except (ValueError, IndexError):
            return CommandResult.fail("Usage: !scroll delta")
        delta = max(-10, min(delta, 10))
        await self.vm.mouse_scroll(delta)
        return CommandResult.ok(f"🖱️ Scrolled {delta}", public=False)

    # ── Keyboard ──────────────────────────────────────────────────────────────

    async def _type(self, args) -> CommandResult:
        if not args:
            return CommandResult.fail("Usage: !type text")
        text = args[0][:self.config.type_max_length]
        await self.vm.type_text(text)
        return CommandResult.ok(f"⌨️ Typed: {text[:30]}{'...' if len(text) > 30 else ''}")

    async def _send(self, args) -> CommandResult:
        if not args:
            return CommandResult.fail("Usage: !send text")
        text = args[0][:self.config.type_max_length]
        await self.vm.send_text(text)
        return CommandResult.ok(f"⌨️ Sent: {text[:30]}{'...' if len(text) > 30 else ''}")

    async def _key(self, args) -> CommandResult:
        key = args[0].lower()
        duration = 0.1
        if len(args) > 1:
            try:
                duration = max(0.05, min(float(args[1]), 2.0))
            except ValueError:
                pass
        ok = await self.vm.key_press(key, duration)
        if not ok:
            return CommandResult.fail(f"Unknown key: {key}")
        return CommandResult.ok(f"⌨️ Key: {key}", public=False)

    async def _combo(self, args) -> CommandResult:
        combo = args[0].lower()
        # Validate - only allow simple combos
        parts = combo.split("+")
        if len(parts) > 4:
            return CommandResult.fail("Too many keys in combo")
        await self.vm.key_combo(combo)
        return CommandResult.ok(f"⌨️ Combo: {combo}")

    async def _keydown(self, args) -> CommandResult:
        key = args[0].lower()
        ok = await self.vm.key_down(key)
        return CommandResult.ok(f"⌨️ KeyDown: {key}", public=False) if ok else CommandResult.fail(f"Unknown key: {key}")

    async def _keyup(self, args) -> CommandResult:
        key = args[0].lower()
        ok = await self.vm.key_up(key)
        return CommandResult.ok(f"⌨️ KeyUp: {key}", public=False) if ok else CommandResult.fail(f"Unknown key: {key}")

    async def _enter(self) -> CommandResult:
        await self.vm.key_press("enter")
        return CommandResult.ok("⌨️ Enter", public=False)

    # ── Utility ───────────────────────────────────────────────────────────────

    async def _wait(self, args) -> CommandResult:
        try:
            secs = float(args[0])
        except (ValueError, IndexError):
            return CommandResult.fail("Usage: !wait seconds")
        secs = max(0, min(secs, self.config.max_wait_seconds))
        await asyncio.sleep(secs)
        return CommandResult.ok(f"⏱️ Waited {secs}s", public=False)

    async def _reset(self) -> CommandResult:
        ok = await self.vm.reset_vm()
        return CommandResult.ok("🔄 VM reset!") if ok else CommandResult.fail("❌ Reset failed")

    async def _revert(self) -> CommandResult:
        ok = await self.vm.restore_snapshot(self.config.snapshot_name)
        if ok:
            await asyncio.sleep(3)
            await self.vm.start_vm(headless=True)
        return CommandResult.ok("⏮️ Snapshot restored!") if ok else CommandResult.fail("❌ Revert failed")

    async def _screenshot(self) -> CommandResult:
        path = await self.vm.screenshot()
        return CommandResult.ok(f"📸 Screenshot saved: {path}") if path else CommandResult.fail("Screenshot failed")

    # ── Shutdown (called by vote system) ──────────────────────────────────────

    async def execute_shutdown(self, force: bool = False) -> CommandResult:
        ok = await self.vm.shutdown_vm(force=force)
        if ok:
            await asyncio.sleep(force and 2 or 12)
            await self.vm.start_vm(headless=True)
            return CommandResult.ok("🔌 VM shut down and restarted!")
        return CommandResult.fail("❌ Shutdown failed")
