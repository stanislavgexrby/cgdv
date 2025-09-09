from aiogram import Dispatcher
from . import basic, profile, search, likes, profile_editing

def register_handlers(dp: Dispatcher):
    dp.include_router(profile.router)
    dp.include_router(profile_editing.router)
    dp.include_router(search.router)
    dp.include_router(likes.router)
    dp.include_router(basic.router)