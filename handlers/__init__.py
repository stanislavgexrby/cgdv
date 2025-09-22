from aiogram import Dispatcher
import logging

logger = logging.getLogger(__name__)

def register_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков"""

    if hasattr(register_handlers, '_registered'):
        logger.warning("Handlers уже зарегистрированы, пропускаем")
        return

    try:
        from . import basic, profile, search, likes, profile_editing, admin, profile_enum

        dp.include_router(basic.router)
        dp.include_router(profile_enum.router)
        dp.include_router(profile.router)
        dp.include_router(profile_editing.router)
        dp.include_router(search.router)
        dp.include_router(likes.router)
        dp.include_router(admin.router)

        register_handlers._registered = True
        logger.info("✅ Все handlers зарегистрированы")

    except Exception as e:
        logger.error(f"❌ Ошибка регистрации handlers: {e}")
        raise