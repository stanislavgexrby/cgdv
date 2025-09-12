import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def main():
    if hasattr(main, '_running'):
        logger.warning("main() уже запущен, завершаем дублирующий вызов")
        return
    main._running = True

    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)

        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token or bot_token == 'your_bot_token_here':
            logger.error("BOT_TOKEN не установлен в .env файле")
            return

        bot = Bot(token=bot_token)
        dp = Dispatcher(storage=MemoryStorage())

        from handlers import register_handlers
        register_handlers(dp)

        logger.info("CGDV запускается...")

        admin_id = os.getenv('ADMIN_ID')
        if admin_id and admin_id != '123456789':
            try:
                await bot.send_message(int(admin_id), "CGDV запущен!")
            except:
                pass

        try:
            await dp.start_polling(bot, skip_updates=True)
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
        finally:
            await bot.session.close()

    finally:
        if hasattr(main, '_running'):
            delattr(main, '_running')

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")