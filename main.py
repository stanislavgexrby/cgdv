import asyncio
import logging
import logging.handlers
from datetime import datetime, timedelta
import os
from pathlib import Path
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv, find_dotenv

from handlers import register_handlers
from handlers.notifications import wait_all_notifications, notify_monthly_profile_reminder
from database.database import Database
from config.settings import ADMIN_IDS
from middleware.database import DatabaseMiddleware
from middleware.state_recovery import StateRecoveryMiddleware

# В main.py функция setup_logging() - ВАРИАНТЫ НАСТРОЙКИ

def setup_logging():
    """Настройка логирования в файлы с ротацией"""
    
    # Создаем папку logs если её нет
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    
    # Формат логов
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # === ВАРИАНТ 1: ПОЛНОСТЬЮ БЕЗ КОНСОЛИ ===
    # (просто НЕ добавляем console_handler)
    
    # === ВАРИАНТ 2: КОНСОЛЬ ТОЛЬКО ДЛЯ КРИТИЧНОГО ===
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)  # Только ошибки в консоль
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # === ВАРИАНТ 3: НАСТРАИВАЕМО ЧЕРЕЗ .env ===
    console_enabled = os.getenv('CONSOLE_LOGS', 'false').lower() == 'true'
    if console_enabled:
        console_handler = logging.StreamHandler()
        console_level = os.getenv('CONSOLE_LEVEL', 'INFO').upper()
        console_handler.setLevel(getattr(logging, console_level, logging.INFO))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # === ФАЙЛОВЫЕ ОБРАБОТЧИКИ (всегда включены) ===
    
    # Основной лог файл
    main_handler = logging.handlers.RotatingFileHandler(
        filename=logs_dir / "bot.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    main_handler.setLevel(logging.INFO)
    main_handler.setFormatter(formatter)
    root_logger.addHandler(main_handler)
    
    # Ошибки в отдельный файл
    error_handler = logging.handlers.RotatingFileHandler(
        filename=logs_dir / "errors.log", 
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # DEBUG логи (если включены)
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
    if debug_mode:
        daily_handler = logging.handlers.TimedRotatingFileHandler(
            filename=logs_dir / "daily.log",
            when='midnight',
            backupCount=7,
            encoding='utf-8'
        )
        daily_handler.setLevel(logging.DEBUG)
        daily_handler.setFormatter(formatter)
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(daily_handler)
    
    # Убираем лишние логи от aiogram и asyncpg
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    
    # Стартовое сообщение (в файлы + консоль если включена)
    logger = logging.getLogger(__name__)
    logger.info("🚀 TeammateBot STARTED")
    logger.info(f"📁 Логи: {logs_dir.absolute()}")
    logger.info(f"📊 Debug: {'ON' if debug_mode else 'OFF'}")
    if console_enabled:
        logger.info(f"🖥️  Консоль: {console_level}")
    else:
        logger.info("🖥️  Консоль: ОТКЛЮЧЕНА")

setup_logging()
logger = logging.getLogger(__name__)

async def cleanup_expired_ads_task(db):
    """Фоновая задача для очистки истекших рекламных постов"""
    logger.info("🗑️ Запуск задачи очистки истекших реклам")

    while True:
        try:
            # Выполняем очистку каждый час
            await asyncio.sleep(3600)  # 1 час

            deleted_count = await db.cleanup_expired_ads()

            if deleted_count > 0:
                logger.info(f"🗑️ Удалено {deleted_count} истекших рекламных постов")

        except Exception as e:
            logger.error(f"❌ Ошибка в задаче очистки реклам: {e}")
            await asyncio.sleep(300)  # При ошибке подождем 5 минут и попробуем снова

async def monthly_reminder_task(bot: Bot, db):
    """Задача для ежемесячных напоминаний"""
    logger.info("📅 Запуск задачи ежемесячных напоминаний")

    try:
        users_for_reminder = await db.get_users_for_monthly_reminder()
        logger.info(f"👥 Найдено {len(users_for_reminder)} пользователей для напоминания")

        reminder_count = 0
        for user in users_for_reminder:
            user_id = user['telegram_id']
            game = user['game']

            try:
                await notify_monthly_profile_reminder(bot, user_id, game, db)
                reminder_count += 1
                await asyncio.sleep(0.1)  # Небольшая задержка между отправками
            except Exception as e:
                logger.error(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")

        logger.info(f"✅ Ежемесячные напоминания отправлены: {reminder_count}/{len(users_for_reminder)}")

    except Exception as e:
        logger.error(f"💥 Критическая ошибка отправки ежемесячных напоминаний: {e}")

async def schedule_monthly_reminders(bot: Bot, db):
    """Планировщик ежемесячных задач"""
    logger.info("⏰ Планировщик ежемесячных напоминаний запущен")
    
    while True:
        try:
            now = datetime.now()

            # Определяем время следующего запуска (1 число каждого месяца в 12:00)
            if now.day == 1 and now.hour < 12:
                next_run = now.replace(hour=12, minute=0, second=0, microsecond=0)
            else:
                if now.month == 12:
                    next_run = now.replace(year=now.year + 1, month=1, day=1, hour=12, minute=0, second=0, microsecond=0)
                else:
                    next_run = now.replace(month=now.month + 1, day=1, hour=12, minute=0, second=0, microsecond=0)

            sleep_seconds = (next_run - now).total_seconds()
            sleep_days = sleep_seconds / 86400
            logger.info(f"⏰ Следующие напоминания через {sleep_days:.1f} дней - {next_run.strftime('%Y-%m-%d %H:%M')}")

            await asyncio.sleep(sleep_seconds)

            # Проверяем, не отправляли ли уже напоминания в этом месяце
            try:
                last_reminder_key = "last_monthly_reminder"
                last_reminder = await db._redis.get(last_reminder_key)
                if last_reminder:
                    last_date = datetime.fromisoformat(last_reminder)
                    if datetime.now() - last_date < timedelta(days=25):
                        logger.info("⏭️  Напоминания уже отправлялись в этом месяце, пропускаем")
                        continue

                # Отмечаем что отправляем напоминания в этом месяце
                await db._redis.setex(last_reminder_key, 86400 * 35, datetime.now().isoformat())
            except Exception as redis_error:
                logger.warning(f"⚠️  Redis недоступен для проверки напоминаний: {redis_error}")

            await monthly_reminder_task(bot, db)

        except Exception as e:
            logger.error(f"💥 Ошибка в планировщике напоминаний: {e}")
            await asyncio.sleep(3600)  # Ждем час и пробуем снова

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("🔄 Удаляем pending updates и настраиваем webhook...")
    await bot.delete_webhook(drop_pending_updates=True)

    # Уведомляем админов о запуске
    startup_success = []
    startup_failed = []
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🤖 Бот запущен и готов к работе!")
            startup_success.append(admin_id)
            logger.info(f"✅ Уведомление о запуске отправлено админу {admin_id}")
        except Exception as e:
            startup_failed.append(admin_id)
            logger.warning(f"⚠️  Не удалось отправить сообщение админу {admin_id}: {e}")

    if startup_success:
        logger.info(f"📨 Уведомления о старте отправлены админам: {startup_success}")
    else:
        logger.warning("⚠️  Не удалось отправить уведомления ни одному админу")
        
    if startup_failed:
        logger.warning(f"❌ Не удалось отправить уведомления админам: {startup_failed}")

async def main():
    """Главная функция запуска бота"""
    try:
        # Загружаем переменные окружения
        load_dotenv(find_dotenv(), override=True)
        token = os.getenv("BOT_TOKEN")
        if not token:
            logger.critical("💥 BOT_TOKEN не найден в переменных окружения!")
            raise RuntimeError("BOT_TOKEN не найден. Проверь .env файл")

        logger.info("🔑 BOT_TOKEN загружен успешно")

        # Создаем бота и диспетчер
        socks_proxy = os.getenv("SOCKS5_PROXY")
        if socks_proxy:
            logger.info(f"🔀 Используем SOCKS5 прокси: {socks_proxy}")
            bot = Bot(token=token, session=AiohttpSession(proxy=socks_proxy))
        else:
            bot = Bot(token=token)
        dp = Dispatcher(storage=MemoryStorage())
        logger.info("🤖 Bot и Dispatcher созданы")

        # Инициализируем базу данных
        logger.info("🔄 Инициализация базы данных PostgreSQL + Redis...")
        db = Database()
        await db.init()
        logger.info("✅ База данных инициализирована успешно")

        # Подключаем middleware
        dp.update.middleware(DatabaseMiddleware(db))
        logger.info("🔧 DatabaseMiddleware подключен")

        dp.callback_query.middleware(StateRecoveryMiddleware())

        # Регистрируем обработчики
        register_handlers(dp)
        logger.info("📝 Обработчики зарегистрированы")

        # Запускаем startup процедуры
        await on_startup(bot)

        # Запускаем планировщик напоминаний в фоне
        reminder_task = asyncio.create_task(schedule_monthly_reminders(bot, db))
        logger.info("⏰ Планировщик напоминаний запущен")

        # Запускаем задачу очистки истекших реклам в фоне
        cleanup_ads_task = asyncio.create_task(cleanup_expired_ads_task(db))
        logger.info("🗑️ Задача очистки истекших реклам запущена")

        logger.info("🚀 CGDV TeammateBot успешно запущен и готов к работе!")
        logger.info("🔄 Начинаем polling...")

        # Основной цикл polling
        await dp.start_polling(bot)

    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("🛑 Остановка бота по запросу пользователя/ОС")
    except Exception as e:
        logger.critical(f"💥 Критическая ошибка запуска: {e}")
        raise
    finally:
        # Завершение работы
        logger.info("🔄 Завершение работы...")
        
        try:
            if 'reminder_task' in locals():
                logger.info("⏰ Отменяем планировщик напоминаний...")
                reminder_task.cancel()
        except:
            pass

        try:
            if 'cleanup_ads_task' in locals():
                logger.info("🗑️ Отменяем задачу очистки реклам...")
                cleanup_ads_task.cancel()
        except:
            pass

        try:
            logger.info("📨 Ожидаем завершения отправки уведомлений...")
            await wait_all_notifications()
        except Exception as e:
            logger.error(f"⚠️  Ошибка ожидания уведомлений: {e}")

        try:
            logger.info("🗃️  Закрываем соединения с базой данных...")
            if 'db' in locals():
                await db.close()
        except Exception as e:
            logger.error(f"⚠️  Ошибка закрытия БД: {e}")

        try:
            logger.info("🔐 Закрываем сессию бота...")
            if 'bot' in locals():
                await bot.session.close()
        except Exception as e:
            logger.error(f"⚠️  Ошибка закрытия бота: {e}")

        logger.info("✅ TeammateBot остановлен корректно")
        logger.info("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки")
    except Exception as e:
        logger.critical(f"💥 Фатальная ошибка: {e}")
        raise