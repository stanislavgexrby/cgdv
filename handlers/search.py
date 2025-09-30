import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from handlers.likes import show_profile_with_photo

from handlers.basic import check_ban_and_profile, safe_edit_message, SearchForm
from handlers.notifications import notify_about_match, notify_about_like, update_user_activity, notify_admin_new_report
from handlers.likes import show_profile_with_photo

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def update_filters_display(callback: CallbackQuery, state: FSMContext, message: str = None):
    """Отображение текущих фильтров"""
    data = await state.get_data()
    game = data.get('game', 'dota')
    game_name = settings.GAMES.get(game, game)

    filters_text = []

    rating_filter = data.get('rating_filter')
    if rating_filter:
        rating_name = settings.RATINGS[game].get(rating_filter, rating_filter)
        filters_text.append(f"<b>Рейтинг:</b> {rating_name}")
    else:
        filters_text.append("<b>Рейтинг:</b> не указан")

    position_filter = data.get('position_filter')
    if position_filter:
        position_name = settings.POSITIONS[game].get(position_filter, position_filter)
        filters_text.append(f"<b>Позиция:</b> {position_name}")
    else:
        filters_text.append("<b>Позиция:</b> не указана")

    country_filter = data.get('country_filter')
    if country_filter:
        country_name = settings.MAIN_COUNTRIES.get(country_filter) or settings.COUNTRIES_DICT.get(country_filter, country_filter)
        filters_text.append(f"<b>Страна:</b> {country_name}")
    else:
        filters_text.append("<b>Страна:</b> не указана")

    goals_filter = data.get('goals_filter')
    if goals_filter:
        goals_name = settings.GOALS.get(goals_filter, goals_filter)
        filters_text.append(f"<b>Цель:</b> {goals_name}")
    else:
        filters_text.append("<b>Цель:</b> не указана")

    text = f"Настройка фильтров для {game_name}\n\n"
    text += "\n".join(filters_text)
    text += "\n\nВыберите что настроить:"

    await safe_edit_message(callback, text, kb.filters_setup_menu())

    if message:
        await callback.answer(message)

async def get_full_filters_display(data: dict) -> str:
    """Полное отображение всех фильтров как в меню настройки"""
    game = data.get('game', 'dota')
    game_name = settings.GAMES.get(game, game)

    filters_text = []

    rating_filter = data.get('rating_filter')
    if rating_filter:
        rating_name = settings.RATINGS[game].get(rating_filter, rating_filter)
        filters_text.append(f"<b>Рейтинг:</b> {rating_name}")
    else:
        filters_text.append("<b>Рейтинг:</b> не указан")

    position_filter = data.get('position_filter')
    if position_filter:
        position_name = settings.POSITIONS[game].get(position_filter, position_filter)
        filters_text.append(f"<b>Позиция:</b> {position_name}")
    else:
        filters_text.append("<b>Позиция:</b> не указана")

    country_filter = data.get('country_filter')
    if country_filter:
        country_name = settings.MAIN_COUNTRIES.get(country_filter) or settings.COUNTRIES_DICT.get(country_filter, country_filter)
        filters_text.append(f"<b>Страна:</b> {country_name}")
    else:
        filters_text.append("<b>Страна:</b> не указана")

    goals_filter = data.get('goals_filter')
    if goals_filter:
        goals_name = settings.GOALS.get(goals_filter, goals_filter)
        filters_text.append(f"<b>Цель:</b> {goals_name}")
    else:
        filters_text.append("<b>Цель:</b> не указана")

    text = f"Поиск в {game_name}\n\n"
    text += "\n".join(filters_text)
    text += "\n\nВыберите действие:"

    return text

