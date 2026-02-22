"""
VirtualBox VM Controller
Wraps VBoxManage CLI for VM control
"""

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger("vm_controller")

# VBoxManage scancode mappings for special keys
SCANCODES = {
    "enter": ["1c", "9c"],
    "return": ["1c", "9c"],
    "space": ["39", "b9"],
    "backspace": ["0e", "8e"],
    "tab": ["0f", "8f"],
    "escape": ["01", "81"],
    "esc": ["01", "81"],
    "up": ["e0 48", "e0 c8"],
    "down": ["e0 50", "e0 d0"],
    "left": ["e0 4b", "e0 cb"],
    "right": ["e0 4d", "e0 cd"],
    "ctrl": ["1d", "9d"],
    "shift": ["2a", "aa"],
    "alt": ["38", "b8"],
    "delete": ["e0 53", "e0 d3"],
    "home": ["e0 47", "e0 c7"],
    "end": ["e0 4f", "e0 cf"],
    "pageup": ["e0 49", "e0 c9"],
    "pagedown": ["e0 51", "e0 d1"],
    "f1": ["3b", "bb"],
    "f2": ["3c", "bc"],
    "f3": ["3d", "bd"],
    "f4": ["3e", "be"],
    "f5": ["3f", "bf"],
    "f6": ["40", "c0"],
    "f7": ["41", "c1"],
    "f8": ["42", "c2"],
    "f9": ["43", "c3"],
    "f10": ["44", "c4"],
    "f11": ["57", "d7"],
    "f12": ["58", "d8"],
    "insert": ["e0 52", "e0 d2"],
    "printscreen": ["e0 37", "e0 b7"],
}

# ASCII to scancode map (US keyboard)
ASCII_SCANCODES = {
    'a': '1e', 'b': '30', 'c': '2e', 'd': '20', 'e': '12',
    'f': '21', 'g': '22', 'h': '23', 'i': '17', 'j': '24',
    'k': '25', 'l': '26', 'm': '32', 'n': '31', 'o': '18',
    'p': '19', 'q': '10', 'r': '13', 's': '1f', 't': '14',
    'u': '16', 'v': '2f', 'w': '11', 'x': '2d', 'y': '15',
    'z': '2c',
    '0': '0b', '1': '02', '2': '03', '3': '04', '4': '05',
    '5': '06', '6': '07', '7': '08', '8': '09', '9': '0a',
    ' ': '39',
    '-': '0c', '=': '0d', '[': '1a', ']': '1b', '\\': '2b',
    ';': '27', "'": '28', '`': '29', ',': '33', '.': '34', '/': '35',
}

SHIFT_CHARS = {
    'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e',
    'F': 'f', 'G': 'g', 'H': 'h', 'I': 'i', 'J': 'j',
    'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n', 'O': 'o',
    'P': 'p', 'Q': 'q', 'R': 'r', 'S': 's', 'T': 't',
    'U': 'u', 'V': 'v', 'W': 'w', 'X': 'x', 'Y': 'y',
    'Z': 'z',
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
    '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
    '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\',
    ':': ';', '"': "'", '~': '`', '<': ',', '>': '.', '?': '/',
}


