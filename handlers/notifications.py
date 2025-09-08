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
        # Получаем текущую игру пользователя
        user = db.get_user(user_id)
        if not user:
            return

        game = user['current_game']
        match_profile = db.get_user_profile(match_user_id, game)

        if match_profile and match_profile.get('name'):
            # При уведомлении о матче показываем контакты
            profile_text = texts.format_profile(match_profile, show_contact=True)
            text = f"🎉 У вас новый матч!\n\n{profile_text}"
        else:
            text = "🎉 У вас новый матч!"

        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=kb.back()
        )
        logger.info(f"📨 Уведомление о матче отправлено {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о матче: {e}")

async def notify_about_like(bot: Bot, user_id: int):
    try:
        await bot.send_message(
            chat_id=user_id,
            text=texts.NEW_LIKE,
            reply_markup=kb.back()
        )
        logger.info(f"📨 Уведомление о лайке отправлено {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о лайке: {e}")