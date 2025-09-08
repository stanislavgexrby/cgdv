import logging
from aiogram import Router, F,  Bot
from aiogram.types import CallbackQuery

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()
db = Database(settings.DATABASE_PATH)

from handlers.basic import safe_edit_message

likes_index = {}

@router.callback_query(F.data == "my_likes")
async def show_my_likes(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('name'):
        await callback.answer("❌ Сначала создайте анкету", show_alert=True)
        return

    likes = db.get_likes_for_user(user_id, user['current_game'])

    if not likes:
        game_name = settings.GAMES.get(user['current_game'], user['current_game'])
        text = f"❤️ Пока никто не лайкнул вашу анкету в {game_name}\n\n"
        text += "Попробуйте:\n"
        text += "• Улучшить анкету\n"
        text += "• Добавить фото\n"
        text += "• Быть активнее в поиске"

        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    likes_index[user_id] = 0
    await show_like_profile(callback, likes, 0)

async def show_like_profile(callback: CallbackQuery, likes: list, index: int):
    """Показать профиль лайкнувшего пользователя"""
    if index >= len(likes):
        text = "✅ Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    profile = likes[index]
    profile_text = texts.format_profile(profile)
    text = f"❤️ Этот игрок лайкнул вас:\n\n{profile_text}"

    try:
        if profile.get('photo_id'):
            try:
                await callback.message.delete()
            except:
                pass

            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=kb.like_actions(profile['telegram_id'])
            )
        else:
            await safe_edit_message(callback, text, kb.like_actions(profile['telegram_id']))

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа лайка: {e}")
        await callback.answer("❌ Ошибка загрузки")

@router.callback_query(F.data.startswith("like_back_"))
async def like_back(callback: CallbackQuery):
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

    is_match = db.add_like(user_id, target_user_id, user['current_game'])

    if is_match:
        target_user = db.get_user(target_user_id)

        if target_user and target_user.get('username'):
            contact_text = f"\n\n💬 @{target_user['username']}"
        else:
            contact_text = "\n\n(У пользователя нет @username)"

        text = texts.MATCH_CREATED + contact_text
        keyboard = kb.contact(target_user.get('username') if target_user else None)

        await safe_edit_message(callback, text, keyboard)
        logger.info(f"Взаимный лайк: {user_id} <-> {target_user_id}")
    else:
        await safe_edit_message(callback, "❤️ Лайк отправлен!", kb.back())

    await callback.answer()

@router.callback_query(F.data.startswith("skip_like_"))
async def skip_like(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user:
        await safe_edit_message(callback, "❌ Ошибка", kb.back())
        await callback.answer()
        return

    likes = db.get_likes_for_user(user_id, user['current_game'])

    current_index = likes_index.get(user_id, 0) + 1
    likes_index[user_id] = current_index

    if current_index >= len(likes):
        text = "✅ Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые."
        await safe_edit_message(callback, text, kb.back())
    else:
        await show_like_profile(callback, likes, current_index)

    await callback.answer()

@router.callback_query(F.data == "my_matches")
async def show_my_matches(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('name'):
        await callback.answer("❌ Сначала создайте анкету", show_alert=True)
        return

    matches = db.get_matches(user_id, user['current_game'])

    if not matches:
        game_name = settings.GAMES.get(user['current_game'], user['current_game'])
        text = f"💔 У вас пока нет матчей в {game_name}\n\n"
        text += "Чтобы получить матчи:\n"
        text += "• Лайкайте анкеты в поиске\n"
        text += "• Отвечайте на лайки других игроков"

        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    game_name = settings.GAMES.get(user['current_game'], user['current_game'])
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

    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

async def notify_about_match(bot: Bot, user_id: int, match_user_id: int):
    try:
        match_user = db.get_user(match_user_id)

        if match_user and match_user.get('name'):
            text = f"🎉 У вас новый матч!\n\n{match_user['name']} лайкнул вас в ответ!"
        else:
            text = "🎉 У вас новый матч!"

        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=kb.back_to_main()
        )
        logger.info(f"📨 Уведомление о матче отправлено {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о матче: {e}")

async def notify_about_like(bot: Bot, user_id: int):
    try:
        await bot.send_message(
            chat_id=user_id,
            text=texts.NEW_LIKE,
            reply_markup=kb.back_to_main()
        )
        logger.info(f"📨 Уведомление о лайке отправлено {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о лайке: {e}")