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

# Простые глобальные переменные
bot_instance = None
dp_instance = None
database_instance = None
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    logger.info(f"Получен сигнал {signum}, начинаем остановку бота...")
    shutdown_event.set()

async def setup_database():
    from database.database import Database
    database = Database()
    await database.init()
    return database

async def setup_bot(database):
    """Настройка и инициализация бота"""
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token or bot_token == 'your_bot_token_here':
        raise ValueError("BOT_TOKEN не установлен в .env файле")

    bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    from middleware.database import DatabaseMiddleware
    dp.message.middleware(DatabaseMiddleware(database))
    dp.callback_query.middleware(DatabaseMiddleware(database))

    from handlers import register_handlers
    register_handlers(dp)

    return bot, dp

async def main():
    global bot_instance, dp_instance, database_instance
    
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Инициализация базы данных
        logger.info("🔄 Инициализация базы данных PostgreSQL + Redis...")
        database_instance = await setup_database()
        
        # Тест БД
        await database_instance.get_user(123456789)
        logger.info("✅ База данных инициализирована и протестирована")
        
        # Инициализация бота с БД
        logger.info("🔄 Инициализация CGDV...")
        bot_instance, dp_instance = await setup_bot(database_instance)
        
        logger.info("✅ CGDV запущен успешно!")
        
        # Polling
        await dp_instance.start_polling(bot_instance, skip_updates=True)
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        return False
    
    finally:
        if database_instance:
            await database_instance.close()
            logger.info("✅ База данных закрыта")
        logger.info("👋 CGDV остановлен")
    
    return True

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановка по Ctrl+C")