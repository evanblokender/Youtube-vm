#!/usr/bin/env python3
"""
YouTube Chat Controls VirtualBox VM - Arch Linux Chaos Mode
Main entry point
"""
import signal
import asyncio
import logging
import sys
from core.bot import ArchChaosBot
from utils.config import Config
import signal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("archstream.log"),
    ],
)
logger = logging.getLogger("main")


async def main():
    config = Config.load("config.json")
    bot = ArchChaosBot(config)

    loop = asyncio.get_event_loop()

    def shutdown_handler():
        logger.info("Shutdown signal received...")
        asyncio.create_task(bot.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: asyncio.create_task(shutdown_handler()))

    logger.info("🚀 Starting Arch Linux Chaos Mode...")
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
