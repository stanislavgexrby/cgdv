from config import settings


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
        except ValueError:
            return False, "Введите число"

    elif field == 'info':
        if len(value) > settings.MAX_INFO_LENGTH:
            return False, f"Слишком длинный текст (максимум {settings.MAX_INFO_LENGTH} символов)"

    return True, ""