import html
import config.settings as settings


def format_age(age: int) -> str:
    """Правильное склонение слова 'год' в зависимости от возраста"""
    if 11 <= age % 100 <= 19:
        return f"{age} лет"
    elif age % 10 == 1:
        return f"{age} год"
    elif 2 <= age % 10 <= 4:
        return f"{age} года"
    else:
        return f"{age} лет"
    
def format_profile(user: dict, show_contact: bool = False) -> str:
    if not user:
        return "Профиль не найден"

    game = user.get('current_game') or user.get('game', 'dota')
    role = user.get('role', 'player')  # ← ДОБАВИТЬ

    # Экранируем пользовательские данные
    name = html.escape(user['name'])
    nickname = html.escape(user['nickname'])

    profile_url = user.get('profile_url')
    if profile_url and profile_url.strip():
        # URL не экранируем в атрибуте href, но nickname экранируем
        nickname_with_link = f"<a href='{profile_url}'>{nickname}</a>"
    else:
        nickname_with_link = nickname

    # Имя с ссылкой на профиль в игре
    gender = user.get('gender')
    gender_text = settings.GENDERS.get(gender, '') if gender else ''
    if gender_text:
        text = f"{name} <b>{nickname_with_link}</b>, {gender_text}, {format_age(user['age'])}\n\n"
    else:
        text = f"{name} <b>{nickname_with_link}</b>, {format_age(user['age'])}\n\n"

    if role != 'player':
        # Для тренера/менеджера: только страна, описание
        role_name = settings.ROLES.get(role, 'Игрок')
        text += f"<b>Роль:</b> {role_name}\n"
        region = user.get('region', '')
        if region == 'any':
            text += f"<b>Страна:</b> Не указана\n"
        elif region in settings.MAIN_COUNTRIES:
            text += f"<b>Страна:</b> {settings.MAIN_COUNTRIES[region]}\n"
        elif region in settings.COUNTRIES_DICT:
            text += f"<b>Страна:</b> {settings.COUNTRIES_DICT[region]}\n"
        else:
            text += f"<b>Страна:</b> {region}\n"

        # Описание
        if user.get('additional_info'):
            additional_info = html.escape(user['additional_info'])
            text += f"\n{additional_info}\n"

        # Контакт
        if show_contact:
            username = user.get('username')
            if username:
                text += f"\n💬 <a href='https://t.me/{username}'>Написать</a>"
            else:
                text += f"\n💬 Контакт: нет username"

        return text

    # ← ДЛЯ ИГРОКОВ: показываем полную информацию (как было раньше)
    
    # Рейтинг
    rating = user['rating']
    if rating == 'any':
        rating_text = f"<b>Рейтинг:</b> Не указан"
    elif rating in settings.RATINGS.get(game, {}):
        rating_desc = settings.RATINGS[game][rating]
        rating_text = f"<b>Рейтинг:</b> {rating_desc}"
    else:
        rating_text = f"<b>Рейтинг:</b> {rating}"

    text += f"{rating_text}\n"

    # Позиция
    if user['positions']:
        if 'any' in user['positions']:
            text += f"<b>Позиция:</b> Не указана\n"
        else:
            positions_text = []
            for pos in user['positions']:
                if pos in settings.POSITIONS.get(game, {}):
                    positions_text.append(settings.POSITIONS[game][pos])
                else:
                    positions_text.append(pos)
            text += f"<b>Позиция:</b> {', '.join(positions_text)}\n"

    # Цели
    if user.get('goals'):
        if 'any' in user['goals']:
            text += f"<b>Цель:</b> Не указана\n"
        else:
            goals_text = []
            for goal in user['goals']:
                if goal in settings.GOALS:
                    goals_text.append(settings.GOALS[goal])
                else:
                    goals_text.append(goal)
            text += f"<b>Цель:</b> {', '.join(goals_text)}\n"

    # Страна
    region = user.get('region', '')
    if region == 'any':
        text += f"<b>Страна:</b> Не указана\n"
    elif region in settings.MAIN_COUNTRIES:
        text += f"<b>Страна:</b> {settings.MAIN_COUNTRIES[region]}\n"
    elif region in settings.COUNTRIES_DICT:
        text += f"<b>Страна:</b> {settings.COUNTRIES_DICT[region]}\n"
    else:
        text += f"<b>Страна:</b> {region}\n"

    # Описание
    if user.get('additional_info'):
        additional_info = html.escape(user['additional_info'])
        text += f"\n{additional_info}\n"

    # Контакт
    if show_contact:
        username = user.get('username')
        if username:
            # username используется в URL, но не экранируется в атрибуте href
            text += f"\n💬 <a href='https://t.me/{username}'>Написать</a>"
        else:
            text += f"\n💬 Контакт: нет username"

    return text

