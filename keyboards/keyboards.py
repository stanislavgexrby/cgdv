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

def roles(selected_role: str = None, with_navigation: bool = False, with_cancel: bool = False, for_profile: bool = True) -> InlineKeyboardMarkup:
    """Выбор роли пользователя"""
    buttons = []
    
    for key, name in settings.ROLES.items():
        if key == selected_role:
            text = f"✅ {name}"
            callback = f"role_remove_{key}"
        else:
            text = name
            callback = f"role_select_{key}"
        
        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])
    
    if with_navigation:
        bottom_row = []
        if selected_role:
            bottom_row.append(InlineKeyboardButton(text="Готово", callback_data="role_done"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Выберите роль", callback_data="role_need"))
        
        if bottom_row:
            buttons.append(bottom_row)
        
        nav_buttons = [
            InlineKeyboardButton(text="Назад", callback_data="profile_back"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel")
        ]
        buttons.append(nav_buttons)
    elif with_cancel:  # ← ДОБАВИТЬ этот блок
        buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_edit")])
    
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


def ad_regions(selected_regions: List[str] = None, editing: bool = False, ad_id: int = None) -> InlineKeyboardMarkup:
    """Интерактивный выбор регионов для рекламы (множественный выбор)"""
    if selected_regions is None:
        selected_regions = []

    buttons = []

    # Опция "Все регионы"
    if "all" in selected_regions:
        buttons.append([InlineKeyboardButton(text="✅ 🌍 Все регионы", callback_data="ad_region_remove_all")])
    else:
        buttons.append([InlineKeyboardButton(text="🌍 Все регионы", callback_data="ad_region_add_all")])

    # Основные регионы
    for key, name in settings.MAIN_COUNTRIES.items():
        if key in selected_regions:
            text = f"✅ {name}"
            callback = f"ad_region_remove_{key}"
        else:
            text = name
            callback = f"ad_region_add_{key}"

        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])

    # Кнопка "Другое" для показа всех регионов
    buttons.append([InlineKeyboardButton(text="🌍 Другие страны", callback_data="ad_region_other")])

    # Кнопка "Готово"
    bottom_row = []
    if selected_regions:
        if editing and ad_id:
            bottom_row.append(InlineKeyboardButton(text="Сохранить", callback_data=f"ad_region_save_{ad_id}"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Готово", callback_data="ad_region_done"))
    else:
        bottom_row.append(InlineKeyboardButton(text="Выберите регионы", callback_data="ad_region_need"))

    if bottom_row:
        buttons.append(bottom_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def ad_all_regions(selected_regions: List[str] = None, editing: bool = False, ad_id: int = None) -> InlineKeyboardMarkup:
    """Полный список всех регионов для рекламы"""
    if selected_regions is None:
        selected_regions = []

    buttons = []

    # Опция "Все регионы"
    if "all" in selected_regions:
        buttons.append([InlineKeyboardButton(text="✅ 🌍 Все регионы", callback_data="ad_region_remove_all")])
    else:
        buttons.append([InlineKeyboardButton(text="🌍 Все регионы", callback_data="ad_region_add_all")])

    # Все страны
    for key, name in settings.COUNTRIES_DICT.items():
        if key in selected_regions:
            text = f"✅ {name}"
            callback = f"ad_region_remove_{key}"
        else:
            text = name
            callback = f"ad_region_add_{key}"

        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])

    # Кнопки навигации
    buttons.append([InlineKeyboardButton(text="🔙 Назад к основным", callback_data="ad_region_back_main")])

    # Кнопка "Готово"
    bottom_row = []
    if selected_regions:
        if editing and ad_id:
            bottom_row.append(InlineKeyboardButton(text="Сохранить", callback_data=f"ad_region_save_{ad_id}"))
        else:
            bottom_row.append(InlineKeyboardButton(text="Готово", callback_data="ad_region_done"))
    else:
        bottom_row.append(InlineKeyboardButton(text="Выберите регионы", callback_data="ad_region_need"))

    if bottom_row:
        buttons.append(bottom_row)

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

def role_filter() -> InlineKeyboardMarkup:
    """Фильтр по роли"""
    buttons = []

    for key, name in settings.ROLES.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"role_filter_{key}")])

    buttons.extend([
        [InlineKeyboardButton(text="Сбросить фильтр", callback_data="role_reset")],
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
    """Меню выбора фото с возможностью установки стандартной"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Стандартная фотография", callback_data="skip_photo")],
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
        [InlineKeyboardButton(text="Стандартная фотография", callback_data="delete_photo")],
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

def filters_setup_menu(role_filter: str = 'player') -> InlineKeyboardMarkup:
    """Меню выбора какой фильтр настроить (с учетом роли)"""
    buttons = []
    
    # Роль показываем всегда
    buttons.append([InlineKeyboardButton(text="Роль", callback_data="filter_role")])
    
    # Для игроков показываем игровые фильтры
    if role_filter == 'player':
        buttons.extend([
            [InlineKeyboardButton(text="Рейтинг", callback_data="filter_rating")],
            [InlineKeyboardButton(text="Позиция", callback_data="filter_position")],
            [InlineKeyboardButton(text="Цели", callback_data="filter_goals")]
        ])
    
    # Страна для всех
    buttons.append([InlineKeyboardButton(text="Страна", callback_data="filter_country")])
    
    # Нижние кнопки
    buttons.extend([
        [InlineKeyboardButton(text="Сбросить все", callback_data="reset_all_filters")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_search")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def edit_profile_menu(game: str = 'dota', role: str = 'player') -> InlineKeyboardMarkup:
    """Меню редактирования профиля с учетом роли"""
    buttons = []
    
    # Общие поля для всех ролей
    buttons.extend([
        [InlineKeyboardButton(text="Изменить имя", callback_data="edit_name")],
        [InlineKeyboardButton(text="Изменить никнейм", callback_data="edit_nickname")],
        [InlineKeyboardButton(text="Изменить возраст", callback_data="edit_age")],
        [InlineKeyboardButton(text="Изменить роль", callback_data="edit_role")],
        [InlineKeyboardButton(text="Изменить страну", callback_data="edit_country")]
    ])
    
    # Поля только для игроков
    if role == 'player':
        profile_button_text = "Изменить Dotabuff" if game == 'dota' else "Изменить FACEIT"
        buttons.extend([
            [InlineKeyboardButton(text="Изменить рейтинг", callback_data="edit_rating")],
            [InlineKeyboardButton(text="Изменить позиции", callback_data="edit_positions")],
            [InlineKeyboardButton(text="Изменить цели", callback_data="edit_goals")],
            [InlineKeyboardButton(text=profile_button_text, callback_data="edit_profile_url")]
        ])
    
    # Общие поля для всех
    buttons.extend([
        [InlineKeyboardButton(text="Изменить описание", callback_data="edit_info")],
        [InlineKeyboardButton(text="Изменить фото", callback_data="edit_photo")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def roles_for_edit(selected_role: str = None) -> InlineKeyboardMarkup:
    """Выбор роли при редактировании"""
    buttons = []
    
    for key, name in settings.ROLES.items():
        if key == selected_role:
            text = f"✅ {name}"
            callback = f"role_select_{key}"  # Убрать edit_
        else:
            text = name
            callback = f"role_select_{key}"  # Убрать edit_
        
        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])
    
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_edit")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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

def like_actions(user_id: int, index: int = 0, total: int = 1) -> InlineKeyboardMarkup:
    """Действия с лайком"""
    buttons = [
        [
            InlineKeyboardButton(text="❤️", callback_data=f"loves_back_{user_id}_{index}"),
            InlineKeyboardButton(text="👎", callback_data=f"loves_skip_{user_id}_{index}")
        ],
        [InlineKeyboardButton(text="Пожаловаться", callback_data=f"loves_report_{user_id}_{index}")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
        [InlineKeyboardButton(text="Реклама", callback_data="admin_ads")],
        [InlineKeyboardButton(text="Жалобы", callback_data="admin_reports")],
        [InlineKeyboardButton(text="Баны", callback_data="admin_bans")],
        [InlineKeyboardButton(text="Забанить пользователя", callback_data="admin_ban_user")],
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

# ==================== РЕКЛАМА ====================

def admin_ads_menu_empty() -> InlineKeyboardMarkup:
    """Меню рекламы когда нет постов"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить пост", callback_data="admin_add_ad")],
        [InlineKeyboardButton(text="◀️ Админ меню", callback_data="admin_back")]
    ])

