from config import settings
import re

def is_valid_profile_url(game: str, url: str) -> bool:
    """Проверка, соответствует ли ссылка нужному сервису"""

    if game == 'dota':
        pattern = r'^(https?://)?(www\.)?dotabuff\.com/players/\d+(/.*)?$'
        return bool(re.match(pattern, url))

    elif game == 'cs':
        pattern = r'^(https?://)?(www\.)?faceit\.com/.+/players/[^/]+(/.*)?$'
        return bool(re.match(pattern, url))

    return False

def validate_profile_input(field: str, value, game: str = None) -> tuple[bool, str]:
    """Валидация ввода при создании профиля"""
    if field == 'name':
        if len(value) < 2 or len(value) > settings.MAX_NAME_LENGTH:
            return False, f"Имя должно быть от 2 до {settings.MAX_NAME_LENGTH} символов"
        if len(value.split()) != 2:
            return False, "Введите имя и фамилию"

    elif field == 'nickname':
        if len(value) < 2 or len(value) > settings.MAX_NICKNAME_LENGTH:
            return False, f"Никнейм должен быть от 2 до {settings.MAX_NICKNAME_LENGTH} символов"

    elif field == 'age':
        try:
            age = int(value)
            if age < settings.MIN_AGE:
                return False, f"Возраст должен быть больше {settings.MIN_AGE}"
            if age > settings.MAX_AGE:
                return False, f"Возраст должен быть меньше {settings.MIN_AGE}"
        except ValueError:
            return False, "Введите число"

    elif field == 'info':
        if len(value) > settings.MAX_INFO_LENGTH:
            return False, f"Слишком длинный текст (максимум {settings.MAX_INFO_LENGTH} символов)"

    elif field == 'profile_url':
        if not value.strip():
            return True, ""

        url = value.strip()

        if not is_valid_profile_url(game, url):
            return False, "Некорректная ссылка"

        if len(url) > 200:
            return False, "Ссылка слишком длинная (максимум 200 символов)"

    return True, ""