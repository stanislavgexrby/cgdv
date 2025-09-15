import config.settings as settings

def format_profile(user: dict, show_contact: bool = False) -> str:
    if not user:
        return "Профиль не найден."

    game = user.get('current_game') or user.get('game', 'dota')

    # Разбиваем имя на части для правильного форматирования
    name_parts = user['name'].split()
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:])
        # Формат: Жирное_имя жирный_никнейм жирная_фамилия, возраст лет
        text = f"{first_name} <b>{user['nickname']}</b> {last_name}, {user['age']} лет\n\n"
    else:
        # Если только одно имя
        text = f"<b>{user['name']}</b> <b>{user['nickname']}</b>, {user['age']} лет\n\n"

    # Рейтинг
    rating = user['rating']
    if rating == 'any':
        text += f"<b>Рейтинг:</b> Любой\n"
    elif rating in settings.RATINGS.get(game, {}):
        rating_desc = settings.RATINGS[game][rating]
        text += f"<b>Рейтинг:</b> {rating_desc}\n"
    else:
        text += f"<b>Рейтинг:</b> {rating}\n"

    # Позиция
    if user['positions']:
        if 'any' in user['positions']:
            text += f"<b>Позиция:</b> Любая\n"
        else:
            positions_text = []
            for pos in user['positions']:
                if pos in settings.POSITIONS.get(game, {}):
                    positions_text.append(settings.POSITIONS[game][pos])
                else:
                    positions_text.append(pos)
            text += f"<b>Позиция:</b> {', '.join(positions_text)}\n"

    # Регион
    region = user.get('region', '')
    if region == 'any':
        text += f"<b>Регион:</b> Любой\n"
    elif region and region in settings.REGIONS:
        text += f"<b>Регион:</b> {settings.REGIONS[region]}\n"

    # Дополнительная информация
    if user.get('additional_info'):
        text += f"\n{user['additional_info']}\n"

    # Контакт
    if show_contact and user.get('username'):
        text += f"\n<b>Контакт:</b> @{user['username']}"

    return text

WELCOME = """Добро пожаловать в TeammateBot.

Этот бот поможет найти сокомандников для Dota 2 и CS2.

У каждой игры будет своя отдельная анкета.

Выберите игру:"""

PROFILE_CREATED = "Анкета создана. Теперь можете искать сокомандников."

PROFILE_UPDATED = "Анкета обновлена."

PROFILE_DELETED = "Анкета удалена."

LIKE_SENT = "Лайк отправлен. Если игрок лайкнет вас в ответ, вы увидите его контакты."

MATCH_CREATED = "Это матч.\n\nВы понравились друг другу."

NO_PROFILES = "Анкеты не найдены. Попробуйте изменить фильтры или зайти позже."

NEW_LIKE = "Кто-то лайкнул вашу анкету. Зайдите в «Лайки» чтобы посмотреть."

QUESTIONS = {
    "name": "Введите ваше имя и фамилию:",
    "nickname": "Введите игровой никнейм:",
    "age": "Введите ваш возраст (полных лет):",
    "info": "Расскажите о себе или нажмите «Пропустить»:",
    "photo": "Отправьте фото или нажмите «Пропустить»:"
}

PROFILE_DELETED_BY_ADMIN = "Ваша анкета была удалена модератором из-за нарушения правил сообщества.\n\nВы можете создать новую анкету, соблюдая правила."

USER_BANNED = "Вы заблокированы до {until_date} за нарушение правил сообщества.\n\nВо время блокировки вы не можете:\n• Создавать анкеты\n• Искать игроков\n• Ставить лайки\n• Просматривать лайки и мтчи"

USER_UNBANNED = "Блокировка снята. Теперь вы можете снова пользоваться ботом."