from config import settings
import re

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

    elif field == 'profile_url':
        if not value.strip():
            return True, ""

        url = value.strip()

        if game == 'dota' and 'dotabuff.com/players/' in url:
            if url.rstrip('/').endswith('/players'):
                return False, ("Неполная ссылка на Dotabuff. Добавьте ваш Player ID.\n\n"
                             "Пример: https://www.dotabuff.com/players/123456789\n\n"
                             "Найти ID можно в URL вашего профиля на Dotabuff")

        if not is_valid_profile_url(game, url):
            if game == 'dota':
                return False, ("Некорректная ссылка на Dotabuff.\n\n"
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