async def handle_search_action(callback: CallbackQuery, action: str, target_user_id: int, state: FSMContext, db):
    """Универсальная обработка действий в поиске"""
    user_id = callback.from_user.id
    data = await state.get_data()
    
    if 'game' not in data:
        user = await db.get_user(user_id)
        game = user['current_game']
        await state.update_data(game=game)
    else:
        game = data['game']
    
    if action == "like":
        is_match = await db.add_like(user_id, target_user_id, game, message=None)
        
        if is_match:
            target_profile = await db.get_user_profile(target_user_id, game)
            await notify_about_match(callback.bot, target_user_id, user_id, game, db)
            
            if target_profile:
                match_text = texts.format_profile(target_profile, show_contact=True)
                text = f"{texts.MATCH_CREATED}\n\n{match_text}"
            else:
                text = texts.MATCH_CREATED
                if target_profile and target_profile.get('username'):
                    text += f"\n\n@{target_profile['username']}"
                else:
                    text += "\n\n(У пользователя нет @username)"
            
            keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
                [kb.InlineKeyboardButton(text="Продолжить поиск", callback_data="continue_search")],
                [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
            ])
            
            await safe_edit_message(callback, text, keyboard)
            logger.info(f"Мэтч: {user_id} <-> {target_user_id}")
        else:
            await callback.answer("Лайк отправлен!")
            await notify_about_like(callback.bot, target_user_id, game, db)
            logger.info(f"Лайк: {user_id} -> {target_user_id}")
            await show_next_profile(callback, state, db)
    
    elif action == "skip":
        await db.add_search_skip(user_id, target_user_id, game)
        logger.info(f"Пропуск в поиске: {user_id} пропустил {target_user_id}")
        await show_next_profile(callback, state, db)
    
    elif action == "report":
        success = await db.add_report(user_id, target_user_id, game)
        
        if success:
            await db._clear_pattern_cache(f"search:{user_id}:{game}:*")
            
            await callback.answer("Жалоба отправлена модератору!\n\nВаша жалоба будет рассмотрена в ближайшее время")
            await notify_admin_new_report(callback.bot, user_id, target_user_id, game)
            logger.info(f"Жалоба добавлена: {user_id} пожаловался на {target_user_id}")
            await show_next_profile(callback, state, db)
        else:
            await callback.answer("Вы уже жаловались на эту анкету", show_alert=True)

async def show_current_profile(callback: CallbackQuery, state: FSMContext):
    """Показ текущего профиля в поиске"""
    data = await state.get_data()
    profiles = data.get('profiles', [])
    index = data.get('current_index', 0)
    
    if not data or 'game' not in data:
        await callback.answer("Сессия поиска истекла\n Начните новый поиск", show_alert=True)
        await state.clear()
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Новый поиск", callback_data="search")],
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, "Начните новый поиск:", keyboard)
        return
    
    if index >= len(profiles):
        await state.clear()
        game_name = settings.GAMES.get(data.get('game', 'dota'), data.get('game', 'dota'))
        text = f"Больше анкет в {game_name} не найдено!\n\nПопробуйте изменить фильтры или зайти позже"
        
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Новый поиск", callback_data="search")],
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, text, keyboard)
        await callback.answer()
        return
    
    profile = profiles[index]
    profile_text = texts.format_profile(profile)
    
    await show_profile_with_photo(
        callback,
        profile,
        profile_text,
        kb.profile_actions(profile['telegram_id'])
    )

async def show_next_profile(callback: CallbackQuery, state: FSMContext, db):
    """Показ следующего профиля с автоподгрузкой"""
    data = await state.get_data()
    current_index = data.get('current_index', 0)
    profiles = data.get('profiles', [])
    
    if not data or 'user_id' not in data:
        user_id = callback.from_user.id
        user = await db.get_user(user_id)
        game = user['current_game']
        await state.update_data(
            user_id=user_id,
            game=game
        )
        data = await state.get_data()
    
    if profiles and current_index >= len(profiles) - 5:
        last_offset = data.get('last_loaded_offset', 0)
        new_offset = last_offset + 20
        
        try:
            new_batch = await db.get_potential_matches(
                user_id=data['user_id'],
                game=data['game'],
                rating_filter=data.get('rating_filter'),
                position_filter=data.get('position_filter'),
                country_filter=data.get('country_filter'),
                goals_filter=data.get('goals_filter'),
                limit=20,
                offset=new_offset
            )
            
            if new_batch:
                profiles.extend(new_batch)
                await state.update_data(
                    profiles=profiles,
                    last_loaded_offset=new_offset
                )
        except Exception as e:
            logger.error(f"Ошибка при подгрузке анкет: {e}")
    
    await state.update_data(current_index=current_index + 1)
    await show_current_profile(callback, state)

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "search")
@check_ban_and_profile()
async def start_search_menu(callback: CallbackQuery, state: FSMContext, db):
    """Показ главного меню поиска"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    await update_user_activity(user_id, 'search_setup', db)

    data = await state.get_data()
    
    if not data or data.get('game') != game:
        await state.clear()
        await state.update_data(
            user_id=user_id,
            game=game,
            rating_filter=None,
            position_filter=None,
            region_filter=None,
            goals_filter=None,
            profiles=[],
            current_index=0
        )
        data = await state.get_data()
    
    await state.set_state(SearchForm.menu)

    text = await get_full_filters_display(data)
    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

@router.callback_query(F.data == "setup_filters", SearchForm.menu)
async def setup_filters_menu(callback: CallbackQuery, state: FSMContext):
    """Переход к настройке фильтров"""
    await state.set_state(SearchForm.filters)
    await update_filters_display(callback, state)
    await callback.answer()

@router.callback_query(F.data == "back_to_search")
async def back_to_search_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат к главному меню поиска"""
    data = await state.get_data()
    await state.set_state(SearchForm.menu)

    text = await get_full_filters_display(data)
    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