def admin_ads_menu_list(ads: list) -> InlineKeyboardMarkup:
    """Меню со списком реклам (кликабельные)"""
    buttons = []
    
    for ad in ads:
        status_emoji = "✅" if ad['is_active'] else "❌"
        button_text = f"{status_emoji} #{ad['id']} {ad['caption'][:30]}"
        buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"ad_view_{ad['id']}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="➕ Добавить пост", callback_data="admin_add_ad")])
    buttons.append([InlineKeyboardButton(text="◀️ Админ меню", callback_data="admin_back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def ad_type_choice_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа рекламы при создании"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Копировать", callback_data="adtype_copy")],
        [InlineKeyboardButton(text="↗️ Переслать", callback_data="adtype_forward")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_ads")]
    ])

def game_choice_for_ad_keyboard() -> InlineKeyboardMarkup:
    """Выбор игр при создании рекламы"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Dota 2", callback_data="adgame_dota"),
            InlineKeyboardButton(text="CS2", callback_data="adgame_cs")
        ],
        [InlineKeyboardButton(text="🎯 Обе игры", callback_data="adgame_both")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_ads")]
    ])

def game_choice_for_ad_edit_keyboard(ad_id: int, current_games: List[str]) -> InlineKeyboardMarkup:
    """Выбор игр при редактировании рекламы"""
    buttons = []
    
    # Dota 2
    dota_text = "• Dota 2 •" if 'dota' in current_games and len(current_games) == 1 else "Dota 2"
    # CS2
    cs_text = "• CS2 •" if 'cs' in current_games and len(current_games) == 1 else "CS2"
    # Both
    both_text = "• Обе игры •" if len(current_games) == 2 else "Обе игры"
    
    buttons.append([
        InlineKeyboardButton(text=dota_text, callback_data=f"setgames_{ad_id}_dota"),
        InlineKeyboardButton(text=cs_text, callback_data=f"setgames_{ad_id}_cs")
    ])
    buttons.append([InlineKeyboardButton(text=both_text, callback_data=f"setgames_{ad_id}_both")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"ad_view_{ad_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_ad_actions(ad: dict) -> InlineKeyboardMarkup:
    """Действия с конкретной рекламой"""
    ad_id = ad['id']
    is_active = ad['is_active']

    toggle_text = "⏸️ Выключить" if is_active else "▶️ Включить"

    buttons = [
        [InlineKeyboardButton(text="👁️ Предпросмотр", callback_data=f"ad_preview_{ad_id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"ad_toggle_{ad_id}")],
        [InlineKeyboardButton(text="🎮 Изменить игры", callback_data=f"ad_games_{ad_id}")],
        [InlineKeyboardButton(text="🌍 Изменить регионы", callback_data=f"ad_regions_{ad_id}")],
        [InlineKeyboardButton(text="📊 Изменить интервал", callback_data=f"ad_interval_{ad_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"ad_delete_{ad_id}")],
        [InlineKeyboardButton(text="◀️ К списку", callback_data="ad_back_to_list")]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def ad_expires_choice_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора срока действия рекламы"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 день", callback_data="ad_expires_1"),
            InlineKeyboardButton(text="3 дня", callback_data="ad_expires_3")
        ],
        [
            InlineKeyboardButton(text="7 дней", callback_data="ad_expires_7"),
            InlineKeyboardButton(text="14 дней", callback_data="ad_expires_14")
        ],
        [
            InlineKeyboardButton(text="30 дней", callback_data="ad_expires_30")
        ],
        [
            InlineKeyboardButton(text="📅 Указать дату", callback_data="ad_expires_custom"),
            InlineKeyboardButton(text="♾️ Бессрочно", callback_data="ad_expires_never")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_ads")]
    ])

def interval_choice_keyboard(ad_id: int = None, current_interval: int = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора интервала показа рекламы"""
    intervals = [5, 10, 15, 20, 25, 30, 40, 50]

    buttons = []
    row = []

    for interval in intervals:
        if current_interval and interval == current_interval:
            button_text = f"• {interval} •"
        else:
            button_text = str(interval)

        if ad_id is not None:
            callback = f"setint_{ad_id}_{interval}"
        else:
            callback = f"interval_{interval}"

        row.append(InlineKeyboardButton(text=button_text, callback_data=callback))

        if len(row) == 4:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Добавляем кнопку для ввода своего значения
    if ad_id is not None:
        buttons.append([InlineKeyboardButton(text="✏️ Ввести своё значение", callback_data=f"custom_interval_{ad_id}")])
        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"ad_view_{ad_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="✏️ Ввести своё значение", callback_data="custom_interval")])

        buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_ads")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)