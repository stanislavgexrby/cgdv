import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv, find_dotenv

from handlers import register_handlers
from handlers.notifications import wait_all_notifications
from database.database import Database
from config.settings import ADMIN_IDS
from middleware.database import DatabaseMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    await bot.delete_webhook(drop_pending_updates=True)

    # Отправляем сообщение всем админам
    startup_success = []
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🤖 Бот запущен и готов к работе")
            startup_success.append(admin_id)
        except Exception as e:
            logger.warning(
                f"Не удалось отправить сообщение админу {admin_id}: {e} "
                f"(частая причина — админ не нажал Start у бота)"
            )

    if startup_success:
        logger.info(f"Отправлены сообщения о старте админам: {startup_success}")
    else:
        logger.warning("Не удалось отправить сообщения ни одному админу")

async def main():
    load_dotenv(find_dotenv(), override=True)
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не найден. Проверь .env")

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    logger.info("Инициализация базы данных PostgreSQL + Redis...")
    db = Database()
    await db.init()
    logger.info("✅ База данных инициализирована")

    dp.update.middleware(DatabaseMiddleware(db))

    register_handlers(dp)

    await on_startup(bot)
    logger.info("✅ CGDV запущен успешно!")

    try:
        await dp.start_polling(bot)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Остановка поллинга по запросу пользователя/ОС")
    finally:
        await wait_all_notifications()
        await db.close()
        await bot.session.close()
        logger.info("CG TeamUp остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