# ==================== НАСТРОЙКА ФИЛЬТРОВ ====================

@router.callback_query(F.data == "filter_rating", SearchForm.filters)
async def set_rating_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора рейтинга"""
    data = await state.get_data()
    game = data.get('game')
    await safe_edit_message(callback, "Выберите рейтинг:", kb.ratings_filter(game))
    await callback.answer()

@router.callback_query(F.data == "filter_position", SearchForm.filters)
async def set_position_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора позиции"""
    data = await state.get_data()
    game = data.get('game')
    await safe_edit_message(callback, "Выберите позицию:", kb.position_filter_menu(game))
    await callback.answer()

@router.callback_query(F.data == "filter_country", SearchForm.filters)
async def set_country_filter(callback: CallbackQuery, state: FSMContext):
    """Настройка фильтра по стране"""
    text = "Выберите страну для поиска:"
    keyboard = kb.countries_filter()
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.callback_query(F.data == "filter_goals", SearchForm.filters)
async def set_goals_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора цели"""
    await safe_edit_message(callback, "Выберите цель:", kb.goals_filter())
    await callback.answer()

@router.callback_query(F.data == "reset_all_filters", SearchForm.filters)
async def reset_all_filters(callback: CallbackQuery, state: FSMContext):
    """Сброс всех фильтров"""
    await state.update_data(
        rating_filter=None,
        position_filter=None,
        country_filter=None,
        goals_filter=None
    )
    await update_filters_display(callback, state, "Все фильтры сброшены")

# ==================== СОХРАНЕНИЕ ФИЛЬТРОВ ====================

@router.callback_query(F.data.startswith("rating_"), SearchForm.filters)
async def save_rating_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранного рейтинга"""
    if callback.data.endswith("_reset"):
        await state.update_data(rating_filter=None)
        await update_filters_display(callback, state, "Фильтр по рейтингу сброшен")
        return

    rating = callback.data.split("_")[1]
    data = await state.get_data()
    game = data['game']

    if rating not in settings.RATINGS.get(game, {}):
        return

    current_rating = data.get('rating_filter')
    if current_rating == rating:
        await callback.answer("Этот рейтинг уже выбран")
        return

    await state.update_data(rating_filter=rating)
    rating_name = settings.RATINGS[game].get(rating, rating)
    await update_filters_display(callback, state, f"Фильтр по рейтингу: {rating_name}")

@router.callback_query(F.data.startswith("pos_filter_"), SearchForm.filters)
async def save_position_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранной позиции"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        return

    position = parts[2]
    data = await state.get_data()
    game = data['game']

    if position not in settings.POSITIONS.get(game, {}):
        return

    current_position = data.get('position_filter')
    if current_position == position:
        await callback.answer("Эта позиция уже выбрана")
        return

    await state.update_data(position_filter=position)
    position_name = settings.POSITIONS[game].get(position, position)
    await update_filters_display(callback, state, f"Фильтр по позиции: {position_name}")

