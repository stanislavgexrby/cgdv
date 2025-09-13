import asyncio
import logging
import os
import signal
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot_instance = None
dp_instance = None
database_instance = None
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"Получен сигнал {signum}, начинаем остановку бота...")
    shutdown_event.set()

async def setup_database():
    """Инициализация базы данных"""
    from database.database import Database
    
    database = Database()
    await database.init()
    return database

async def setup_bot():
    """Настройка и инициализация бота"""
    from dotenv import load_dotenv
    load_dotenv(override=True)

    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token or bot_token == 'your_bot_token_here':
        raise ValueError("BOT_TOKEN не установлен в .env файле")

    bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация обработчиков
    from handlers import register_handlers
    register_handlers(dp)

    return bot, dp

async def notify_admin_startup(bot: Bot):
    """Уведомление админа о запуске"""
    admin_id = os.getenv('ADMIN_ID')
    if admin_id and admin_id != '123456789' and admin_id.isdigit():
        try:
            await bot.send_message(int(admin_id), "🚀 CGDV запущен с PostgreSQL + Redis!")
            logger.info(f"Админ {admin_id} уведомлен о запуске")
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа: {e}")

async def notify_admin_shutdown(bot: Bot):
    """Уведомление админа об остановке"""
    admin_id = os.getenv('ADMIN_ID')
    if admin_id and admin_id != '123456789' and admin_id.isdigit():
        try:
            await bot.send_message(int(admin_id), "🛑 CGDV остановлен")
            logger.info(f"Админ {admin_id} уведомлен об остановке")
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа об остановке: {e}")

# Глобальный доступ к БД для handlers
_global_database = None

def get_database():
    """Получение экземпляра базы данных для handlers"""
    return _global_database

async def main():
    """Основная функция запуска бота"""
    global bot_instance, dp_instance, database_instance, _global_database
    
    # Настройка обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Инициализация базы данных
        logger.info("🔄 Инициализация базы данных PostgreSQL + Redis...")
        database_instance = await setup_database()
        _global_database = database_instance  # Делаем доступной для handlers
        
        # Инициализация бота
        logger.info("🔄 Инициализация CGDV...")
        bot_instance, dp_instance = await setup_bot()
        
        # Уведомление админа
        await notify_admin_startup(bot_instance)
        
        logger.info("✅ CGDV запущен успешно!")
        
        # Создаем задачи
        polling_task = asyncio.create_task(
            dp_instance.start_polling(bot_instance, skip_updates=True)
        )
        
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        
        # Ждем завершения одной из задач
        done, pending = await asyncio.wait(
            [polling_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Отменяем незавершенные задачи
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Проверяем результат polling
        if polling_task in done:
            try:
                await polling_task
            except Exception as e:
                logger.error(f"Ошибка в polling: {e}")
                raise
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        return False
    
    finally:
        # Graceful shutdown
        logger.info("🔄 Начинаем graceful shutdown...")
        
        if bot_instance:
            try:
                await notify_admin_shutdown(bot_instance)
                await bot_instance.session.close()
            except Exception as e:
                logger.error(f"Ошибка при закрытии бота: {e}")
        
        # Закрываем базу данных
        if database_instance:
            try:
                await database_instance.close()
                logger.info("✅ База данных закрыта")
            except Exception as e:
                logger.error(f"Ошибка закрытия базы данных: {e}")
        
        logger.info("👋 CGDV остановлен")
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("👋 Остановка по Ctrl+C")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        sys.exit(1)