class VMController:
    def __init__(self, vm_name: str, vboxmanage_path: str = "VBoxManage",
                 screenshot_dir: str = "data/screenshots"):
        self.vm_name = vm_name
        self.vboxmanage = vboxmanage_path
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._mouse_x = 0
        self._mouse_y = 0
        self._lock = asyncio.Lock()

    async def _run(self, *args, timeout: int = 10) -> tuple[int, str, str]:
        """Run a VBoxManage command asynchronously."""
        cmd = [self.vboxmanage] + list(args)
        logger.debug(f"Running: {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode, stdout.decode(), stderr.decode()
        except asyncio.TimeoutError:
            logger.error(f"VBoxManage command timed out: {' '.join(args)}")
            return -1, "", "Timeout"
        except Exception as e:
            logger.error(f"VBoxManage error: {e}")
            return -1, "", str(e)

    # ── VM State ──────────────────────────────────────────────────────────────

    async def get_vm_state(self) -> str:
        rc, out, _ = await self._run("showvminfo", self.vm_name, "--machinereadable")
        if rc != 0:
            return "unknown"
        for line in out.splitlines():
            if line.startswith("VMState="):
                return line.split("=")[1].strip('"')
        return "unknown"

    async def is_running(self) -> bool:
        state = await self.get_vm_state()
        return state == "running"

    async def start_vm(self, headless: bool = False) -> bool:
        state = await self.get_vm_state()
        if state == "running":
            return True
        mode = "headless" if headless else "gui"
        rc, _, err = await self._run("startvm", self.vm_name, "--type", mode, timeout=30)
        if rc == 0:
            logger.info(f"VM '{self.vm_name}' started ({mode})")
            await asyncio.sleep(2)
            return True
        logger.error(f"Failed to start VM: {err}")
        return False

    async def shutdown_vm(self, force: bool = False) -> bool:
        method = "poweroff" if force else "acpipowerbutton"
        rc, _, err = await self._run("controlvm", self.vm_name, method)
        if rc == 0:
            logger.info(f"VM shutdown ({method})")
            if not force:
                # Wait for graceful shutdown then restart
                await asyncio.sleep(10)
            return True
        logger.error(f"Shutdown failed: {err}")
        return False

    async def reset_vm(self) -> bool:
        rc, _, _ = await self._run("controlvm", self.vm_name, "reset")
        return rc == 0

    async def restore_snapshot(self, snapshot_name: str) -> bool:
        logger.info(f"Restoring snapshot '{snapshot_name}'...")
        # Must power off first
        state = await self.get_vm_state()
        if state == "running":
            await self._run("controlvm", self.vm_name, "poweroff")
            await asyncio.sleep(3)
        rc, _, err = await self._run("snapshot", self.vm_name, "restore", snapshot_name, timeout=60)
        if rc == 0:
            logger.info("Snapshot restored")
            return True
        logger.error(f"Snapshot restore failed: {err}")
        return False

    async def take_snapshot(self, name: str) -> bool:
        rc, _, _ = await self._run("snapshot", self.vm_name, "take", name, "--live")
        return rc == 0

    # ── Screenshot ────────────────────────────────────────────────────────────

    async def screenshot(self) -> Path | None:
        path = self.screenshot_dir / f"screen_{int(time.time()*1000)}.png"
        rc, _, err = await self._run(
            "controlvm", self.vm_name, "screenshotpng", str(path)
        )
        if rc == 0:
            return path
        logger.debug(f"Screenshot failed: {err}")
        return None

    async def get_latest_screenshot(self) -> Path | None:
        screenshots = sorted(self.screenshot_dir.glob("screen_*.png"))
        return screenshots[-1] if screenshots else None

    # ── Mouse ─────────────────────────────────────────────────────────────────

    async def mouse_move(self, dx: int, dy: int) -> bool:
        async with self._lock:
            self._mouse_x = max(0, min(self._mouse_x + dx, 32767))
            self._mouse_y = max(0, min(self._mouse_y + dy, 32767))
            rc, _, _ = await self._run(
                "controlvm", self.vm_name, "mousemove",
                str(self._mouse_x), str(self._mouse_y)
            )
            return rc == 0

    async def mouse_abs(self, x: int, y: int) -> bool:
        async with self._lock:
            self._mouse_x = max(0, min(x, 32767))
            self._mouse_y = max(0, min(y, 32767))
            rc, _, _ = await self._run(
                "controlvm", self.vm_name, "mousemove",
                str(self._mouse_x), str(self._mouse_y)
            )
            return rc == 0

    async def mouse_click(self, button: str = "left") -> bool:
        btn_map = {"left": "MouseButtonLeft", "right": "MouseButtonRight", "middle": "MouseButtonMiddle"}
        btn = btn_map.get(button, "MouseButtonLeft")
        rc, _, _ = await self._run("controlvm", self.vm_name, "mousecapture", btn)
        await asyncio.sleep(0.05)
        await self._run("controlvm", self.vm_name, "mouserelease", btn)
        return rc == 0

    async def mouse_click_v2(self, button: str = "left") -> bool:
        """Click using putmouseevent (more reliable)."""
        btn_code = {"left": 1, "right": 2, "middle": 4}.get(button, 1)
        # Press
        rc, _, _ = await self._run(
            "controlvm", self.vm_name, "putmouseevent",
            "0", "0", "0", "0", str(btn_code)
        )
        await asyncio.sleep(0.05)
        # Release
        await self._run("controlvm", self.vm_name, "putmouseevent", "0", "0", "0", "0", "0")
        return rc == 0

    async def mouse_scroll(self, delta: int) -> bool:
        rc, _, _ = await self._run(
            "controlvm", self.vm_name, "putmouseevent",
            "0", "0", str(delta), "0", "0"
        )
        return rc == 0

    async def mouse_drag(self, dx: int, dy: int, button: str = "left") -> bool:
        btn_code = {"left": 1, "right": 2, "middle": 4}.get(button, 1)
        # Press button
        await self._run("controlvm", self.vm_name, "putmouseevent",
                        "0", "0", "0", "0", str(btn_code))
        # Move in steps
        steps = max(abs(dx), abs(dy), 1)
        step_x = dx // steps
        step_y = dy // steps
        for _ in range(steps):
            await self._run("controlvm", self.vm_name, "putmouseevent",
                            str(step_x), str(step_y), "0", "0", str(btn_code))
            await asyncio.sleep(0.01)
        # Release
        await self._run("controlvm", self.vm_name, "putmouseevent", "0", "0", "0", "0", "0")
        return True

    # ── Keyboard ──────────────────────────────────────────────────────────────

    async def key_press(self, key: str, duration: float = 0.1) -> bool:
        """Press and release a key by name."""
        key = key.lower()
        if key not in SCANCODES:
            logger.warning(f"Unknown key: {key}")
            return False
        press, release = SCANCODES[key]
        rc, _, _ = await self._run("controlvm", self.vm_name, "keyboardputscancode", press)
        await asyncio.sleep(duration)
        await self._run("controlvm", self.vm_name, "keyboardputscancode", release)
        return rc == 0

    async def key_down(self, key: str) -> bool:
        key = key.lower()
        if key not in SCANCODES:
            return False
        press, _ = SCANCODES[key]
        rc, _, _ = await self._run("controlvm", self.vm_name, "keyboardputscancode", press)
        return rc == 0

    async def key_up(self, key: str) -> bool:
        key = key.lower()
        if key not in SCANCODES:
            return False
        _, release = SCANCODES[key]
        rc, _, _ = await self._run("controlvm", self.vm_name, "keyboardputscancode", release)
        return rc == 0

    async def key_combo(self, combo: str) -> bool:
        """Execute key combo like ctrl+c, ctrl+alt+t."""
        keys = combo.lower().split("+")
        # Press all
        for k in keys:
            await self.key_down(k)
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.1)
        # Release all in reverse
        for k in reversed(keys):
            await self.key_up(k)
            await asyncio.sleep(0.05)
        return True

    async def type_text(self, text: str) -> bool:
        """Type text using keyboardputstring (handles most ASCII)."""
        if not text:
            return False
        rc, _, err = await self._run("controlvm", self.vm_name, "keyboardputstring", text)
        if rc != 0:
            logger.warning(f"keyboardputstring failed ({err}), using scancode fallback")
            return await self._type_scancodes(text)
        return True

    async def _type_scancodes(self, text: str) -> bool:
        """Fallback: type character by character using scancodes."""
        for char in text:
            if char in SHIFT_CHARS:
                base = SHIFT_CHARS[char]
                if base not in ASCII_SCANCODES:
                    continue
                sc = ASCII_SCANCODES[base]
                rel_sc = hex(int(sc, 16) + 0x80)[2:].zfill(2)
                shift_press, shift_release = SCANCODES["shift"]
                await self._run("controlvm", self.vm_name, "keyboardputscancode",
                                shift_press, sc, rel_sc, shift_release)
            elif char.lower() in ASCII_SCANCODES:
                sc = ASCII_SCANCODES[char.lower()]
                rel_sc = hex(int(sc, 16) + 0x80)[2:].zfill(2)
                await self._run("controlvm", self.vm_name, "keyboardputscancode", sc, rel_sc)
            await asyncio.sleep(0.02)
        return True

    async def send_text(self, text: str) -> bool:
        """Type text then press Enter."""
        ok = await self.type_text(text)
        if ok:
            await asyncio.sleep(0.1)
            await self.key_press("enter")
        return ok

    async def toggle_fullscreen(self) -> bool:
        rc, _, _ = await self._run("controlvm", self.vm_name, "setvideomodehint",
                                   "1920", "1080", "32")
        return rc == 0
