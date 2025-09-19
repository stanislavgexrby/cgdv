import config.settings as settings

def format_profile(user: dict, show_contact: bool = False) -> str:
    if not user:
        return "Профиль не найден."

    game = user.get('current_game') or user.get('game', 'dota')

    name_parts = user['name'].split()
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:])
        profile_url = user.get('profile_url')
        if profile_url and profile_url.strip():
            text = f"{first_name} <a href='{profile_url}'><b>{user['nickname']}</b></a> {last_name}, {user['age']} лет\n\n"
        else:
            text = f"{first_name} <b>{user['nickname']}</b> {last_name}, {user['age']} лет\n\n"
    else:
        text = f"<b>{user['name']}</b> <b>{user['nickname']}</b>, {user['age']} лет\n\n"

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

    # Регион
    region = user.get('region', '')
    if region == 'any':
        text += f"<b>Регион:</b> Не указан\n"
    elif region and region in settings.REGIONS:
        text += f"<b>Регион:</b> {settings.REGIONS[region]}\n"

    # Дополнительная информация
    if user.get('additional_info'):
        text += f"\n{user['additional_info']}\n"

    # Контакт
    if show_contact and user.get('username'):
        text += f"\n<b>Контакт:</b> @{user['username']}"

    return text

WELCOME = """<b>ДОБРО ПОЖАЛОВАТЬ В CG TEAMUP</b>

Этот бот поможет найти сокомандников для Dota 2 и CS2.

<b>Примечание:</b>
<blockquote>• У каждой игры будет своя отдельная анкета

• Контакт поддержки расположен в описании бота</blockquote>

<b>Выберите игру:</b>"""

PROFILE_CREATED = "Анкета создана. Теперь можете искать сокомандников."

PROFILE_UPDATED = "Анкета обновлена."

PROFILE_DELETED = "Анкета удалена."

LIKE_SENT = "Лайк отправлен. Если игрок лайкнет Вас в ответ, вы увидите его контакты."

MATCH_CREATED = "Это матч.\n\nВы понравились друг другу."

NO_PROFILES = "Анкеты не найдены. Попробуйте изменить фильтры или зайти позже."

NEW_LIKE = "Кто-то лайкнул Вашу анкету. Зайдите в «Лайки» чтобы посмотреть."

QUESTIONS = {
    "name": "Введите Ваше имя и фамилию:",
    "nickname": "Введите игровой никнейм:",
    "age": "Введите Ваш возраст (полных лет):",
    "info": """Расскажите о себе (или нажмите «Пропустить»):

Например:
- Время игры: вечером после 19:00 МСК
- Опыт: играю 3 года, был в команде
- Связь: Discord, TeamSpeak""",
    "photo": "Отправьте фото или нажмите «Пропустить»:"
}

PROFILE_RECREATED = "Новая анкета создана! Старая анкета была заменена."

PROFILE_DELETED_BY_ADMIN = "Ваша анкета была удалена модератором из-за нарушения правил сообщества.\n\nВы можете создать новую анкету, соблюдая правила."

USER_BANNED = "Вы заблокированы до {until_date} за нарушение правил сообщества.\n\nВо время блокировки Вы не можете:\n• Создавать анкеты\n• Искать игроков\n• Ставить лайки\n• Просматривать лайки и мтчи"

USER_UNBANNED = "Блокировка снята. Теперь Вы можете снова пользоваться ботом."