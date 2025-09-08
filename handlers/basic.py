import logging
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import Command

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()
db = Database(settings.DATABASE_PATH)

__all__ = ['safe_edit_message', 'router']

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    try:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=reply_markup)
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        try:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=reply_markup)
        except:
            pass

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    logger.info(f"Пользователь {user_id} запустил бота")

    user = db.get_user(user_id)

    if user and user.get('current_game'):
        game = user['current_game']
        game_name = settings.GAMES.get(game, game)
        has_profile = db.has_profile(user_id, game)

        text = f"🏠 Главное меню\n\nТекущая игра: {game_name}"
        if has_profile:
            text += "\n\nВыберите действие:"
        else:
            text += "\n\nСоздайте анкету для начала:"

        await message.answer(text, reply_markup=kb.main_menu(has_profile, game))
    else:
        await message.answer(texts.WELCOME, reply_markup=kb.game_selection())

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """🎮 TeammateBot - Помощь

🔍 Функции:
• Создание анкеты для каждой игры
• Поиск сокомандников
• Система лайков и матчей

📝 Как пользоваться:
1. Выберите игру (Dota 2 или CS2)
2. Создайте анкету для выбранной игры
3. Ищите игроков с фильтрами
4. Лайкайте понравившихся
5. При взаимном лайке получите контакты

⚙️ Команды:
/start - Главное меню
/help - Эта справка"""

    await message.answer(help_text)

@router.callback_query(F.data.startswith("game_"))
async def select_game(callback: CallbackQuery):
    game = callback.data.split("_")[1]
    user_id = callback.from_user.id
    username = callback.from_user.username

    logger.info(f"Пользователь {user_id} выбрал игру: {game}")

    db.create_user(user_id, username, game)

    has_profile = db.has_profile(user_id, game)
    game_name = settings.GAMES.get(game, game)
    
    text = f"🏠 Главное меню\n\nИгра: {game_name}"

    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += "\n\nСоздайте анкету для начала:"

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()

@router.callback_query(F.data.startswith("switch_"))
async def switch_game(callback: CallbackQuery):
    game = callback.data.split("_")[1]
    user_id = callback.from_user.id

    logger.info(f"Переключение на игру: {game}")

    db.switch_game(user_id, game)

    has_profile = db.has_profile(user_id, game)
    game_name = settings.GAMES.get(game, game)
    
    text = f"🏠 Главное меню\n\nИгра: {game_name}"

    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += f"\n\nУ вас пока нет анкеты для {game_name}.\nСоздайте анкету для начала:"

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await safe_edit_message(callback, texts.WELCOME, kb.game_selection())
        await callback.answer()
        return

    game = user['current_game']
    has_profile = db.has_profile(user_id, game)
    game_name = settings.GAMES.get(game, game)

    text = f"🏠 Главное меню\n\nИгра: {game_name}"

    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += "\n\nСоздайте анкету для начала:"

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()

@router.callback_query(F.data == "view_profile")
async def view_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']
    profile = db.get_user_profile(user_id, game)

    if not profile:
        await callback.answer("❌ Анкета не найдена", show_alert=True)
        return

    # Показываем контакты при просмотре своей анкеты
    profile_text = texts.format_profile(profile, show_contact=True)
    game_name = settings.GAMES.get(game, game)
    text = f"👤 Ваша анкета в {game_name}:\n\n{profile_text}"

    try:
        # Если есть фото, показываем с фото
        if profile.get('photo_id'):
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=kb.back()
            )
        else:
            # Если фото нет, показываем текстом
            await safe_edit_message(callback, text, kb.back())
    except Exception as e:
        logger.error(f"Ошибка отображения профиля: {e}")
        # Fallback на текстовое сообщение
        await safe_edit_message(callback, text, kb.back())

    await callback.answer()

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ панель"""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ Нет прав")
        return

    try:
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM profiles")
            total_profiles = cursor.fetchone()[0]

            cursor = conn.execute("SELECT game, COUNT(*) FROM profiles GROUP BY game")
            profiles_by_game = cursor.fetchall()

            cursor = conn.execute("SELECT COUNT(*) FROM matches")
            total_matches = cursor.fetchone()[0]

        text = f"""👑 Админ панель

📊 Статистика:
• Всего пользователей: {total_users}
• Всего анкет: {total_profiles}"""

        for game, count in profiles_by_game:
            game_name = settings.GAMES.get(game, game)
            text += f"\n  - {game_name}: {count}"

        text += f"\n• Матчей: {total_matches}"

        await message.answer(text)
    except Exception as e:
        await message.answer(f"Ошибка получения статистики: {e}")