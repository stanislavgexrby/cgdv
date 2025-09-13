import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv, find_dotenv

from handlers import register_handlers
from database.database import Database
from config.settings import ADMIN_ID
from middleware.database import DatabaseMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    # сбрасываем возможный старый вебхук
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await bot.send_message(ADMIN_ID, "🚀 Бот запущен и готов к работе")
        logger.info("Отправлено сообщение админу о старте")
    except Exception as e:
        logger.warning(
            f"Не удалось отправить сообщение админу: {e} "
            f"(частая причина — админ не нажал Start у бота)"
        )

async def main():
    # 1) env
    load_dotenv(find_dotenv())
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не найден. Проверь .env")

    # 2) bot/dispatcher
    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    # 3) db
    logger.info("🔄 Инициализация базы данных PostgreSQL + Redis...")
    db = Database()
    await db.init()
    logger.info("✅ База данных инициализирована")

    # 4) middleware
    dp.update.middleware(DatabaseMiddleware(db))

    # 5) handlers
    register_handlers(dp)

    # 6) старт и поллинг
    await on_startup(bot)
    logger.info("✅ CGDV запущен успешно!")

    try:
        await dp.start_polling(bot)  # обычная остановка даст CancelledError внутри
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("🛑 Остановка поллинга по запросу пользователя/ОС")
    finally:
        await db.close()
        await bot.session.close()
        logger.info("👋 CGDV остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # чтобы Windows/IDE не печатал лишний трейс при Ctrl+C
        pass
