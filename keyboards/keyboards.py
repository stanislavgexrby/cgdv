from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Tuple
import config.settings as settings

# ==================== ОСНОВНЫЕ МЕНЮ ====================

def game_selection() -> InlineKeyboardMarkup:
    """Выбор игры при старте"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Dota 2", callback_data="game_dota")],
        [InlineKeyboardButton(text="🔫 CS2", callback_data="game_cs")]
    ])

def main_menu(has_profile: bool = False, current_game: str = None) -> InlineKeyboardMarkup:
    """Главное меню"""
    buttons = []

    if has_profile:
        buttons.extend([
            [InlineKeyboardButton(text="Поиск", callback_data="search")],
            [InlineKeyboardButton(text="Моя анкета", callback_data="view_profile")],
            [InlineKeyboardButton(text="Лайки", callback_data="my_likes")],
            [InlineKeyboardButton(text="Мэтчи", callback_data="my_matches")]
        ])
    else:
        buttons.append([InlineKeyboardButton(text="Создать анкету", callback_data="create_profile")])

    if current_game:
        other_game = "cs" if current_game == "dota" else "dota"
        other_name = settings.GAMES[other_game]
        buttons.append([InlineKeyboardButton(text=f"Переключить на {other_name}", callback_data=f"switch_{other_game}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def view_profile_menu() -> InlineKeyboardMarkup:
    """Меню просмотра профиля"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактировать", callback_data="edit_profile")],
        [InlineKeyboardButton(text="Создать заново", callback_data="recreate_profile")],
        [InlineKeyboardButton(text="Удалить анкету", callback_data="delete_profile")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])


def back() -> InlineKeyboardMarkup:
    """Простая кнопка назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

def subscribe_channel_keyboard(game: str, from_switch: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой подписки на канал"""
    if game == "dota":
        channel = settings.DOTA_CHANNEL
        button_text = "Подписаться на Dota 2 канал"
    elif game == "cs":
        channel = settings.CS_CHANNEL
        button_text = "Подписаться на CS2 канал"
    else:
        return back()

    channel_username = channel.lstrip('@')

    buttons = [
        [InlineKeyboardButton(text=button_text, url=f"https://t.me/{channel_username}")],
        [InlineKeyboardButton(text="Я подписался", callback_data=f"game_{game}")]
    ]

    if from_switch:
        buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_main")])
    else:
        buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_games")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def notification_ok() -> InlineKeyboardMarkup:
    """Кнопка OK для уведомлений"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Понятно", callback_data="dismiss_notification")]
    ])

# ==================== СОЗДАНИЕ И РЕДАКТИРОВАНИЕ ПРОФИЛЕЙ ====================

def ratings(game: str, for_profile: bool = True, with_cancel: bool = False) -> InlineKeyboardMarkup:
    """Выбор рейтинга"""
    buttons = []

    for key, name in settings.RATINGS[game].items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"rating_{key}")])

    if for_profile:
        buttons.append([InlineKeyboardButton(text="Любой рейтинг", callback_data="rating_any")])

    if with_cancel:
        # Для редактирования используем cancel_edit
        cancel_callback = "cancel_edit" if not for_profile else "cancel"
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data=cancel_callback)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def regions(for_profile: bool = True, with_cancel: bool = False) -> InlineKeyboardMarkup:
    """Выбор региона"""
    buttons = []

    for key, name in settings.REGIONS.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"region_{key}")])

    if for_profile:
        buttons.append([InlineKeyboardButton(text="Любой регион", callback_data="region_any")])

    if with_cancel:
        # Для редактирования используем cancel_edit
        cancel_callback = "cancel_edit" if not for_profile else "cancel"
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data=cancel_callback)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def positions(game: str, selected: List[str] = None, for_profile: bool = True, editing: bool = False) -> InlineKeyboardMarkup:
    """Выбор позиций"""
    if selected is None:
        selected = []

    buttons = []

    for key, name in settings.POSITIONS[game].items():
        if key in selected:
            text = f"✅ {name}"
            callback = f"pos_remove_{key}"
        else:
            text = f"{name}"
            callback = f"pos_add_{key}"

        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])

    if editing and "any" in selected:
        buttons.append([InlineKeyboardButton(text="✅ Любая позиция", callback_data="pos_remove_any")])

    # Кнопка "Любая позиция" для добавления
    if editing and "any" not in selected:
        buttons.append([InlineKeyboardButton(text="Любая позиция", callback_data="pos_add_any")])
    elif for_profile and not selected:
        buttons.append([InlineKeyboardButton(text="Любая позиция", callback_data="pos_any")])

    if selected:
        buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="pos_done")])
    elif for_profile:
        buttons.append([InlineKeyboardButton(text="Выберите позицию", callback_data="pos_need")])
    else:
        buttons.append([InlineKeyboardButton(text="Выберите позицию", callback_data="pos_need")])

    if editing:
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_edit")])
    else:
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def skip_photo() -> InlineKeyboardMarkup:
    """Пропуск загрузки фото"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_photo")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])

def skip_info() -> InlineKeyboardMarkup:
    """Пропуск дополнительной информации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_info")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])

def cancel_profile_creation() -> InlineKeyboardMarkup:
    """Отмена создания профиля"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])

# ==================== РЕДАКТИРОВАНИЕ ПРОФИЛЕЙ ====================

def edit_profile_menu() -> InlineKeyboardMarkup:
    """Меню редактирования профиля"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="Изменить никнейм", callback_data="edit_nickname")],
        [InlineKeyboardButton(text="Изменить возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="Изменить рейтинг", callback_data="edit_rating")],
        [InlineKeyboardButton(text="Изменить регион", callback_data="edit_region")],
        [InlineKeyboardButton(text="Изменить позиции", callback_data="edit_positions")],
        [InlineKeyboardButton(text="Изменить описание", callback_data="edit_info")],
        [InlineKeyboardButton(text="Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

def cancel_edit() -> InlineKeyboardMarkup:
    """Отмена редактирования"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_edit")]
    ])

