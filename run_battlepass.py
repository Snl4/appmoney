"""Standalone Battle Pass web server (no Telegram bot required)."""

import asyncio
import logging
import os

from aiohttp import web
from dotenv import load_dotenv

from bot.battlepass_api import setup_battlepass_routes
from bot.battlepass_db import init_battlepass_db, seed_demo_if_empty

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("battlepass")


async def main() -> None:
    await init_battlepass_db()
    await seed_demo_if_empty()

    app = web.Application()
    setup_battlepass_routes(app)
    from pathlib import Path

    webapp = Path(__file__).resolve().parent / "webapp"
    app.router.add_static("/static/", webapp, name="static")

    port = int(os.getenv("WEBAPP_PORT", "8765"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Battle Pass: http://127.0.0.1:%s/battlepass", port)
    logger.info("Admin:       http://127.0.0.1:%s/battlepass/admin", port)
    logger.info("Admin key:   %s", os.getenv("BATTLEPASS_ADMIN_KEY", "capy-admin-dev"))
    logger.info("MC API key:  %s", os.getenv("MINECRAFT_API_KEY", "capy-mc-dev"))
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
