# utils/texts.py
"""
Тексты для бота
"""

import config.settings as settings

def format_profile(user: dict) -> str:
    """Форматирование профиля"""
    game = user.get('current_game') or user.get('game', 'dota')
    
    text = f"👤 {user['name']}\n"
    text += f"🎮 {user['nickname']}\n"
    text += f"🎂 {user['age']} лет\n"
    
    # Рейтинг
    rating = user['rating']
    if rating in settings.RATINGS.get(game, {}):
        rating = settings.RATINGS[game][rating]
    text += f"🏆 {rating}\n"
    
    # Позиции
    if user['positions']:
        positions_text = []
        for pos in user['positions']:
            if pos in settings.POSITIONS.get(game, {}):
                positions_text.append(settings.POSITIONS[game][pos])
            else:
                positions_text.append(pos)
        text += f"⚔️ {', '.join(positions_text)}\n"
    
    # Дополнительная информация
    if user.get('additional_info'):
        text += f"\n📝 {user['additional_info']}\n"
    
    # Контакт
    if user.get('username'):
        text += f"\n💬 @{user['username']}"
    
    return text

# Основные тексты
WELCOME = """🎮 Добро пожаловать в TeammateBot!

Этот бот поможет найти сокомандников для Dota 2 и CS2.

Выберите игру:"""

PROFILE_CREATED = "✅ Анкета создана! Теперь можете искать сокомандников."

PROFILE_UPDATED = "✅ Анкета обновлена!"

PROFILE_DELETED = "🗑️ Анкета удалена!"

LIKE_SENT = "❤️ Лайк отправлен! Если игрок лайкнет вас в ответ, вы увидите его контакты."

MATCH_CREATED = "🎉 Это матч! 💖\n\nВы понравились друг другу!"

NO_PROFILES = "😔 Анкеты не найдены. Попробуйте изменить фильтры или зайти позже."

NEW_LIKE = "❤️ Кто-то лайкнул вашу анкету! Зайдите в 'Лайки' чтобы посмотреть."

# Вопросы для создания анкеты
QUESTIONS = {
    "name": "👤 Введите ваше имя и фамилию:",
    "nickname": "🎮 Введите игровой никнейм:",
    "age": "🎂 Возраст (16-50):",
    "info": "📝 Расскажите о себе (или отправьте '-' чтобы пропустить):",
    "photo": "📸 Отправьте фото или нажмите 'Пропустить':"
}