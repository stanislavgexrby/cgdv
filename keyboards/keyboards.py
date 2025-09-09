from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List
import config.settings as settings

def game_selection() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Dota 2", callback_data="game_dota")],
        [InlineKeyboardButton(text="🔫 CS2", callback_data="game_cs")]
    ])

def main_menu(has_profile: bool = False, current_game: str = None) -> InlineKeyboardMarkup:
    buttons = []

    if has_profile:
        buttons.extend([
            [InlineKeyboardButton(text="👤 Моя анкета", callback_data="view_profile")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_profile")],
            [InlineKeyboardButton(text="🔍 Поиск", callback_data="search")],
            [InlineKeyboardButton(text="❤️ Лайки", callback_data="my_likes")],
            [InlineKeyboardButton(text="💖 Матчи", callback_data="my_matches")],
            [InlineKeyboardButton(text="🗑️ Удалить анкету", callback_data="delete_profile")]
        ])
    else:
        buttons.append([InlineKeyboardButton(text="📝 Создать анкету", callback_data="create_profile")])

    if current_game:
        other_game = "cs" if current_game == "dota" else "dota"
        other_name = settings.GAMES[other_game]
        buttons.append([InlineKeyboardButton(text=f"🔄 {other_name}", callback_data=f"switch_{other_game}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def ratings(game: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, name in settings.RATINGS[game].items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"rating_{key}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def positions(game: str, selected: List[str] = None) -> InlineKeyboardMarkup:
    if selected is None:
        selected = []

    buttons = []
    for key, name in settings.POSITIONS[game].items():
        if key in selected:
            text = f"✅ {name}"
            callback = f"pos_remove_{key}"
        else:
            text = f"❌ {name}"
            callback = f"pos_add_{key}"

        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])

    # buttons.append([InlineKeyboardButton(text="──────────", callback_data="separator")])

    if selected:
        buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="pos_done")])
    else:
        buttons.append([InlineKeyboardButton(text="⚠️ Выберите позицию", callback_data="pos_need")])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def search_filters() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Начать поиск", callback_data="start_search")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="filter_rating")],
        [InlineKeyboardButton(text="⚔️ Позиция", callback_data="filter_position")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def profile_actions(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{user_id}"),
            InlineKeyboardButton(text="👎 Пропустить", callback_data=f"skip_{user_id}")
        ],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def like_actions(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк в ответ", callback_data=f"like_back_{user_id}"),
            InlineKeyboardButton(text="👎 Пропустить", callback_data=f"skip_like_{user_id}")
        ],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def skip_photo() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_photo")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def cancel_profile_creation() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def confirm_delete() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="confirm_delete"),
            InlineKeyboardButton(text="❌ Нет", callback_data="main_menu")
        ]
    ])

def back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def back_to_editing() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактирование", callback_data="edit_profile")]
    ])

def back_to_search() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Поиск", callback_data="search")]
    ])

def contact(username: str = None) -> InlineKeyboardMarkup:
    buttons = []

    if username:
        buttons.append([InlineKeyboardButton(text="💬 Написать", url=f"https://t.me/{username}")])

    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def edit_profile_menu() -> InlineKeyboardMarkup:
    """Основное меню редактирования профиля"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Изменить имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="🎮 Изменить никнейм", callback_data="edit_nickname")],
        [InlineKeyboardButton(text="🎂 Изменить возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="🏆 Изменить рейтинг", callback_data="edit_rating")],
        [InlineKeyboardButton(text="⚔️ Изменить позиции", callback_data="edit_positions")],
        [InlineKeyboardButton(text="📝 Изменить описание", callback_data="edit_info")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="🔄 Создать заново", callback_data="create_profile")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def cancel_edit() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены редактирования"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ])

def edit_photo_menu() -> InlineKeyboardMarkup:
    """Клавиатура для редактирования фото"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить фото", callback_data="delete_photo")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ])

def position_filter_menu(game: str) -> InlineKeyboardMarkup:
    """Клавиатура для выбора фильтра по позиции"""
    buttons = []
    for key, name in settings.POSITIONS[game].items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"pos_filter_{key}")])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_filter")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def subscribe_channel_keyboard(game: str, from_switch: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой подписки на канал для конкретной игры"""
    if game == "dota":
        channel = settings.DOTA_CHANNEL
        button_text = "📢 Подписаться на Dota 2 канал"
    elif game == "cs":
        channel = settings.CS_CHANNEL
        button_text = "📢 Подписаться на CS2 канал"
    else:
        return back()
    
    # Убираем @ из начала, если есть, для формирования URL
    channel_username = channel.lstrip('@')
    
    buttons = [
        [InlineKeyboardButton(text=button_text, url=f"https://t.me/{channel_username}")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data=f"game_{game}")]
    ]
    
    # Разные callback_data для кнопки "Назад" в зависимости от контекста
    if from_switch:
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    else:
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_games")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)