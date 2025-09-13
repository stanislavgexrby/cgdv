import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings
from handlers.basic import check_ban_and_profile, safe_edit_message
from handlers.notifications import notify_about_match, notify_about_like

logger = logging.getLogger(__name__)
router = Router()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def show_profile_with_photo(callback: CallbackQuery, profile: dict, text: str, keyboard):
    """Универсальная функция показа профиля с фото или без"""
    try:
        if profile.get('photo_id'):
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=keyboard
            )
        else:
            await safe_edit_message(callback, text, keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа профиля: {e}")
        await callback.answer("❌ Ошибка загрузки")

async def show_empty_state(callback: CallbackQuery, message: str):
    """Показ пустого состояния (нет лайков/матчей)"""
    await safe_edit_message(callback, message, kb.back())
    await callback.answer()

async def process_like_action(callback: CallbackQuery, target_user_id: int, action: str, current_index: int = 0, db=None):
    if db is None:
        raise RuntimeError("db is required")

    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    if action == "like":
        is_match = await db.add_like(user_id, target_user_id, game)

        if is_match:
            # было: await handle_match_created(callback, target_user_id, game)
            await handle_match_created(callback, target_user_id, game, db)
        else:
            await notify_about_like(callback.bot, target_user_id, game)
            # было: await show_next_like_or_finish(callback, user_id, game)
            await show_next_like_or_finish(callback, user_id, game, db)

    elif action == "skip":
        await db.skip_like(user_id, target_user_id, game)
        # было: await show_next_like_or_finish(callback, user_id, game)
        await show_next_like_or_finish(callback, user_id, game, db)



async def handle_match_created(callback: CallbackQuery, target_user_id: int, game: str, db):
    bot = callback.bot
    user_id = callback.from_user.id

    # уведомление текущему
    await notify_about_match(bot, user_id, target_user_id, game, db)
    # уведомление тому, кого лайкнули
    await notify_about_match(bot, target_user_id, user_id, game, db)
    """Обработка создания матча"""
    target_profile = await db.get_user_profile(target_user_id, game)
    await notify_about_match(callback.bot, target_user_id, callback.from_user.id, game)

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
    logger.info(f"Взаимный лайк: {callback.from_user.id} <-> {target_user_id}")

async def show_next_like_or_finish(callback: CallbackQuery, user_id: int, game: str, db):
    """Показ следующего лайка или завершение просмотра"""
    likes = await db.get_likes_for_user(user_id, game)
    
    if likes:
        await show_like_profile(callback, likes, 0)
    else:
        text = "✅ Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые."
        await safe_edit_message(callback, text, kb.back())

async def show_like_profile(callback: CallbackQuery, likes: list, index: int):
    """Показ профиля в лайках"""
    if index >= len(likes):
        text = "✅ Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    profile = likes[index]
    profile_text = texts.format_profile(profile)
    text = f"❤️ Этот игрок лайкнул вас:\n\n{profile_text}"

    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [
            kb.InlineKeyboardButton(text="❤️ Лайк в ответ", callback_data=f"loves_back_{profile['telegram_id']}_{index}"),
            kb.InlineKeyboardButton(text="👎 Пропустить", callback_data=f"loves_skip_{profile['telegram_id']}_{index}")
        ],
        [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await show_profile_with_photo(callback, profile, text, keyboard)

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "my_likes")
@check_ban_and_profile()
async def show_my_likes(callback: CallbackQuery, state: FSMContext, db):
    """Показ входящих лайков"""
    await state.clear()

    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    likes = await db.get_likes_for_user(user_id, game)

    if not likes:
        game_name = settings.GAMES.get(game, game)
        text = f"❤️ Пока никто не лайкнул вашу анкету в {game_name}\n\n"
        text += "Попробуйте:\n"
        text += "• Улучшить анкету\n"
        text += "• Добавить фото\n"
        text += "• Быть активнее в поиске"
        
        await show_empty_state(callback, text)
        return

    await show_like_profile(callback, likes, 0)

@router.callback_query(F.data == "my_matches")
@check_ban_and_profile()
async def show_my_matches(callback: CallbackQuery, state: FSMContext, db):
    """Показ матчей пользователя"""
    await state.clear()

    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    matches = await db.get_matches(user_id, game)
    game_name = settings.GAMES.get(game, game)

    if not matches:
        text = f"💔 У вас пока нет матчей в {game_name}\n\n"
        text += "Чтобы получить матчи:\n"
        text += "• Лайкайте анкеты в поиске\n"
        text += "• Отвечайте на лайки других игроков"
        
        await show_empty_state(callback, text)
        return

    # Формируем список матчей
    text = f"💖 Ваши матчи в {game_name} ({len(matches)}):\n\n"
    for i, match in enumerate(matches, 1):
        name = match['name']
        username = match.get('username', 'нет username')
        text += f"{i}. {name} (@{username})\n"

    text += "\n💬 Вы можете связаться с любым из них!"

    # Создаем кнопки для контакта (максимум 5)
    buttons = []
    for match in matches[:5]:
        name = match['name'][:15] + "..." if len(match['name']) > 15 else match['name']
        buttons.append([kb.InlineKeyboardButton(
            text=f"💬 {name}", 
            callback_data=f"contact_{match['telegram_id']}"
        )])

    buttons.append([kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

# ==================== ОБРАБОТЧИКИ ДЕЙСТВИЙ С ЛАЙКАМИ ====================

@router.callback_query(F.data.startswith("like_back"))
async def like_back(callback: CallbackQuery, state: FSMContext, db):
    """
    Возврат к предыдущей анкете и повторная попытка "лайк".
    Ожидается, что в callback.data есть ID и текущий индекс (как у тебя было).
    """
    parts = callback.data.split("_")
    try:
        target_user_id = int(parts[2])
    except Exception:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    current_index = 0
    if len(parts) > 3:
        try:
            current_index = int(parts[3])
        except Exception:
            current_index = 0

    await process_like_action(callback, target_user_id, "like", current_index, db=db)
    await callback.answer()


@router.callback_query(F.data.startswith("loves_skip_"))
async def skip_like(callback: CallbackQuery, db):
    """Пропуск лайка"""
    try:
        parts = callback.data.split("_")
        target_user_id = int(parts[2])
        current_index = int(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await safe_edit_message(callback, "❌ Ошибка", kb.back())
        await callback.answer()
        return

    # Проверяем бан
    if await db.is_user_banned(user_id):
        game_name = settings.GAMES.get(user['current_game'], user['current_game'])
        ban_info = await db.get_user_ban(user_id)
        
        if ban_info:
            ban_end = ban_info['expires_at'][:16]
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end}."
        else:
            text = f"🚫 Вы заблокированы в {game_name}."
        
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    await process_like_action(callback, target_user_id, "skip", current_index)
    await callback.answer()

# ==================== ПОКАЗ КОНТАКТОВ ====================

@router.callback_query(F.data.startswith("contact_"))
async def show_contact(callback: CallbackQuery, db):
    """Показ контактной информации матча"""
    try:
        target_user_id = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']

    # Проверяем бан
    if await db.is_user_banned(user_id):
        game_name = settings.GAMES.get(game, game)
        ban_info = await db.get_user_ban(user_id)
        
        if ban_info:
            ban_end = ban_info['expires_at'][:16]
            await callback.answer(f"🚫 Вы заблокированы в {game_name} до {ban_end}", show_alert=True)
        else:
            await callback.answer(f"🚫 Вы заблокированы в {game_name}", show_alert=True)
        return

    # Получаем профиль
    target_profile = await db.get_user_profile(target_user_id, game)

    if not target_profile:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    profile_text = texts.format_profile(target_profile, show_contact=True)
    text = f"💖 Ваш матч:\n\n{profile_text}"

    keyboard = kb.contact(target_profile.get('username'))

    await show_profile_with_photo(callback, target_profile, text, keyboard)