"""
Main bot orchestrator - ties together all systems.

ALL bot responses now go to the OBS overlay (zero YouTube send quota used).
Incoming messages are still read via the YouTube polling API (read-only, low cost).
"""

import asyncio
import logging
import time
from typing import Optional

from api.youtube_chat import YouTubeChatClient, ChatMessage
from commands.executor import CommandExecutor, CommandResult
from commands.parser import (
    parse_command, ParsedCommand, CommandTier, Permission, get_help_text
)
from core.rate_limiter import RateLimiter, ExecutionQueue
from core.user_db import UserDatabase
from core.vm_controller import VMController
from core.vote_system import VoteManager
from obs_overlay import OverlayServer

logger = logging.getLogger("bot")


class ArchChaosBot:
    def __init__(self, config):
        self.config = config
        self._running = False
        self._start_time = time.time()

        self.vm = VMController(
            vm_name=config.vm_name,
            vboxmanage_path=config.vboxmanage_path,
            screenshot_dir=f"{config.data_dir}/screenshots",
        )
        self.chat = YouTubeChatClient(config)
        self.users = UserDatabase(config.data_dir)
        self.rate_limiter = RateLimiter(
            user_cooldown=config.user_cooldown,
            global_cooldown=config.command_cooldown,
        )
        self.vote_manager = VoteManager(vote_duration=config.vote_duration)
        self.executor = CommandExecutor(self.vm, config)
        self.queue = ExecutionQueue(max_size=config.queue_max_size)

        overlay_port = getattr(config, "overlay_port", 7373)
        self.overlay = OverlayServer(host="127.0.0.1", port=overlay_port)

        self.rate_limiter.set_command_cooldown("leaderboard", 15)
        self.rate_limiter.set_command_cooldown("stats", 10)
        self.rate_limiter.set_command_cooldown("uptime", 10)

        self._banned: set[str] = set()
        self.vote_manager.on_result(self._on_vote_result)

    async def start(self):
        self._running = True
        config = self.config

        try:
            config.validate()
        except ValueError as e:
            logger.error(str(e))
            return

        logger.info("Starting OBS overlay server...")
        await self.overlay.start()

        logger.info("Connecting to YouTube Live Chat (read-only)...")
        await self.chat.start()

        logger.info("Checking VM state...")
        if not await self.vm.is_running():
            logger.info("Starting VM...")
            await self.vm.start_vm(headless=True)

        self._announce(
            "🤖 Arch Linux Chaos Mode is LIVE! "
            "Type !help for commands. Let's install Arch together... or break it trying! 🐧"
        )

        await asyncio.gather(
            self._chat_loop(),
            self._execution_loop(),
            self._screenshot_loop(),
            self._save_loop(),
            self._vote_ticker_loop(),
        )

    async def shutdown(self):
        self._running = False
        self.users.save()
        self._announce("🤖 Bot shutting down. Thanks for playing! 👋")
        await self.chat.close()
        await self.overlay.stop()

    # ── Overlay helpers ───────────────────────────────────────────────────────

    def _announce(self, text: str):
        self.overlay.add_bot_message(text)
        logger.info(f"[OVERLAY] {text}")

    def _announce_for(self, user: str, text: str):
        self.overlay.add_bot_message(f"@{user} {text}")
        logger.info(f"[OVERLAY → {user}] {text}")

    # ── Main Chat Loop ────────────────────────────────────────────────────────

    async def _chat_loop(self):
        logger.info("Chat loop started")
        async for message in self.chat.message_stream():
            if not self._running:
                break
            try:
                await self._process_message(message)
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

    async def _process_message(self, msg: ChatMessage):
        text = msg.text.strip()

        badge = "owner" if msg.is_owner else "mod" if msg.is_moderator else "member" if msg.is_member else ""
        self.overlay.add_chat_message(msg.author_display, text, badge=badge)

        if not text.startswith("!"):
            return

        user = self.users.get_or_create(msg.author_id, msg.author_display)

        if msg.author_id in self._banned:
            return

        perm = Permission.VIEWER
        if msg.author_id in self.config.admin_user_ids or msg.is_owner:
            perm = Permission.ADMIN
        elif msg.author_id in self.config.mod_user_ids or msg.is_moderator:
            perm = Permission.MOD
        elif msg.is_member:
            perm = Permission.MEMBER

        cmd = parse_command(text)
        if cmd is None:
            return

        if cmd.required_permission.value > perm.value:
            self._announce_for(msg.author_display, f"❌ No permission for !{cmd.name}")
            return

        if cmd.name == "help":
            arg = cmd.args[0] if cmd.args else None
            self._announce(get_help_text(arg))
            return

        if cmd.name == "stats":
            self._announce(self._format_stats(user))
            return

        if cmd.name == "leaderboard":
            self._announce(self._format_leaderboard())
            return

        if cmd.name == "uptime":
            up = int(time.time() - self._start_time)
            h, m, s = up // 3600, (up % 3600) // 60, up % 60
            self._announce(f"⏱️ Stream uptime: {h:02d}:{m:02d}:{s:02d}")
            return

        if cmd.name == "vote":
            await self._handle_vote_cast(msg, cmd, perm)
            return

        if cmd.name in ("ban", "unban"):
            await self._handle_moderation(msg, cmd, perm)
            return

        allowed, reason = self.rate_limiter.check(msg.author_id, cmd.name)
        if not allowed:
            if cmd.tier == CommandTier.CLASSIC and cmd.name in (
                "move", "click", "rclick", "type", "send", "key", "enter", "scroll", "abs", "drag"
            ):
                return
            self._announce_for(msg.author_display, f"⏳ {reason}")
            return

        if cmd.tier == CommandTier.MAJOR:
            await self._handle_major_command(msg, cmd)
            return

        self.rate_limiter.record(msg.author_id, cmd.name)
        self.users.increment_commands(msg.author_id)
        self.users.add_points(msg.author_id, self.config.points_per_command)

        args_str = " ".join(str(a) for a in cmd.args) if cmd.args else ""
        self.overlay.set_active_command(msg.author_display, cmd.name, args_str)

        enqueued = await self.queue.put((cmd, msg.author_display, msg.author_id))
        if not enqueued:
            self._announce_for(msg.author_display, "⚠️ Queue full, try again later")
            self.overlay.clear_active_command()

    # ── Major Commands & Voting ───────────────────────────────────────────────

    async def _handle_major_command(self, msg: ChatMessage, cmd: ParsedCommand):
        session = await self.vote_manager.start_vote(cmd.name, msg.author_id)
        self.users.increment_votes_cast(msg.author_id)

        if session is not None:
            dur = self.config.vote_duration
            self._announce(
                f"🗳️ VOTE STARTED! Type !vote shutdown or !vote forceshutdown. "
                f"You have {dur}s! Current: !{cmd.name} (1 vote)"
            )
        else:
            status = self.vote_manager.get_vote_status()
            if status:
                counts = " | ".join(f"!{k}: {v}" for k, v in status["counts"].items())
                self._announce_for(
                    msg.author_display,
                    f"voted !{cmd.name}. [{counts}] - {status['time_remaining']:.0f}s left"
                )

    async def _handle_vote_cast(self, msg: ChatMessage, cmd: ParsedCommand, perm: Permission):
        if not cmd.args:
            self._announce_for(msg.author_display, "Usage: !vote shutdown | !vote forceshutdown")
            return

        target = cmd.args[0].lower().lstrip("!")
        if target not in ("shutdown", "forceshutdown"):
            self._announce_for(msg.author_display, "Vote options: shutdown, forceshutdown")
            return

        ok = await self.vote_manager.cast_vote(msg.author_id, target)
        if ok:
            self.users.increment_votes_cast(msg.author_id)
            status = self.vote_manager.get_vote_status()
            if status:
                counts = " | ".join(f"!{k}: {v}" for k, v in status["counts"].items())
                self._announce_for(msg.author_display, f"✅ Voted !{target}. [{counts}]")
        else:
            self._announce_for(
                msg.author_display,
                "❌ No active vote right now. Trigger !shutdown or !forceshutdown first."
            )

    async def _on_vote_result(self, winner: str, counts: dict, voter_ids: list):
        self.overlay.clear_vote()
        if not winner:
            self._announce("🗳️ Vote ended with no winner.")
            return

        counts_str = " | ".join(f"!{k}: {v}" for k, v in counts.items())
        self._announce(f"🗳️ Vote ended! [{counts_str}] → Winner: !{winner} 🎉")

        for uid in voter_ids:
            self.users.add_points(uid, self.config.points_per_vote_win)
            self.users.increment_votes_won(uid)

        await asyncio.sleep(1)
        if winner == "shutdown":
            result = await self.executor.execute_shutdown(force=False)
        elif winner == "forceshutdown":
            result = await self.executor.execute_shutdown(force=True)
        else:
            return

        if result.message:
            self._announce(result.message)

    # ── Execution Loop ────────────────────────────────────────────────────────

    async def _execution_loop(self):
        logger.info("Execution loop started")
        while self._running:
            try:
                cmd, user_display, user_id = await asyncio.wait_for(
                    self.queue.get(), timeout=1.0
                )
                self.queue.task_done()

                if cmd.name not in ("startvm", "stats", "leaderboard", "uptime", "help", "screenshot"):
                    if not await self.vm.is_running():
                        self._announce_for(user_display, "❌ VM is not running! Try !startvm")
                        self.overlay.clear_active_command()
                        continue

                result = await self.executor.execute(cmd, user_display)

                if result.message and result.public:
                    self._announce_for(user_display, result.message)
                elif not result.success and result.message:
                    self._announce_for(user_display, result.message)

                self.overlay.clear_active_command()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Execution loop error: {e}", exc_info=True)

    # ── Vote Ticker Loop ──────────────────────────────────────────────────────

    async def _vote_ticker_loop(self):
        while self._running:
            status = self.vote_manager.get_vote_status()
            if status:
                self.overlay.set_vote_status(
                    options=status["counts"],
                    time_remaining=status["time_remaining"],
                )
            else:
                self.overlay.clear_vote()
            await asyncio.sleep(1.0)

    # ── Screenshot Loop ───────────────────────────────────────────────────────

    async def _screenshot_loop(self):
        while self._running:
            try:
                if await self.vm.is_running():
                    await self.vm.screenshot()
            except Exception as e:
                logger.debug(f"Screenshot loop error: {e}")
            await asyncio.sleep(self.config.screenshot_interval)

    # ── Save Loop ─────────────────────────────────────────────────────────────

    async def _save_loop(self):
        while self._running:
            await asyncio.sleep(60)
            self.users.save()
            logger.debug("User data saved")

    # ── Moderation ────────────────────────────────────────────────────────────

    async def _handle_moderation(self, msg: ChatMessage, cmd: ParsedCommand, perm: Permission):
        if perm.value < Permission.MOD.value:
            return
        if not cmd.args:
            return
        target_name = cmd.args[0].lstrip("@")

        if cmd.name == "ban":
            self._banned.add(target_name)
            self._announce(f"🚫 {target_name} has been banned from commands")
        elif cmd.name == "unban":
            self._banned.discard(target_name)
            self._announce(f"✅ {target_name} has been unbanned")

    # ── Formatting ────────────────────────────────────────────────────────────

    def _format_stats(self, user) -> str:
        return (
            f"📊 @{user.display_name} | Rank: {user.rank} | "
            f"Points: {user.points} | Commands: {user.commands_executed} | "
            f"Votes: {user.votes_cast} (won: {user.votes_won})"
        )

    def _format_leaderboard(self) -> str:
        top = self.users.get_leaderboard(self.config.leaderboard_size)
        if not top:
            return "🏆 Leaderboard is empty!"
        entries = " | ".join(
            f"#{i+1} {u.display_name}: {u.points}pts"
            for i, u in enumerate(top[:5])
        )
        return f"🏆 Top Players: {entries}"
