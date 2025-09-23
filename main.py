import asyncio
from datetime import datetime, timedelta
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv, find_dotenv

from handlers import register_handlers
from handlers.notifications import wait_all_notifications, notify_monthly_profile_reminder
from database.database import Database
from config.settings import ADMIN_IDS
from middleware.database import DatabaseMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def monthly_reminder_task(bot: Bot, db):
    """Задача для ежемесячных напоминаний"""
    logger.info("Запуск задачи ежемесячных напоминаний")

    try:
        users_for_reminder = await db.get_users_for_monthly_reminder()
        logger.info(f"Найдено {len(users_for_reminder)} пользователей для напоминания")

        for user in users_for_reminder:
            user_id = user['telegram_id']
            game = user['game']

            await notify_monthly_profile_reminder(bot, user_id, game, db)
            await asyncio.sleep(0.1)

        logger.info("Ежемесячные напоминания отправлены")

    except Exception as e:
        logger.error(f"Ошибка отправки ежемесячных напоминаний: {e}")

async def schedule_monthly_reminders(bot: Bot, db):
    """Планировщик ежемесячных задач"""
    while True:
        try:
            now = datetime.now()

            if now.day == 1 and now.hour < 12:
                next_run = now.replace(hour=12, minute=0, second=0, microsecond=0)
            else:
                if now.month == 12:
                    next_run = now.replace(year=now.year + 1, month=1, day=1, hour=12, minute=0, second=0, microsecond=0)
                else:
                    next_run = now.replace(month=now.month + 1, day=1, hour=12, minute=0, second=0, microsecond=0)

            sleep_seconds = (next_run - now).total_seconds()
            sleep_days = sleep_seconds / 86400
            logger.info(f"Следующие напоминания через {sleep_days:.1f} дней - {next_run.strftime('%Y-%m-%d %H:%M')}")

            await asyncio.sleep(sleep_seconds)

            try:
                last_reminder_key = "last_monthly_reminder"
                last_reminder = await db._redis.get(last_reminder_key)
                if last_reminder:
                    last_date = datetime.fromisoformat(last_reminder)
                    if datetime.now() - last_date < timedelta(days=25):
                        logger.info("Напоминания уже отправлялись в этом месяце, пропускаем")
                        continue

                await db._redis.setex(last_reminder_key, 86400 * 35, datetime.now().isoformat())
            except Exception as redis_error:
                logger.warning(f"Redis недоступен для проверки напоминаний: {redis_error}")

            await monthly_reminder_task(bot, db)

        except Exception as e:
            logger.error(f"Ошибка в планировщике напоминаний: {e}")
            await asyncio.sleep(3600)

async def on_startup(bot: Bot):
    await bot.delete_webhook(drop_pending_updates=True)

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

    reminder_task = asyncio.create_task(schedule_monthly_reminders(bot, db))

    try:
        await dp.start_polling(bot)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Остановка поллинга по запросу пользователя/ОС")
        reminder_task.cancel()
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
