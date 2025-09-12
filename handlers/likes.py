import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

from .notifications import notify_about_match, notify_about_like

logger = logging.getLogger(__name__)
router = Router()
db = Database(settings.DATABASE_PATH)

from handlers.basic import safe_edit_message

@router.callback_query(F.data == "my_likes")
async def show_my_likes(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']

    if db.is_user_banned(user_id):
        ban_info = db.get_user_ban(user_id)
        if ban_info:
            game_name = settings.GAMES.get(game, game)
            ban_end = ban_info['expires_at']
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}\n\n"
            text += "Во время блокировки раздел 'Лайки' недоступен."

            await safe_edit_message(callback, text, kb.back())
            await callback.answer()
            return

    if not db.has_profile(user_id, game):
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"❌ Сначала создайте анкету для {game_name}", show_alert=True)
        return

    likes = db.get_likes_for_user(user_id, game)

    if not likes:
        game_name = settings.GAMES.get(game, game)
        text = f"❤️ Пока никто не лайкнул вашу анкету в {game_name}\n\n"
        text += "Попробуйте:\n"
        text += "• Улучшить анкету\n"
        text += "• Добавить фото\n"
        text += "• Быть активнее в поиске"

        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    await show_like_profile(callback, likes, 0)

async def show_like_profile(callback: CallbackQuery, likes: list, index: int):
    if index >= len(likes):
        text = "✅ Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    profile = likes[index]
    profile_text = texts.format_profile(profile)
    text = f"❤️ Этот игрок лайкнул вас:\n\n{profile_text}"

    callback_like = f"loves_back_{profile['telegram_id']}_{index}"
    callback_skip = f"loves_skip_{profile['telegram_id']}_{index}"

    like_keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [
            kb.InlineKeyboardButton(text="❤️ Лайк в ответ", callback_data=callback_like),
            kb.InlineKeyboardButton(text="👎 Пропустить", callback_data=callback_skip)
        ],
        [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    try:
        if profile.get('photo_id'):
            try:
                await callback.message.delete()
            except:
                pass

            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=like_keyboard
            )
        else:
            await safe_edit_message(callback, text, like_keyboard)

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа лайка: {e}")
        await callback.answer("❌ Ошибка загрузки")

@router.callback_query(F.data.startswith("loves_back_"))
async def like_back(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        target_user_id = int(parts[2])
        current_index = int(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']

    if db.is_user_banned(user_id):
        game_name = settings.GAMES.get(game, game)
        ban_info = db.get_user_ban(user_id)
        if ban_info:
            ban_end = ban_info['expires_at']
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}. Нельзя отправлять лайки."
        else:
            text = f"🚫 Вы заблокированы в {game_name}. Нельзя отправлять лайки."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    is_match = db.add_like(user_id, target_user_id, game)

    if is_match:
        target_profile = db.get_user_profile(target_user_id, game)
        await notify_about_match(callback.bot, target_user_id, user_id, game)

        if target_profile:
            match_text = texts.format_profile(target_profile, show_contact=True)
            text = f"{texts.MATCH_CREATED}\n\n{match_text}"
        else:
            text = texts.MATCH_CREATED
            if target_profile and target_profile.get('username'):
                text += f"\n\n💬 @{target_profile['username']}"
            else:
                text += "\n\n(У пользователя нет @username)"

        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="❤️ Другие лайки", callback_data="my_likes")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])

        await safe_edit_message(callback, text, keyboard)

        logger.info(f"Взаимный лайк: {user_id} <-> {target_user_id}")
    else:
        await notify_about_like(callback.bot, target_user_id, game)

        likes = db.get_likes_for_user(user_id, game)

        if likes and current_index < len(likes):
            await show_like_profile(callback, likes, current_index)
        else:
            text = "✅ Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые."
            await safe_edit_message(callback, text, kb.back())

    await callback.answer()

@router.callback_query(F.data.startswith("loves_skip_"))
async def skip_like(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        target_user_id = int(parts[2])
        current_index = int(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await safe_edit_message(callback, "❌ Ошибка", kb.back())
        await callback.answer()
        return

    game = user['current_game']

    if db.is_user_banned(user_id):
        game_name = settings.GAMES.get(game, game)
        ban_info = db.get_user_ban(user_id)
        if ban_info:
            ban_end = ban_info['expires_at']
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}."
        else:
            text = f"🚫 Вы заблокированы в {game_name}."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    db.skip_like(user_id, target_user_id, game)

    likes = db.get_likes_for_user(user_id, game)

    if likes:
        await show_like_profile(callback, likes, 0)
    else:
        text = "✅ Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые."
        await safe_edit_message(callback, text, kb.back())

    await callback.answer()

@router.callback_query(F.data == "my_matches")
async def show_my_matches(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']

    if db.is_user_banned(user_id):
        ban_info = db.get_user_ban(user_id)
        if ban_info:
            game_name = settings.GAMES.get(game, game)
            ban_end = ban_info['expires_at']
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}\n\n"
            text += "Во время блокировки раздел 'Матчи' недоступен."

            await safe_edit_message(callback, text, kb.back())
            await callback.answer()
            return

    if not db.has_profile(user_id, game):
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"❌ Сначала создайте анкету для {game_name}", show_alert=True)
        return

    matches = db.get_matches(user_id, game)
    game_name = settings.GAMES.get(game, game)

    if not matches:
        text = f"💔 У вас пока нет матчей в {game_name}\n\n"
        text += "Чтобы получить матчи:\n"
        text += "• Лайкайте анкеты в поиске\n"
        text += "• Отвечайте на лайки других игроков"

        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    text = f"💖 Ваши матчи в {game_name} ({len(matches)}):\n\n"

    for i, match in enumerate(matches, 1):
        name = match['name']
        username = match.get('username', 'нет username')
        text += f"{i}. {name} (@{username})\n"

    text += "\n💬 Вы можете связаться с любым из них!"

    buttons = []
    for i, match in enumerate(matches[:5]):
        name = match['name'][:15] + "..." if len(match['name']) > 15 else match['name']
        buttons.append([kb.InlineKeyboardButton(
            text=f"💬 {name}", 
            callback_data=f"contact_{match['telegram_id']}"
        )])

    buttons.append([kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("contact_"))
async def show_contact(callback: CallbackQuery):
    try:
        target_user_id = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']

    if db.is_user_banned(user_id):
        game_name = settings.GAMES.get(game, game)
        ban_info = db.get_user_ban(user_id)
        if ban_info:
            ban_end = ban_info['expires_at']
            await callback.answer(f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}", show_alert=True)
        else:
            await callback.answer(f"🚫 Вы заблокированы в {game_name}", show_alert=True)
        return

    target_profile = db.get_user_profile(target_user_id, game)

    if not target_profile:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    profile_text = texts.format_profile(target_profile, show_contact=True)
    text = f"💖 Ваш матч:\n\n{profile_text}"

    keyboard = kb.contact(target_profile.get('username'))

    try:
        if target_profile.get('photo_id'):
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=target_profile['photo_id'],
                caption=text,
                reply_markup=keyboard
            )
        else:
            await safe_edit_message(callback, text, keyboard)
    except Exception as e:
        logger.error(f"Ошибка отображения контакта: {e}")
        await safe_edit_message(callback, text, keyboard)

    await callback.answer()