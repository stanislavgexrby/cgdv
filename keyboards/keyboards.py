from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Tuple
import config.settings as settings

# ==================== ОСНОВНЫЕ МЕНЮ ====================

def community_rules_simple() -> InlineKeyboardMarkup:
    """Простое уведомление о правилах"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Понятно", callback_data="rules_understood")]
    ])

def game_selection() -> InlineKeyboardMarkup:
    """Выбор игры при старте"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Dota 2", callback_data="game_dota")],
        [InlineKeyboardButton(text="CS2", callback_data="game_cs")]
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

    buttons.append([InlineKeyboardButton(text="Сменить игру", callback_data="back_to_games")])

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
        [InlineKeyboardButton(text="Понятно", callback_data="dismiss_notification")]
    ])

# ==================== СОЗДАНИЕ И РЕДАКТИРОВАНИЕ ПРОФИЛЕЙ ====================

def profile_creation_navigation(step: str, has_prev_data: bool = False) -> InlineKeyboardMarkup:
    """Навигация при создании профиля"""
    buttons = []
    
    if step == "name":
        if has_prev_data:
            buttons.extend([
                [InlineKeyboardButton(text="Продолжить", callback_data="profile_continue")],
                [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
            ])
        else:
            buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    elif has_prev_data:
        buttons.extend([
            [InlineKeyboardButton(text="Продолжить", callback_data="profile_continue")],
            [
                InlineKeyboardButton(text="Назад", callback_data="profile_back"),
                InlineKeyboardButton(text="Отмена", callback_data="cancel")
            ]
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="Назад", callback_data="profile_back"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def ratings(game: str, selected_rating: str = None, with_navigation: bool = False, 
           for_profile: bool = True, with_cancel: bool = False) -> InlineKeyboardMarkup:
    """Интерактивный выбор рейтинга"""
    buttons = []

    for key, name in settings.RATINGS[game].items():
        if key == selected_rating:
            text = f"✅ {name}"
            callback = f"rating_remove_{key}"
        else:
            text = name
            callback = f"rating_select_{key}"
        
        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])

    # Объединяем кнопки "Не указывать" и "Готово" в одну строку
    bottom_row = []
    
    if for_profile:
        if selected_rating == "any":
            bottom_row.append(InlineKeyboardButton(text="✅ Не указывать", callback_data="rating_remove_any"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Не указывать", callback_data="rating_select_any"))

    if with_navigation:
        if selected_rating:
            bottom_row.append(InlineKeyboardButton(text="Готово", callback_data="rating_done"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Выберите рейтинг", callback_data="rating_need"))
    
    if bottom_row:
        buttons.append(bottom_row)

    if with_navigation:
        nav_buttons = [
            InlineKeyboardButton(text="Назад", callback_data="profile_back"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel")
        ]
        buttons.append(nav_buttons)
    elif with_cancel:
        cancel_callback = "cancel_edit" if not for_profile else "cancel"
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data=cancel_callback)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def countries(selected_country: str = None, with_navigation: bool = False, 
              for_profile: bool = True, with_cancel: bool = False) -> InlineKeyboardMarkup:
    """Интерактивный выбор страны"""
    buttons = []

    for key, name in settings.MAIN_COUNTRIES.items():
        if key == selected_country:
            text = f"✅ {name}"
            callback = f"country_remove_{key}"
        else:
            text = name
            callback = f"country_select_{key}"

        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])

    buttons.append([InlineKeyboardButton(text="🌍 Другое", callback_data="country_other")])

    # Объединяем кнопки "Не указывать" и "Готово" в одну строку  
    bottom_row = []
    
    if for_profile:
        if selected_country == "any":
            bottom_row.append(InlineKeyboardButton(text="✅ Не указывать", callback_data="country_remove_any"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Не указывать", callback_data="country_select_any"))

    if with_navigation:
        if selected_country:
            bottom_row.append(InlineKeyboardButton(text="Готово", callback_data="country_done"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Выберите страну", callback_data="country_need"))
    
    if bottom_row:
        buttons.append(bottom_row)

    if with_navigation:
        nav_buttons = [
            InlineKeyboardButton(text="Назад", callback_data="profile_back"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel")
        ]
        buttons.append(nav_buttons)
    elif with_cancel:
        cancel_callback = "cancel_edit" if not for_profile else "cancel"
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data=cancel_callback)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def positions(game: str, selected: List[str] = None, with_navigation: bool = False, 
             for_profile: bool = True, editing: bool = False) -> InlineKeyboardMarkup:
    """Интерактивный выбор позиций"""
    if selected is None:
        selected = []

    buttons = []

    for key, name in settings.POSITIONS[game].items():
        if key in selected:
            text = f"✅ {name}"
            callback = f"pos_remove_{key}"
        else:
            text = name
            callback = f"pos_add_{key}"

        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])

    # Объединяем кнопки "Не указывать" и "Готово" в одну строку
    bottom_row = []
    
    if for_profile or editing:
        if "any" in selected:
            bottom_row.append(InlineKeyboardButton(text="✅ Не указывать", callback_data="pos_remove_any"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Не указывать", callback_data="pos_add_any"))

    if with_navigation:
        if selected:
            bottom_row.append(InlineKeyboardButton(text="Готово", callback_data="pos_done"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Выберите позицию", callback_data="pos_need"))
    elif editing:
        if selected:
            bottom_row.append(InlineKeyboardButton(text="Сохранить", callback_data="pos_save_edit"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Выберите позицию", callback_data="pos_need"))
    
    if bottom_row:
        buttons.append(bottom_row)

    if with_navigation:
        nav_buttons = [
            InlineKeyboardButton(text="Назад", callback_data="profile_back"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel")
        ]
        buttons.append(nav_buttons)
    elif editing:
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_edit")])
    elif not with_navigation and for_profile:
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def goals(selected: List[str] = None, with_navigation: bool = False, 
         for_profile: bool = True, editing: bool = False) -> InlineKeyboardMarkup:
    """Интерактивный выбор целей"""
    if selected is None:
        selected = []

    buttons = []

    for key, name in settings.GOALS.items():
        if key in selected:
            text = f"✅ {name}"
            callback = f"goals_remove_{key}"
        else:
            text = name
            callback = f"goals_add_{key}"

        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])

# Объединяем кнопки "Не указывать" и "Готово" в одну строку
    bottom_row = []
    
    if for_profile or editing:
        if "any" in selected:
            bottom_row.append(InlineKeyboardButton(text="✅ Не указывать", callback_data="goals_remove_any"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Не указывать", callback_data="goals_add_any"))

    if with_navigation:
        if selected:
            bottom_row.append(InlineKeyboardButton(text="Готово", callback_data="goals_done"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Выберите цель", callback_data="goals_need"))
    elif editing:
        if selected:
            bottom_row.append(InlineKeyboardButton(text="Сохранить", callback_data="goals_save_edit"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Выберите цель", callback_data="goals_need"))
    
    if bottom_row:
        buttons.append(bottom_row)

    if with_navigation:
        nav_buttons = [
            InlineKeyboardButton(text="Назад", callback_data="profile_back"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel")
        ]
        buttons.append(nav_buttons)
    elif editing:
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_edit")])
    elif not with_navigation and for_profile:
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def goals_filter() -> InlineKeyboardMarkup:
    """Фильтр по цели"""
    buttons = []

    for key, name in settings.GOALS.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"goals_filter_{key}")])

    buttons.extend([
        [InlineKeyboardButton(text="Сбросить фильтр", callback_data="goals_reset")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_filter")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def skip_profile_url() -> InlineKeyboardMarkup:
    """Пропуск ссылки профиля с навигацией"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_profile_url")],
        [
            InlineKeyboardButton(text="Назад", callback_data="profile_back"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel")
        ]
    ])

def skip_photo() -> InlineKeyboardMarkup:
    """Пропуск загрузки фото с навигацией"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_photo")],
        [
            InlineKeyboardButton(text="Назад", callback_data="profile_back"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel")
        ]
    ])

def skip_info() -> InlineKeyboardMarkup:
    """Пропуск дополнительной информации с навигацией"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_info")],
        [
            InlineKeyboardButton(text="Назад", callback_data="profile_back"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel")
        ]
    ])

def confirm_cancel_profile() -> InlineKeyboardMarkup:
    """Подтверждение отмены создания профиля"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, отменить", callback_data="confirm_cancel"),
            InlineKeyboardButton(text="Нет, продолжить", callback_data="continue_profile")
        ]
    ])

# ==================== РЕДАКТИРОВАНИЕ ПРОФИЛЕЙ ====================

def edit_profile_menu(game: str = 'dota') -> InlineKeyboardMarkup:
    """Меню редактирования профиля с учетом игры"""
    profile_button_text = "Изменить Dotabuff" if game == 'dota' else "Изменить FACEIT"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="Изменить никнейм", callback_data="edit_nickname")],
        [InlineKeyboardButton(text="Изменить возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="Изменить рейтинг", callback_data="edit_rating")],
        [InlineKeyboardButton(text="Изменить страну", callback_data="edit_country")],
        [InlineKeyboardButton(text="Изменить позиции", callback_data="edit_positions")],
        [InlineKeyboardButton(text="Изменить цели", callback_data="edit_goals")],
        [InlineKeyboardButton(text=profile_button_text, callback_data="edit_profile_url")],
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
    """Простое меню поиска"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Поиск", callback_data="start_search")],
        [InlineKeyboardButton(text="Настроить фильтры", callback_data="setup_filters")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

def filters_setup_menu() -> InlineKeyboardMarkup:
    """Меню настройки фильтров"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Рейтинг", callback_data="filter_rating")],
        [InlineKeyboardButton(text="Позиция", callback_data="filter_position")],
        [InlineKeyboardButton(text="Страна", callback_data="filter_country")],  # Изменено с "filter_region"
        [InlineKeyboardButton(text="Цель", callback_data="filter_goals")],
        [InlineKeyboardButton(text="Сбросить все", callback_data="reset_all_filters")],
        [InlineKeyboardButton(text="Назад к поиску", callback_data="back_to_search")]
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

def countries_filter() -> InlineKeyboardMarkup:
    """Фильтр по странам для поиска"""
    buttons = []

    for key, name in settings.MAIN_COUNTRIES.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"country_filter_{key}")])

    buttons.append([InlineKeyboardButton(text="🌍 Другое", callback_data="country_filter_other")])

    buttons.extend([
        [InlineKeyboardButton(text="Сбросить фильтр", callback_data="country_reset")],
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
    """Действия с профилем в поиске - новая раскладка"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️", callback_data=f"like_{user_id}"),
            InlineKeyboardButton(text="💌", callback_data=f"like_msg_{user_id}"),
            InlineKeyboardButton(text="👎", callback_data=f"skip_{user_id}")
        ],
        [
            InlineKeyboardButton(text="Пожаловаться", callback_data=f"report_{user_id}"),
            InlineKeyboardButton(text="Главное меню", callback_data="main_menu")
        ]
    ])

def confirm_country(country_key: str) -> InlineKeyboardMarkup:
    """Подтверждение выбранной страны из поиска"""
    country_name = settings.COUNTRIES_DICT.get(country_key, country_key)

    buttons = [
        [InlineKeyboardButton(text=f"✅ Выбрать {country_name}", callback_data=f"confirm_country_{country_key}")],
        [InlineKeyboardButton(text="Попробовать еще раз", callback_data="retry_country_input")],
        [InlineKeyboardButton(text="Назад", callback_data="country_back")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==================== ЛАЙКИ И МЭТЧИ ====================

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
        [InlineKeyboardButton(text="Главное меню", callback_data="back_to_games")]
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
            nav_buttons.append(InlineKeyboardButton(text="Пред.", callback_data=f"rep:nav:prev:{current_index}"))
        if current_index < total_count - 1:
            nav_buttons.append(InlineKeyboardButton(text= "След.", callback_data=f"rep:nav:next:{current_index}"))
        if nav_buttons:
            buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton(text="Админ меню", callback_data="admin_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_back_menu() -> InlineKeyboardMarkup:
    """Возврат в админ меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Админ меню", callback_data="admin_back")]
    ])

def admin_ban_actions_with_nav(user_id: int, current_index: int, total_count: int) -> InlineKeyboardMarkup:
    """Действия с баном с навигацией"""
    buttons = [
        [InlineKeyboardButton(text="✅ Снять бан", callback_data=f"admin_unban_{user_id}")]
    ]

    if total_count > 1:
        nav_buttons = []
        if current_index > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="Пред.",
                callback_data=f"admin_ban_prev_{current_index}"
            ))
        if current_index < total_count - 1:
            nav_buttons.append(InlineKeyboardButton(
                text="След.",
                callback_data=f"admin_ban_next_{current_index}"
            ))
        if nav_buttons:
            buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text="Админ меню", callback_data="admin_back")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)