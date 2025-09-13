import config.settings as settings

def format_profile(user: dict, show_contact: bool = False) -> str:
    if not user:
        return "❌ Профиль не найден"

    game = user.get('current_game') or user.get('game', 'dota')

    text = f"👤 {user['name']}\n"
    text += f"🎮 {user['nickname']}\n"
    text += f"🎂 {user['age']} лет\n"

    rating = user['rating']
    if rating == 'any':
        text += f"🏆 Любой рейтинг\n"
    elif rating in settings.RATINGS.get(game, {}):
        rating = settings.RATINGS[game][rating]
        text += f"🏆 {rating}\n"
    else:
        text += f"🏆 {rating}\n"

    region = user.get('region', '')
    if region == 'any':
        text += f"🌍 Любой регион\n"
    elif region and region in settings.REGIONS:
        text += f"🌍 {settings.REGIONS[region]}\n"

    if user['positions']:
        if 'any' in user['positions']:
            text += f"⚔️ Любая позиция\n"
        else:
            positions_text = []
            for pos in user['positions']:
                if pos in settings.POSITIONS.get(game, {}):
                    positions_text.append(settings.POSITIONS[game][pos])
                else:
                    positions_text.append(pos)
            text += f"⚔️ {', '.join(positions_text)}\n"

    if user.get('additional_info'):
        text += f"\n📝 {user['additional_info']}\n"

    if show_contact and user.get('username'):
        text += f"\n💬 @{user['username']}"

    return text

WELCOME = """🎮 Добро пожаловать в TeammateBot!

Этот бот поможет найти сокомандников для Dota 2 и CS2.

У каждой игры будет своя отдельная анкета.

Выберите игру:"""

PROFILE_CREATED = "✅ Анкета создана! Теперь можете искать сокомандников."

PROFILE_UPDATED = "✅ Анкета обновлена!"

PROFILE_DELETED = "🗑️ Анкета удалена!"

LIKE_SENT = "❤️ Лайк отправлен! Если игрок лайкнет вас в ответ, вы увидите его контакты."

MATCH_CREATED = "🎉 Это матч! 💖\n\nВы понравились друг другу!"

NO_PROFILES = "😔 Анкеты не найдены. Попробуйте изменить фильтры или зайти позже."

NEW_LIKE = "❤️ Кто-то лайкнул вашу анкету! Зайдите в 'Лайки' чтобы посмотреть."

QUESTIONS = {
    "name": "👤 Введите ваше имя и фамилию:",
    "nickname": "🎮 Введите игровой никнейм:",
    "age": "🎂 Возраст:",
    "info": "📝 Расскажите о себе или нажмите 'Пропустить':",
    "photo": "📸 Отправьте фото или нажмите 'Пропустить':"
}

PROFILE_DELETED_BY_ADMIN = "⚠️ Ваша анкета была удалена модератором из-за нарушения правил сообщества.\n\nВы можете создать новую анкету, соблюдая правила."

USER_BANNED = "🚫 Вы заблокированы до {until_date} за нарушение правил сообщества.\n\nВо время блокировки вы не можете:\n• Создавать анкеты\n• Искать игроков\n• Ставить лайки\n• Просматривать лайки и матчи"

USER_UNBANNED = "✅ Блокировка снята! Теперь вы можете снова пользоваться ботом."