def back_to_editing() -> InlineKeyboardMarkup:
    """Возврат к редактированию"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактирование", callback_data="back_to_editing")]
    ])

def edit_info_menu() -> InlineKeyboardMarkup:
    """Меню редактирования описания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Удалить описание", callback_data="delete_info")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_edit")]
    ])

def edit_photo_menu() -> InlineKeyboardMarkup:
    """Меню редактирования фото"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Удалить фото", callback_data="delete_photo")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_edit")]
    ])

def confirm_delete() -> InlineKeyboardMarkup:
    """Подтверждение удаления профиля"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data="confirm_delete"),
            InlineKeyboardButton(text="Нет", callback_data="main_menu")
        ]
    ])

# ==================== ПОИСК ====================

def search_filters() -> InlineKeyboardMarkup:
    """Меню фильтров поиска"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начать поиск", callback_data="start_search")],
        [InlineKeyboardButton(text="Рейтинг", callback_data="filter_rating")],
        [InlineKeyboardButton(text="Позиция", callback_data="filter_position")],
        [InlineKeyboardButton(text="Регион", callback_data="filter_region")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

def ratings_filter(game: str) -> InlineKeyboardMarkup:
    """Фильтр по рейтингу"""
    buttons = []

    for key, name in settings.RATINGS[game].items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"rating_{key}")])

    buttons.extend([
        [InlineKeyboardButton(text="Сбросить фильтр", callback_data="rating_reset")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_filter")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def regions_filter() -> InlineKeyboardMarkup:
    """Фильтр по региону"""
    buttons = []

    for key, name in settings.REGIONS.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"region_filter_{key}")])

    buttons.extend([
        [InlineKeyboardButton(text="Сбросить фильтр", callback_data="region_reset")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_filter")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def position_filter_menu(game: str) -> InlineKeyboardMarkup:
    """Фильтр по позиции"""
    buttons = []

    for key, name in settings.POSITIONS[game].items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"pos_filter_{key}")])

    buttons.extend([
        [InlineKeyboardButton(text="Сбросить фильтр", callback_data="position_reset")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_filter")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def profile_actions(user_id: int) -> InlineKeyboardMarkup:
    """Действия с профилем в поиске"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Лайк", callback_data=f"like_{user_id}"),
            InlineKeyboardButton(text="Пропустить", callback_data=f"skip_{user_id}")
        ],
        [InlineKeyboardButton(text="Пожаловаться", callback_data=f"report_{user_id}")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

# ==================== ЛАЙКИ И МАТЧИ ====================

def like_actions(user_id: int) -> InlineKeyboardMarkup:
    """Действия с лайком"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Лайк в ответ", callback_data=f"like_back_{user_id}"),
            InlineKeyboardButton(text="Пропустить", callback_data=f"skip_like_{user_id}")
        ],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

def contact(username: str = None) -> InlineKeyboardMarkup:
    """Контактная информация"""
    buttons = []

    if username:
        buttons.append([InlineKeyboardButton(text="💬 Написать", url=f"https://t.me/{username}")])

    buttons.append([InlineKeyboardButton(text="Главное меню", callback_data="main_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_navigation_keyboard(buttons: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    """Создание клавиатуры с кнопками навигации"""
    keyboard_buttons = [[InlineKeyboardButton(text=t, callback_data=cb)] for t, cb in buttons]
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

# ==================== АДМИН ПАНЕЛЬ ====================

def admin_main_menu() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="Жалобы", callback_data="admin_reports")],
        [InlineKeyboardButton(text="Баны", callback_data="admin_bans")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

def admin_report_actions(reported_user_id: int, report_id: int, current_index: int = 0, total_count: int = 1) -> InlineKeyboardMarkup:
    """Действия с жалобой"""
    buttons = [
        [
            InlineKeyboardButton(text="🗑️ Удалить профиль", callback_data=f"rep:del:{report_id}:{reported_user_id}"),
            InlineKeyboardButton(text="🚫 Бан 7д", callback_data=f"rep:ban:{report_id}:{reported_user_id}:7")
        ],
        [
            InlineKeyboardButton(text="🚫 Бан 30д", callback_data=f"rep:ban:{report_id}:{reported_user_id}:30")
        ],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rep:ignore:{report_id}")],
    ]
    
    if total_count > 1:
        nav_buttons = []
        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"rep:nav:prev:{current_index}"))
        if current_index < total_count - 1:
            nav_buttons.append(InlineKeyboardButton(text= "След. ▶️", callback_data=f"rep:nav:next:{current_index}"))
        if nav_buttons:
            buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="🏠 Админ меню", callback_data="admin_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_back_menu() -> InlineKeyboardMarkup:
    """Возврат в админ меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Админ меню", callback_data="admin_back")]
    ])

def admin_ban_actions_with_nav(user_id: int, current_index: int, total_count: int) -> InlineKeyboardMarkup:
    """Действия с баном с навигацией"""
    buttons = [
        [InlineKeyboardButton(text="Снять бан", callback_data=f"admin_unban_{user_id}")]
    ]

    if total_count > 1:
        nav_buttons = []
        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="Предыдущий", 
                callback_data=f"admin_ban_prev_{current_index}"
            ))
        if current_index < total_count - 1:
            nav_buttons.append(InlineKeyboardButton(
                text="Следующий", 
                callback_data=f"admin_ban_next_{current_index}"
            ))
        if nav_buttons:
            buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text="Админ меню", callback_data="admin_stats")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)