# keyboards/keyboards.py
"""
Простые клавиатуры для бота
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List
import config.settings as settings

def game_selection() -> InlineKeyboardMarkup:
    """Выбор игры"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Dota 2", callback_data="game_dota")],
        [InlineKeyboardButton(text="🔫 CS2", callback_data="game_cs")]
    ])

def main_menu(has_profile: bool = False, current_game: str = None) -> InlineKeyboardMarkup:
    """Главное меню"""
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
    
    # Переключение игры
    if current_game:
        other_game = "cs" if current_game == "dota" else "dota"
        other_name = settings.GAMES[other_game]
        buttons.append([InlineKeyboardButton(text=f"🔄 {other_name}", callback_data=f"switch_{other_game}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def ratings(game: str) -> InlineKeyboardMarkup:
    """Выбор рейтинга"""
    buttons = []
    for key, name in settings.RATINGS[game].items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"rating_{key}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def positions(game: str, selected: List[str] = None) -> InlineKeyboardMarkup:
    """Выбор позиций"""
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
    
    # Кнопки управления
    buttons.append([InlineKeyboardButton(text="──────────", callback_data="separator")])
    
    if selected:
        buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="pos_done")])
    else:
        buttons.append([InlineKeyboardButton(text="⚠️ Выберите позицию", callback_data="pos_need")])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def search_filters() -> InlineKeyboardMarkup:
    """Фильтры поиска"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="filter_rating")],
        [InlineKeyboardButton(text="⚔️ Позиция", callback_data="filter_position")],
        [InlineKeyboardButton(text="🔍 Начать поиск", callback_data="start_search")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def profile_actions(user_id: int) -> InlineKeyboardMarkup:
    """Действия с профилем в поиске"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👎 Пропустить", callback_data=f"skip_{user_id}"),
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{user_id}")
        ],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def like_actions(user_id: int) -> InlineKeyboardMarkup:
    """Действия с лайком"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк в ответ", callback_data=f"like_back_{user_id}"),
            InlineKeyboardButton(text="👎 Пропустить", callback_data=f"skip_like_{user_id}")
        ],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def skip_photo() -> InlineKeyboardMarkup:
    """Пропустить фото"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_photo")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

def confirm_delete() -> InlineKeyboardMarkup:
    """Подтверждение удаления"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="confirm_delete"),
            InlineKeyboardButton(text="❌ Нет", callback_data="main_menu")
        ]
    ])

def back() -> InlineKeyboardMarkup:
    """Назад в главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def contact(username: str = None) -> InlineKeyboardMarkup:
    """Связаться с пользователем"""
    buttons = []
    
    if username:
        buttons.append([InlineKeyboardButton(text="💬 Написать", url=f"https://t.me/{username}")])
    
    buttons.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)