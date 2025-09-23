import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import re

import config.settings as settings
import keyboards.keyboards as kb

from handlers.profile_enum import ProfileStep, get_step_question_text

logger = logging.getLogger(__name__)
router = Router()

def is_valid_profile_url(game: str, url: str) -> bool:
    """Проверка, соответствует ли ссылка нужному сервису"""

    if game == 'dota':
        pattern = r'^(https?://)?(www\.)?dotabuff\.com/players/\d{8,12}(/.*)?$'
        return bool(re.match(pattern, url))

    elif game == 'cs':
        pattern = r'^(https?://)?(www\.)?faceit\.com/.+/players/[^/]+(/.*)?$'
        return bool(re.match(pattern, url))

    return False

def validate_profile_input(field: str, value, game: str = None) -> tuple[bool, str]:
    if field == 'name':
        if len(value) < 2 or len(value) > settings.MAX_NAME_LENGTH:
            return False, f"Имя должно быть от 2 до {settings.MAX_NAME_LENGTH} символов"

        if len(value.split()) != 1:
            return False, "Имя должно быть одним словом (без пробелов)"

    elif field == 'nickname':
        if len(value) < 2 or len(value) > settings.MAX_NICKNAME_LENGTH:
            return False, f"Никнейм должен быть от 2 до {settings.MAX_NICKNAME_LENGTH} символов"

    elif field == 'age':
        try:
            age = int(value)
            if age < settings.MIN_AGE:
                return False, f"Возраст должен быть больше {settings.MIN_AGE}"
            if age > settings.MAX_AGE:
                return False, f"Возраст должен быть меньше {settings.MAX_AGE}"
        except ValueError:
            return False, "Введите число"

    elif field == 'info':
        if len(value) > settings.MAX_INFO_LENGTH:
            return False, f"Слишком длинный текст (максимум {settings.MAX_INFO_LENGTH} символов)"

    elif field == 'profile_url':
            if not value.strip():
                return True, ""

            url = value.strip()

            if game == 'dota' and 'dotabuff.com/players/' in url:
                if url.rstrip('/').endswith('/players'):
                    return False, ("Неполная ссылка на Dotabuff. Добавьте ваш Player ID\n\n"
                                "Пример: https://www.dotabuff.com/players/123456789\n\n"
                                "Найти ID можно в URL вашего профиля на Dotabuff")

            if not is_valid_profile_url(game, url):
                if game == 'dota':
                    return False, ("Некорректная ссылка на Dotabuff\n\n"
                                "Правильный формат: https://www.dotabuff.com/players/123456789\n\n"
                                "Где 123456789 - ваш Player ID")
                elif game == 'cs':
                    return False, ("Некорректная ссылка на FACEIT.\n\n"
                                "Пример: https://www.faceit.com/en/players/nickname")
                else:
                    return False, "Некорректная ссылка"

            if len(url) > 200:
                return False, "Ссылка слишком длинная (максимум 200 символов)"

    return True, ""

async def show_validation_error(message: Message, state: FSMContext, error_text: str):
    """Показ ошибки валидации в том же сообщении"""
    data = await state.get_data()
    current_step = data.get('current_step', 'name')
    
    try:
        await message.delete()
    except Exception:
        pass
    
    try:
        current_step_enum = ProfileStep(current_step)
        question_text = await get_step_question_text(current_step_enum, data, False)
    except Exception:
        question_text = "Попробуйте еще раз:"
    
    text = f"{question_text}\n\n❌ {error_text}"
    
    if current_step == 'name':
        keyboard = kb.profile_creation_navigation("name", False)
    elif current_step == 'nickname':
        keyboard = kb.profile_creation_navigation("nickname", False)
    elif current_step == 'age':
        keyboard = kb.profile_creation_navigation("age", False)
    elif current_step == 'profile_url':
        keyboard = kb.skip_profile_url()
    elif current_step == 'additional_info':
        keyboard = kb.skip_info()
    elif current_step == 'photo':
        keyboard = kb.skip_photo()
    else:
        keyboard = kb.profile_creation_navigation(current_step, False)
    
    bot = message.bot
    chat_id = message.chat.id
    last_message_id = data.get('last_bot_message_id')
    
    if last_message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=last_message_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Не удалось показать ошибку в сообщении {last_message_id}: {e}")
    else:
        logger.error("Нет last_bot_message_id для показа ошибки валидации")