WELCOME = """<b>ДОБРО ПОЖАЛОВАТЬ В Cardigans Gaming Team Finder</b>

Этот бот поможет найти сокомандников для Dota 2 и CS2

<b>Примечание:</b>
<blockquote>• У каждой игры будет своя отдельная анкета

• Контакт поддержки расположен в описании бота</blockquote>

<b>Выберите игру:</b>"""

COMMUNITY_RULES_SIMPLE = """<b>Важная информация</b>

Создавая анкету или используя бота, Вы соглашаетесь с <b><a href='https://docs.google.com/document/d/1omGgDsIxHStXpY_i21LZwQgN-qtcLAScF7OJpwYGqcA/edit?usp=sharing'>правилами сообщества</a></b>

Также Вы можете воспользоваться <b><a href='https://t.me/feedbackcgteamfinder'>Feedback CG Team Finder</a></b>, если у вас есть жалобы или предложения"""

PROFILE_CREATED = "Анкета создана! Теперь можете искать сокомандников"

PROFILE_UPDATED = "Анкета обновлена"

PROFILE_DELETED = "Анкета удалена"

LIKE_SENT = "Лайк отправлен! Если игрок лайкнет Вас в ответ, вы увидите его контакты"

MATCH_CREATED = "Это мэтч\n\nВы понравились друг другу"

NO_PROFILES = "Анкеты не найдены! Попробуйте изменить фильтры или зайти позже"

NEW_LIKE = "Кто-то лайкнул Вашу анкету! Зайдите в «Лайки» чтобы посмотреть"

QUESTIONS = {
    "name": "Введите Ваше имя:",
    "nickname": "Введите игровой никнейм:",
    "age": "Введите Ваш возраст (полных лет):",
    "region": "Выберите страну:",
    "info": """Расскажите о себе (или нажмите 'Пропустить'):

Например:
- Время игры: вечером после 19:00 МСК
- Опыт: играю 3 года, был в команде
- Связь: Discord, TeamSpeak""",
    "photo": "Отправьте фото:"
}

PROFILE_RECREATED = "Новая анкета создана! Старая анкета была заменена"

PROFILE_DELETED_BY_ADMIN = "Ваша анкета была удалена модератором из-за нарушения правил сообщества\n\nВы можете создать новую анкету, соблюдая правила"

USER_BANNED = "Вы заблокированы до {until_date} за нарушение правил сообщества\n\nВо время блокировки Вы не можете:\n• Создавать анкеты\n• Искать игроков\n• Ставить лайки\n• Просматривать лайки и мэтчи"

USER_UNBANNED = "Блокировка снята! Теперь Вы можете снова пользоваться ботом"

# ==================== ОНБОРДИНГ ====================

ONBOARDING_TIPS = {
    'name': '<b>Совет:</b> Используй реальное имя или игровой никнейм, который тебе нравится',
    'nickname': '<b>Совет:</b> Укажи твой игровой никнейм, так другим будет проще тебя найти',
    'age': '<b>Совет:</b> Возраст помогает найти людей близких по возрасту',
    'rating': '<b>Совет:</b> Указывай честный рейтинг - так найдешь игроков своего уровня',
    'positions': '<b>Совет:</b> Выбери 1-3 позиции, на которых играешь лучше всего',
    'goals': '<b>Совет:</b> Цели помогают найти единомышленников. Можно выбрать несколько',
    'photo': '<b>Важно:</b> Профили с фото получают в 3 раза больше лайков\n\nМожешь загрузить своё фото или оставить стандартное',
    'info': '<b>Совет:</b> Напиши пару слов о себе:\n• Когда обычно играешь\n• Что ищешь в тиммейтах\n• Стиль игры\n\nПрофили с описанием получают на 40% больше мэтчей'
}