@router.callback_query(F.data.startswith("country_filter_"), SearchForm.filters)
async def save_country_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранной страны в фильтре"""
    parts = callback.data.split("_")
    
    if len(parts) < 3:
        return

    if parts[2] == "other":
        await state.set_state(SearchForm.country_filter_input)

        text = "Введите название страны для поиска:\n\nНапример: Молдова, Эстония, Литва, Польша, Германия и т.д."

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_country_filter")]
        ])

        await safe_edit_message(callback, text, keyboard)
        await callback.answer()
        return

    country = parts[2]

    if country not in settings.MAIN_COUNTRIES:
        return

    data = await state.get_data()
    current_country = data.get('country_filter')
    if current_country == country:
        await callback.answer("Эта страна уже выбрана")
        return

    await state.update_data(country_filter=country)
    country_name = settings.MAIN_COUNTRIES.get(country, country)
    await update_filters_display(callback, state, f"Фильтр по стране: {country_name}")

@router.callback_query(F.data == "back_country_filter", SearchForm.country_filter_input)
async def back_to_country_filter(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору страны в фильтре"""
    await state.set_state(SearchForm.filters)
    
    text = "Выберите страну для поиска:"
    keyboard = kb.countries_filter()
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.message(SearchForm.country_filter_input)
async def process_country_filter_input(message: Message, state: FSMContext):
    """Обработка ввода названия страны для фильтра"""
    search_name = message.text.strip()
    
    country_key = settings.find_country_by_name(search_name)
    
    if country_key:
        country_name = settings.COUNTRIES_DICT[country_key]
        text = f"Найдена страна: {country_name}\n\nВыберите действие:"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Использовать {country_name}", callback_data=f"confirm_filter_country_{country_key}")],
            [InlineKeyboardButton(text="Попробовать еще раз", callback_data="retry_country_filter_input")],
            [InlineKeyboardButton(text="Назад", callback_data="back_country_filter")]
        ])
        
        await message.answer(text, reply_markup=keyboard)
    else:
        text = f"Страна '{search_name}' не найдена в словаре.\n\nПопробуйте ввести другое название."
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Попробовать еще раз", callback_data="retry_country_filter_input")],
            [InlineKeyboardButton(text="Назад", callback_data="back_country_filter")]
        ])
        
        await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "retry_country_filter_input", SearchForm.country_filter_input)
async def handle_retry_country_filter_input(callback: CallbackQuery, state: FSMContext):
    """Обработчик повторного ввода страны в фильтре поиска"""  
    text = "Введите название страны для поиска:\n\nНапример: Молдова, Эстония, Литва, Польша, Германия и т.д."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_country_filter")]
    ])
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_filter_country_"), SearchForm.country_filter_input)
async def confirm_country_filter(callback: CallbackQuery, state: FSMContext):
    """Подтверждение выбранной страны для фильтра"""
    country_key = callback.data.split("_", 3)[3]

    await state.update_data(country_filter=country_key)
    await state.set_state(SearchForm.filters)

    country_name = settings.COUNTRIES_DICT[country_key]

    try:
        await callback.message.delete()
    except:
        pass

    await update_filters_display(callback, state, f"Фильтр по стране: {country_name}")

@router.callback_query(F.data.startswith("goals_filter_"), SearchForm.filters)
async def save_goals_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранной цели"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        return

    goal = parts[2]

    if goal not in settings.GOALS:
        return

    data = await state.get_data()
    current_goal = data.get('goals_filter')
    if current_goal == goal:
        await callback.answer("Эта цель уже выбрана")
        return

    await state.update_data(goals_filter=goal)
    goals_name = settings.GOALS.get(goal, goal)
    await update_filters_display(callback, state, f"Фильтр по цели: {goals_name}")

# ==================== СБРОС ФИЛЬТРОВ ====================

@router.callback_query(F.data == "rating_reset", SearchForm.filters)
async def reset_rating_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(rating_filter=None)
    await update_filters_display(callback, state, "Фильтр по рейтингу сброшен")

@router.callback_query(F.data == "position_reset", SearchForm.filters)
async def reset_position_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(position_filter=None)
    await update_filters_display(callback, state, "Фильтр по позиции сброшен")

@router.callback_query(F.data == "country_reset", SearchForm.filters)
async def reset_country_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(country_filter=None)
    await update_filters_display(callback, state, "Фильтр по стране сброшен")

@router.callback_query(F.data == "goals_reset", SearchForm.filters)
async def reset_goals_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(goals_filter=None)
    await update_filters_display(callback, state, "Фильтр по цели сброшен")

@router.callback_query(F.data == "cancel_filter", SearchForm.filters)
async def cancel_filter(callback: CallbackQuery, state: FSMContext):
    await update_filters_display(callback, state, "Отменено")

# ==================== НАЧАЛО ПОИСКА ====================

