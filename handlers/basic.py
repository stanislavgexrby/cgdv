# handlers/basic.py
"""
Основные команды и навигация
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()
db = Database(settings.DATABASE_PATH)

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    logger.info(f"Пользователь {user_id} запустил бота")
    
    # Проверяем есть ли пользователь
    user = db.get_user(user_id)
    
    if user and user.get('current_game'):
        # Пользователь есть, показываем главное меню
        game_name = settings.GAMES.get(user['current_game'], user['current_game'])
        has_profile = bool(user.get('name'))
        
        text = f"🏠 Главное меню\n\nТекущая игра: {game_name}"
        if has_profile:
            text += "\n\nВыберите действие:"
        else:
            text += "\n\nСоздайте анкету для начала:"
        
        await message.answer(text, reply_markup=kb.main_menu(has_profile, user['current_game']))
    else:
        # Новый пользователь, показываем выбор игры
        await message.answer(texts.WELCOME, reply_markup=kb.game_selection())

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь"""
    help_text = """🎮 TeammateBot - Помощь

🔍 Функции:
• Создание анкеты
• Поиск сокомандников
• Система лайков и матчей

📝 Как пользоваться:
1. Выберите игру (Dota 2 или CS2)
2. Создайте анкету
3. Ищите игроков с фильтрами
4. Лайкайте понравившихся
5. При взаимном лайке получите контакты

⚙️ Команды:
/start - Главное меню
/help - Эта справка"""
    
    await message.answer(help_text)

@router.callback_query(F.data.startswith("game_"))
async def select_game(callback: CallbackQuery):
    """Выбор игры"""
    game = callback.data.split("_")[1]
    user_id = callback.from_user.id
    username = callback.from_user.username
    
    logger.info(f"Пользователь {user_id} выбрал игру: {game}")
    
    # Создаем/обновляем пользователя
    db.create_user(user_id, username, game)
    
    # Получаем пользователя
    user = db.get_user(user_id)
    has_profile = bool(user.get('name'))
    
    game_name = settings.GAMES.get(game, game)
    text = f"🏠 Главное меню\n\nИгра: {game_name}"
    
    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += "\n\nСоздайте анкету для начала:"
    
    await callback.message.edit_text(text, reply_markup=kb.main_menu(has_profile, game))
    await callback.answer()

@router.callback_query(F.data.startswith("switch_"))
async def switch_game(callback: CallbackQuery):
    """Переключение игры"""
    game = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    logger.info(f"Переключение на игру: {game}")
    
    # Переключаем игру
    db.switch_game(user_id, game)
    
    # Получаем пользователя
    user = db.get_user(user_id)
    has_profile = bool(user.get('name'))
    
    game_name = settings.GAMES.get(game, game)
    text = f"🏠 Главное меню\n\nИгра: {game_name}"
    
    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += "\n\nСоздайте анкету для начала:"
    
    await callback.message.edit_text(text, reply_markup=kb.main_menu(has_profile, game))
    await callback.answer()

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    """Главное меню"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user or not user.get('current_game'):
        await callback.message.edit_text(texts.WELCOME, reply_markup=kb.game_selection())
        await callback.answer()
        return
    
    has_profile = bool(user.get('name'))
    game_name = settings.GAMES.get(user['current_game'], user['current_game'])
    
    text = f"🏠 Главное меню\n\nИгра: {game_name}"
    
    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += "\n\nСоздайте анкету для начала:"
    
    await callback.message.edit_text(text, reply_markup=kb.main_menu(has_profile, user['current_game']))
    await callback.answer()

@router.callback_query(F.data == "view_profile")
async def view_profile(callback: CallbackQuery):
    """Просмотр профиля"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user or not user.get('name'):
        await callback.answer("❌ Анкета не найдена", show_alert=True)
        return
    
    profile_text = texts.format_profile(user)
    text = f"👤 Ваша анкета:\n\n{profile_text}"
    
    await callback.message.edit_text(text, reply_markup=kb.back())
    await callback.answer()

# Админ команды
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ панель"""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ Нет прав")
        return
    
    # Простая статистика
    try:
        with db._init_db.__self__._init_db.__globals__['sqlite3'].connect(db.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM users WHERE name IS NOT NULL")
            with_profiles = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM matches")
            total_matches = cursor.fetchone()[0]
        
        text = f"""👑 Админ панель

📊 Статистика:
• Всего пользователей: {total_users}
• С анкетами: {with_profiles}
• Матчей: {total_matches}"""
        
        await message.answer(text)
    except Exception as e:
        await message.answer(f"Ошибка получения статистики: {e}")