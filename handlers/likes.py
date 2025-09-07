# handlers/likes.py
"""
Лайки и матчи
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()
db = Database(settings.DATABASE_PATH)

@router.callback_query(F.data == "my_likes")
async def show_my_likes(callback: CallbackQuery):
    """Показать входящие лайки"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user or not user.get('name'):
        await callback.answer("❌ Сначала создайте анкету", show_alert=True)
        return
    
    # Получаем лайки
    likes = db.get_likes_for_user(user_id, user['current_game'])
    
    if not likes:
        game_name = settings.GAMES.get(user['current_game'], user['current_game'])
        text = f"❤️ Пока никто не лайкнул вашу анкету в {game_name}\n\n"
        text += "Попробуйте:\n"
        text += "• Улучшить анкету\n"
        text += "• Добавить фото\n"
        text += "• Быть активнее в поиске"
        
        await callback.message.edit_text(text, reply_markup=kb.back())
        await callback.answer()
        return
    
    # Показываем первый лайк
    await show_like_profile(callback, likes[0])

async def show_like_profile(callback: CallbackQuery, profile: dict):
    """Показать профиль того, кто лайкнул"""
    profile_text = texts.format_profile(profile)
    text = f"❤️ Этот игрок лайкнул вас:\n\n{profile_text}"
    
    try:
        if profile.get('photo_id'):
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=kb.like_actions(profile['telegram_id'])
            )
        else:
            await callback.message.edit_text(text, reply_markup=kb.like_actions(profile['telegram_id']))
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка показа лайка: {e}")
        await callback.answer("❌ Ошибка загрузки")

@router.callback_query(F.data.startswith("like_back_"))
async def like_back(callback: CallbackQuery):
    """Лайкнуть в ответ"""
    try:
        target_user_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    # Добавляем лайк (это точно будет матч)
    is_match = db.add_like(user_id, target_user_id, user['current_game'])
    
    if is_match:
        # Получаем данные пользователя
        target_user = db.get_user(target_user_id)
        
        if target_user and target_user.get('username'):
            contact_text = f"\n\n💬 @{target_user['username']}"
        else:
            contact_text = "\n\n(У пользователя нет @username)"
        
        text = texts.MATCH_CREATED + contact_text
        keyboard = kb.contact(target_user.get('username') if target_user else None)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        logger.info(f"Взаимный лайк: {user_id} <-> {target_user_id}")
    else:
        await callback.message.edit_text("❤️ Лайк отправлен!", reply_markup=kb.back())
    
    await callback.answer()

@router.callback_query(F.data.startswith("skip_like_"))
async def skip_like(callback: CallbackQuery):
    """Пропустить лайк"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.message.edit_text("❌ Ошибка", reply_markup=kb.back())
        await callback.answer()
        return
    
    # Получаем оставшиеся лайки
    likes = db.get_likes_for_user(user_id, user['current_game'])
    
    if len(likes) <= 1:
        text = "✅ Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые."
        await callback.message.edit_text(text, reply_markup=kb.back())
    else:
        # Показываем следующий лайк
        await show_like_profile(callback, likes[1])
    
    await callback.answer()

@router.callback_query(F.data == "my_matches")
async def show_my_matches(callback: CallbackQuery):
    """Показать матчи"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user or not user.get('name'):
        await callback.answer("❌ Сначала создайте анкету", show_alert=True)
        return
    
    # Получаем матчи
    matches = db.get_matches(user_id, user['current_game'])
    
    if not matches:
        game_name = settings.GAMES.get(user['current_game'], user['current_game'])
        text = f"💔 У вас пока нет матчей в {game_name}\n\n"
        text += "Чтобы получить матчи:\n"
        text += "• Лайкайте анкеты в поиске\n"
        text += "• Отвечайте на лайки других игроков"
        
        await callback.message.edit_text(text, reply_markup=kb.back())
        await callback.answer()
        return
    
    # Формируем список матчей
    game_name = settings.GAMES.get(user['current_game'], user['current_game'])
    text = f"💖 Ваши матчи в {game_name} ({len(matches)}):\n\n"
    
    for i, match in enumerate(matches, 1):
        name = match['name']
        username = match.get('username', 'нет username')
        text += f"{i}. {name} (@{username})\n"
    
    text += "\n💬 Вы можете связаться с любым из них!"
    
    # Создаем кнопки для первых 5 матчей
    buttons = []
    for i, match in enumerate(matches[:5]):
        name = match['name'][:15] + "..." if len(match['name']) > 15 else match['name']
        buttons.append([kb.InlineKeyboardButton(
            text=f"💬 {name}", 
            callback_data=f"contact_{match['telegram_id']}"
        )])
    
    buttons.append([kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("contact_"))
async def show_contact(callback: CallbackQuery):
    """Показать контакт матча"""
    try:
        target_user_id = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    # Получаем данные пользователя
    target_user = db.get_user(target_user_id)
    
    if not target_user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    profile_text = texts.format_profile(target_user)
    text = f"💖 Ваш матч:\n\n{profile_text}"
    
    if target_user.get('username'):
        text += f"\n\n💬 @{target_user['username']}"
    else:
        text += "\n\n(У пользователя нет @username)"
    
    keyboard = kb.contact(target_user.get('username'))
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()