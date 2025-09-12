import logging
from aiogram import Bot
from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
db = Database(settings.DATABASE_PATH)

async def notify_about_match(bot: Bot, user_id: int, match_user_id: int):
    try:
        user = db.get_user(user_id)
        if not user:
            return

        game = user['current_game']
        match_profile = db.get_user_profile(match_user_id, game)

        if match_profile and match_profile.get('name'):
            profile_text = texts.format_profile(match_profile, show_contact=True)
            game_name = settings.GAMES.get(game, game)
            text = f"🎉 У вас новый матч в {game_name}!\n\n{profile_text}"

            if match_profile.get('photo_id'):
                await bot.send_photo(
                    chat_id=user_id,
                    photo=match_profile['photo_id'],
                    caption=text,
                    reply_markup=kb.back()
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=kb.back()
                )
        else:
            game_name = settings.GAMES.get(game, game)
            text = f"🎉 У вас новый матч в {game_name}!"
            await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=kb.back()
            )

        logger.info(f"📨 Уведомление о матче отправлено {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о матче: {e}")

async def notify_about_like(bot: Bot, user_id: int, game: str = None):
    try:
        if not game:
            user = db.get_user(user_id)
            if user:
                game = user.get('current_game', 'dota')
            else:
                game = 'dota'

        current_user = db.get_user(user_id)
        if current_user and current_user.get('current_game') != game:
            db.switch_game(user_id, game)
            logger.info(f"Переключили пользователя {user_id} на {game} из-за лайка")

        game_name = settings.GAMES.get(game, game)

        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="❤️ Посмотреть лайки", callback_data="my_likes")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])

        text = f"❤️ Кто-то лайкнул вашу анкету в {game_name}! Зайдите в 'Лайки' чтобы посмотреть."

        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard
        )
        logger.info(f"📨 Уведомление о лайке отправлено {user_id} для игры {game}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о лайке: {e}")

async def notify_profile_deleted(bot: Bot, user_id: int, game: str):
    try:
        game_name = settings.GAMES.get(game, game)
        text = f"⚠️ Ваша анкета в {game_name} была удалена модератором\n\n"
        text += f"📋 Причина: нарушение правил сообщества\n\n"
        text += f"✅ Что можно сделать:\n"
        text += f"• Создать новую анкету\n"
        text += f"• Соблюдать правила сообщества\n"
        text += f"• Быть вежливыми с другими игроками"

        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="📝 Создать новую анкету", callback_data="create_profile")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])

        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard
        )
        logger.info(f"📨 Уведомление об удалении профиля отправлено {user_id} для игры {game}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об удалении профиля: {e}")

async def notify_user_banned(bot: Bot, user_id: int, expires_at: str):
    try:
        text = f"🚫 Вы заблокированы до {expires_at[:16]} за нарушение правил сообщества.\n\n" \
               f"Во время блокировки вы не можете:\n" \
               f"• Создавать анкеты\n" \
               f"• Искать игроков\n" \
               f"• Ставить лайки\n" \
               f"• Просматривать лайки и матчи"

        await bot.send_message(
            chat_id=user_id,
            text=text
        )
        logger.info(f"📨 Уведомление о бане отправлено {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о бане: {e}")

async def notify_user_unbanned(bot: Bot, user_id: int):
    try:
        text = "✅ Блокировка снята! Теперь вы можете снова пользоваться ботом."

        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])

        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=keyboard
        )
        logger.info(f"📨 Уведомление о снятии бана отправлено {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о снятии бана: {e}")