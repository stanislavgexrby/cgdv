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
            [InlineKeyboardButton(text="🔍 Поиск", callback_data="search")],
            [InlineKeyboardButton(text="👤 Моя анкета", callback_data="edit_profile")],
            [InlineKeyboardButton(text="❤️ Лайки", callback_data="my_likes")],
            [InlineKeyboardButton(text="💖 Матчи", callback_data="my_matches")]
        ])
    else:
        buttons.append([InlineKeyboardButton(text="📝 Создать анкету", callback_data="create_profile")])

    if current_game:
        other_game = "cs" if current_game == "dota" else "dota"
        other_name = settings.GAMES[other_game]
        buttons.append([InlineKeyboardButton(text=f"🔄 {other_name}", callback_data=f"switch_{other_game}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def ratings(game: str, for_profile: bool = True, with_cancel: bool = False) -> InlineKeyboardMarkup:
    buttons = []

    for key, name in settings.RATINGS[game].items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"rating_{key}")])

    if for_profile:
        buttons.append([InlineKeyboardButton(text="Любой рейтинг", callback_data="rating_any")])

    if with_cancel:
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def regions(for_profile: bool = True, with_cancel: bool = False) -> InlineKeyboardMarkup:
    buttons = []

    for key, name in settings.REGIONS.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"region_{key}")])

    if for_profile:
        buttons.append([InlineKeyboardButton(text="Любой регион", callback_data="region_any")])

    if with_cancel:
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def positions(game: str, selected: List[str] = None, for_profile: bool = True) -> InlineKeyboardMarkup:
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

    if for_profile and not selected:
        buttons.append([InlineKeyboardButton(text="Любая позиция", callback_data="pos_any")])

    if selected:
        buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="pos_done")])
    elif for_profile:
        buttons.append([InlineKeyboardButton(text="⚠️ Выберите позицию", callback_data="pos_need")])
    else:
        buttons.append([InlineKeyboardButton(text="⚠️ Выберите позицию", callback_data="pos_need")])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def search_filters() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Начать поиск", callback_data="start_search")],
        [InlineKeyboardButton(text="🏆 Рейтинг", callback_data="filter_rating")],
        [InlineKeyboardButton(text="⚔️ Позиция", callback_data="filter_position")],
        [InlineKeyboardButton(text="🌍 Регион", callback_data="filter_region")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def regions_filter() -> InlineKeyboardMarkup:
    buttons = []

    for key, name in settings.REGIONS.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"region_filter_{key}")])

    buttons.append([InlineKeyboardButton(text="🔄 Сбросить фильтр", callback_data="region_reset")])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_filter")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def ratings_filter(game: str) -> InlineKeyboardMarkup:
    buttons = []

    for key, name in settings.RATINGS[game].items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"rating_{key}")])

    buttons.append([InlineKeyboardButton(text="🔄 Сбросить фильтр", callback_data="rating_reset")])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_filter")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def profile_actions(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{user_id}"),
            InlineKeyboardButton(text="👎 Пропустить", callback_data=f"skip_{user_id}")
        ],
        [InlineKeyboardButton(text="🚩 Пожаловаться", callback_data=f"report_{user_id}")],
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

def skip_info() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_info")],
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

def edit_info_menu() -> InlineKeyboardMarkup:
    """Клавиатура для редактирования описания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить описание", callback_data="delete_info")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ])

def back_to_editing() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Редактирование", callback_data="back_to_editing")]
    ])

def back_to_search() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск", callback_data="back_to_search")]
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
        [InlineKeyboardButton(text="🌍 Изменить регион", callback_data="edit_region")],
        [InlineKeyboardButton(text="⚔️ Изменить позиции", callback_data="edit_positions")],
        [InlineKeyboardButton(text="📝 Изменить описание", callback_data="edit_info")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="🔄 Создать заново", callback_data="create_profile")],
        [InlineKeyboardButton(text="🗑️ Удалить анкету", callback_data="delete_profile")],
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

    buttons.append([InlineKeyboardButton(text="🔄 Сбросить фильтр", callback_data="position_reset")])

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

    channel_username = channel.lstrip('@')

    buttons = [
        [InlineKeyboardButton(text=button_text, url=f"https://t.me/{channel_username}")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data=f"game_{game}")]
    ]

    if from_switch:
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    else:
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_games")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_main_menu() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🚩 Жалобы", callback_data="admin_reports")],
        [InlineKeyboardButton(text="🚫 Баны", callback_data="admin_bans")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

def admin_report_actions(report_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для действий с жалобой"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑️ Удалить профиль", callback_data=f"admin_approve_{report_id}"),
            InlineKeyboardButton(text="🚫 Забанить на неделю", callback_data=f"admin_ban_{report_id}")
        ],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_dismiss_{report_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к жалобам", callback_data="admin_reports")]
    ])

def admin_back_to_reports() -> InlineKeyboardMarkup:
    """Клавиатура для возврата к списку жалоб"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к жалобам", callback_data="admin_reports")]
    ])

def admin_back_to_bans() -> InlineKeyboardMarkup:
    """Клавиатура для возврата к списку банов"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к банам", callback_data="admin_bans")]
    ])

def admin_ban_actions(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для действий с баном"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Снять бан", callback_data=f"admin_unban_{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к банам", callback_data="admin_bans")]
    ])
def admin_ban_actions_with_nav(user_id: int, current_index: int, total_count: int) -> InlineKeyboardMarkup:
    """Клавиатура для действий с баном с навигацией"""
    buttons = []

    buttons.append([InlineKeyboardButton(text="✅ Снять бан", callback_data=f"admin_unban_{user_id}")])

    if total_count > 1:
        nav_buttons = []

        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="◀️ Предыдущий", 
                callback_data=f"admin_ban_prev_{current_index}"
            ))

        if current_index < total_count - 1:
            nav_buttons.append(InlineKeyboardButton(
                text="Следующий ▶️", 
                callback_data=f"admin_ban_next_{current_index}"
            ))

        if nav_buttons:
            buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text="⬅️ Админ меню", callback_data="admin_stats")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_report_actions_with_nav(report_id: int, current_index: int, total_count: int) -> InlineKeyboardMarkup:
    buttons = []

    buttons.append([
        InlineKeyboardButton(text="🗑️ Удалить профиль", callback_data=f"admin_approve_{report_id}"),
        InlineKeyboardButton(text="🚫 Забанить", callback_data=f"admin_ban_{report_id}")
    ])
    buttons.append([InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_dismiss_{report_id}")])

    if total_count > 1:
        nav_buttons = []

        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="◀️ Предыдущая", 
                callback_data=f"admin_report_prev_{current_index}"
            ))

        if current_index < total_count - 1:
            nav_buttons.append(InlineKeyboardButton(
                text="Следующая ▶️", 
                callback_data=f"admin_report_next_{current_index}"
            ))

        if nav_buttons:
            buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text="⬅️ Админ меню", callback_data="admin_stats")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)