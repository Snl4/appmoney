import asyncio
import logging
import os
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo
from dotenv import load_dotenv

from bot.database import init_db
from bot.handlers import router
from bot.webapp_api import create_app

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("budget-bot")


async def run_webapp_server(bot_token: str) -> None:
    port = int(os.getenv("WEBAPP_PORT", "8080"))
    app = create_app(bot_token)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Web App API на порту %s", port)


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не задано")
        sys.exit(1)

    await init_db()
    await run_webapp_server(token)

    webapp_url = os.getenv("WEBAPP_URL", "")
    if webapp_url.startswith("https://"):
        logger.info("Mini App: %s", webapp_url)
    else:
        logger.warning("WEBAPP_URL не задано — Mini App кнопка прихована. Додай HTTPS домен в .env")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    if webapp_url.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="📱 Бюджет", web_app=WebAppInfo(url=webapp_url)),
        )

    logger.info("Бот запущено (polling)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