def get_profile_quality_score(profile: dict) -> tuple:
    """
    Возвращает (текущий балл, максимальный балл)
    Не учитываем имя и возраст - они обязательны
    Для тренеров/менеджеров используется упрощенная оценка (только 3 параметра)
    """
    role = profile.get('role', 'player')

    # Для тренеров и менеджеров упрощенная оценка
    if role in ['coach', 'manager']:
        score = 0
        max_score = 3

        # Регион
        if profile.get('region') and profile['region'] != 'any':
            score += 1

        # Описание
        if profile.get('additional_info') and profile.get('additional_info', '').strip():
            score += 1

        # Фото (только кастомное)
        photo_id = profile.get('photo_id')
        if photo_id:
            game = profile.get('game') or profile.get('current_game')
            is_default = False
            if game:
                import config.settings as settings
                default_avatar = settings.get_cached_photo_id(f'avatar_{game}')
                is_default = (default_avatar and photo_id == default_avatar)
            if not is_default:
                score += 1

        return score, max_score

    # Для игроков полная оценка (7 параметров)
    score = 0
    max_score = 7

    # Рейтинг считается заполненным, если указан и не 'any'
    if profile.get('rating') and profile['rating'] != 'any':
        score += 1

    # Позиции считаются заполненными, если есть и не ['any']
    positions = profile.get('positions', [])
    if positions and len(positions) > 0 and 'any' not in positions:
        score += 1

    # Регион считается заполненным, если указан и не 'any'
    if profile.get('region') and profile['region'] != 'any':
        score += 1

    # Цели считаются заполненными, если есть и не ['any']
    goals = profile.get('goals', [])
    if goals and len(goals) > 0 and 'any' not in goals:
        score += 1

    # Описание считается заполненным, если не пустое
    if profile.get('additional_info') and profile.get('additional_info', '').strip():
        score += 1

    # Ссылка на профиль (Dotabuff/Faceit)
    if profile.get('profile_url') and profile['profile_url'].strip():
        score += 1

    # Фото (только кастомное, не дефолтное)
    photo_id = profile.get('photo_id')
    if photo_id:
        # Проверяем, не является ли фото дефолтным
        game = profile.get('game') or profile.get('current_game')
        is_default = False

        if game:
            import config.settings as settings
            default_avatar = settings.get_cached_photo_id(f'avatar_{game}')
            is_default = (default_avatar and photo_id == default_avatar)

        # Засчитываем только если НЕ дефолтное
        if not is_default:
            score += 1

    return score, max_score

def format_profile_quality(profile: dict) -> str:
    """Форматирование качества профиля с прогресс-баром"""
    score, max_score = get_profile_quality_score(profile)
    percentage = int((score / max_score) * 100)

    # Прогресс-бар
    filled = '█' * (score * 2)
    empty = '░' * ((max_score - score) * 2)

    quality_text = f"\n<b>Заполненность профиля:</b> {score}/{max_score}\n{filled}{empty} {percentage}%"

    # Добавляем мотивационный текст
    if score < 4:
        quality_text += "\n<i>Заполни профиль для большего количества лайков</i>"
    elif score < 6:
        quality_text += "\n<i>Хороший профиль! Добавь еще пару деталей</i>"
    else:
        quality_text += "\n<i>Отличный профиль</i>"

    # Подсказки, что можно улучшить
    missing = []
    role = profile.get('role', 'player')

    # Для тренеров/менеджеров упрощенный список
    if role in ['coach', 'manager']:
        # Проверяем регион
        if not profile.get('region') or profile.get('region') == 'any':
            missing.append("Укажи страну")

        # Проверяем описание
        if not profile.get('additional_info') or not profile.get('additional_info', '').strip():
            missing.append("Напиши о себе")

        # Проверяем фото
        photo_id = profile.get('photo_id')
        has_custom_photo = False
        if photo_id:
            game = profile.get('game') or profile.get('current_game')
            if game:
                import config.settings as settings
                default_avatar = settings.get_cached_photo_id(f'avatar_{game}')
                has_custom_photo = not (default_avatar and photo_id == default_avatar)

        if not has_custom_photo:
            missing.append("Добавь своё фото")

    else:
        # Для игроков полный список
        # Проверяем рейтинг
        if not profile.get('rating') or profile.get('rating') == 'any':
            missing.append("Укажи рейтинг")

        # Проверяем позиции
        positions = profile.get('positions', [])
        if not positions or len(positions) == 0 or 'any' in positions:
            missing.append("Укажи позиции")

        # Проверяем регион
        if not profile.get('region') or profile.get('region') == 'any':
            missing.append("Укажи страну")

        # Проверяем цели
        goals = profile.get('goals', [])
        if not goals or len(goals) == 0 or 'any' in goals:
            missing.append("Укажи цели")

        # Проверяем описание
        if not profile.get('additional_info') or not profile.get('additional_info', '').strip():
            missing.append("Напиши о себе")

        # Проверяем ссылку на профиль
        if not profile.get('profile_url') or not profile['profile_url'].strip():
            missing.append("Добавь ссылку на профиль")

        # Проверяем фото (только кастомное, не дефолтное)
        photo_id = profile.get('photo_id')
        has_custom_photo = False
        if photo_id:
            game = profile.get('game') or profile.get('current_game')
            if game:
                import config.settings as settings
                default_avatar = settings.get_cached_photo_id(f'avatar_{game}')
                # Считаем кастомным, если фото есть И оно не дефолтное
                has_custom_photo = not (default_avatar and photo_id == default_avatar)

        if not has_custom_photo:
            missing.append("Добавь своё фото")

    if missing and score < max_score:
        quality_text += f"\n\n<b>Можно улучшить:</b>\n• " + "\n• ".join(missing)

    return quality_text