@router.callback_query(F.data == "start_search")
async def begin_search(callback: CallbackQuery, state: FSMContext, db):
    """Начать поиск с применением фильтров"""
    data = await state.get_data()
    current_state = await state.get_state()
    
    if current_state == SearchForm.menu:
        await state.set_state(SearchForm.filters)
        data = await state.get_data()
    
    await update_user_activity(data['user_id'], 'search_browsing', db)
    
    all_profiles = []
    for batch_offset in [0, 20, 40]:
        batch = await db.get_potential_matches(
            user_id=data['user_id'],
            game=data['game'],
            rating_filter=data.get('rating_filter'),
            position_filter=data.get('position_filter'),
            country_filter=data.get('country_filter'),
            goals_filter=data.get('goals_filter'),
            limit=20,
            offset=batch_offset
        )
        if batch:
            all_profiles.extend(batch)
        else:
            break
    
    if not all_profiles:
        await state.clear()
        game_name = settings.GAMES.get(data['game'], data['game'])
        text = f"Анкеты в {game_name} не найдены!\n\nПопробуйте изменить фильтры или зайти позже"
        
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Новый поиск", callback_data="search")],
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, text, keyboard)
        await callback.answer()
        return
    
    await state.set_state(SearchForm.browsing)
    await state.update_data(
        profiles=all_profiles,  # Используем profiles для совместимости
        current_index=0,
        last_loaded_offset=40  # Запоминаем последний загруженный offset
    )
    await show_current_profile(callback, state)

# ==================== ДЕЙСТВИЯ В ПОИСКЕ ====================

@router.callback_query(F.data.startswith("skip_"))
async def skip_profile(callback: CallbackQuery, state: FSMContext, db):
    try:
        target_user_id = int(callback.data.split("_")[1])
    except Exception:
        await state.clear()
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await handle_search_action(callback, "skip", target_user_id, state, db)

@router.callback_query(F.data.regexp(r"^like_\d+$"))
async def like_profile(callback: CallbackQuery, state: FSMContext, db):
    # Игнорируем like_msg_ - он обрабатывается отдельно
    if callback.data.startswith("like_msg_"):
        return
    
    try:
        target_user_id = int(callback.data.split("_")[1])
    except Exception:
        await state.clear()
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await handle_search_action(callback, "like", target_user_id, state, db)

@router.callback_query(F.data.startswith("report_"))
async def report_profile(callback: CallbackQuery, state: FSMContext, db):
    try:
        target_user_id = int(callback.data.split("_")[1])
    except Exception:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await handle_search_action(callback, "report", target_user_id, state, db)

@router.callback_query(F.data == "continue_search", SearchForm.browsing)
async def continue_search(callback: CallbackQuery, state: FSMContext, db):
    """Продолжить поиск после лайка"""
    data = await state.get_data()
    if not data or 'profiles' not in data:
        await begin_search(callback, state, db)
    else:
        await show_next_profile(callback, state, db)

@router.callback_query(F.data.startswith("like_msg_"))
async def like_with_message(callback: CallbackQuery, state: FSMContext, db):
    """Инициация лайка с сообщением"""
    try:
        target_user_id = int(callback.data.split("_")[2])
    except Exception:
        await state.clear()
        await callback.answer("Ошибка данных", show_alert=True)
        return
    
    data = await state.get_data()
    profiles = data.get('profiles', [])
    current_index = data.get('current_index', 0)
    
    if current_index >= len(profiles):
        await callback.answer("Анкета не найдена", show_alert=True)
        return
    
    profile = profiles[current_index]
    
    # Сохраняем информацию о целевом пользователе И ID сообщения
    await state.update_data(
        message_target_user_id=target_user_id,
        message_target_index=current_index,
        last_search_message_id=callback.message.message_id  # ДОБАВИТЬ ЭТУ СТРОКУ
    )
    await state.set_state(SearchForm.waiting_message)
    
    # Редактируем сообщение
    profile_text = texts.format_profile(profile)
    text = f"{profile_text}\n\n<b>💌 Напишите сообщение этому пользователю:</b>"
    
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text="Отмена", callback_data="cancel_message")]
    ])
    
    await show_profile_with_photo(callback, profile, text, keyboard)
    await callback.answer()

@router.callback_query(F.data == "cancel_message", SearchForm.waiting_message)
async def cancel_message(callback: CallbackQuery, state: FSMContext):
    """Отмена отправки сообщения - возврат к текущей анкете"""
    await state.set_state(SearchForm.browsing)
    
    # Удаляем временные данные о сообщении
    data = await state.get_data()
    if 'message_target_user_id' in data:
        del data['message_target_user_id']
    if 'message_target_index' in data:
        del data['message_target_index']
    await state.set_data(data)
    
    # Показываем текущий профиль заново
    await show_current_profile(callback, state)
    await callback.answer()

