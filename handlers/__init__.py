# handlers/__init__.py
"""
Регистрация всех обработчиков
"""

from aiogram import Dispatcher
from . import basic, profile, search, likes

def register_handlers(dp: Dispatcher):
    """Регистрируем все обработчики"""
    dp.include_router(profile.router)  # FSM обработчики первыми
    dp.include_router(search.router)
    dp.include_router(likes.router)
    dp.include_router(basic.router)    # Основные команды последними