@router.message(SearchForm.waiting_message, F.text)
async def process_message_with_like(message: Message, state: FSMContext, db):
    """Обработка сообщения и отправка лайка"""
    user_id = message.from_user.id
    data = await state.get_data()
    
    target_user_id = data.get('message_target_user_id')
    game = data.get('game')
    user_message = message.text.strip()
    
    if not target_user_id or not game:
        await message.answer("Ошибка: данные не найдены")
        await state.clear()
        return
    
    # Валидация сообщения
    if len(user_message) > 500:
        await message.answer("Сообщение слишком длинное. Максимум 500 символов.")
        return
    
    # ДОБАВИТЬ: Удаляем сообщение с анкетой, на которой была нажата кнопка
    last_message_id = data.get('last_search_message_id')
    if last_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_message_id)
        except Exception:
            pass
    
    # Добавляем лайк с сообщением
    is_match = await db.add_like(user_id, target_user_id, game, message=user_message)
    
    # Отправляем обычное уведомление о лайке
    await notify_about_like(message.bot, target_user_id, game, db)
    
    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except Exception:
        pass
    
    if is_match:
        # Обработка мэтча
        target_profile = await db.get_user_profile(target_user_id, game)
        await notify_about_match(message.bot, target_user_id, user_id, game, db)
        
        if target_profile:
            match_text = texts.format_profile(target_profile, show_contact=True)
            text = f"{texts.MATCH_CREATED}\n\n{match_text}"
        else:
            text = texts.MATCH_CREATED
            if target_profile and target_profile.get('username'):
                text += f"\n\n@{target_profile['username']}"
            else:
                text += "\n\n(У пользователя нет @username)"
        
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Продолжить поиск", callback_data="continue_search")],
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
        logger.info(f"Мэтч с сообщением: {user_id}  {target_user_id}")
    else:
        logger.info(f"Лайк с сообщением: {user_id} -> {target_user_id}")
        # Показываем успех и переходим к следующей анкете
        await state.set_state(SearchForm.browsing)
        
        # Обновляем current_index для перехода к следующему профилю
        current_index = data.get('current_index', 0)
        await state.update_data(current_index=current_index + 1)
        
        # Показываем следующий профиль
        profiles = data.get('profiles', [])
        next_index = current_index + 1
        
        if next_index >= len(profiles):
            # Нужно загрузить больше профилей или показать конец
            await show_search_end(message, state, game)
        else:
            # Показываем следующую анкету
            await show_next_search_profile(message, state, db)

async def show_next_search_profile(message: Message, state: FSMContext, db):
    """Показ следующего профиля после отправки сообщения"""
    data = await state.get_data()
    profiles = data.get('profiles', [])
    current_index = data.get('current_index', 0)
    
    if current_index >= len(profiles):
        game = data.get('game')
        await show_search_end(message, state, game)
        return
    
    profile = profiles[current_index]
    profile_text = texts.format_profile(profile)
    text = f"Поиск игроков:\n\n{profile_text}"
    
    keyboard = kb.profile_actions(profile['telegram_id'])
    
    # ДОБАВИТЬ: Удаляем предыдущее сообщение с анкетой
    last_message_id = data.get('last_search_message_id')
    if last_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_message_id)
        except Exception:
            pass
    
    # Отправляем новое сообщение с анкетой
    if profile.get('photo_id'):
        try:
            sent_msg = await message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except Exception:
            sent_msg = await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        sent_msg = await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    
    # ДОБАВИТЬ: Сохраняем ID нового сообщения
    await state.update_data(last_search_message_id=sent_msg.message_id)

async def show_search_end(message: Message, state: FSMContext, game: str):
    """Показ сообщения о конце анкет"""
    await state.clear()
    game_name = settings.GAMES.get(game, game)
    text = f"Больше анкет в {game_name} не найдено.\n\nПопробуйте изменить фильтры или вернитесь позже!"
    
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text="Настроить фильтры", callback_data="setup_filters")],
        [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.message(SearchForm.waiting_message)
async def wrong_message_format(message: Message):
    """Обработка неправильного формата сообщения"""
    await message.answer(
        "Пожалуйста, отправьте текстовое сообщение или нажмите 'Отмена'",
        parse_mode='HTML'
    )