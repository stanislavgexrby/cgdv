import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

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

    region_filter = data.get('region_filter')
    if region_filter:
        region_name = settings.REGIONS.get(region_filter, region_filter)
        filters_text.append(f"<b>Регион:</b> {region_name}")
    else:
        filters_text.append("<b>Регион:</b> не указан")

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

    region_filter = data.get('region_filter')
    if region_filter:
        region_name = settings.REGIONS.get(region_filter, region_filter)
        filters_text.append(f"<b>Регион:</b> {region_name}")
    else:
        filters_text.append("<b>Регион:</b> не указан")

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
    game = data['game']

    if action == "like":
        is_match = await db.add_like(user_id, target_user_id, game)

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
            logger.info(f"Матч: {user_id} <-> {target_user_id}")
        else:
            await callback.answer("Лайк отправлен!")
            await notify_about_like(callback.bot, target_user_id, game, db)
            logger.info(f"Лайк: {user_id} -> {target_user_id}")
            await show_next_profile(callback, state)

    elif action == "skip":
        await db.add_search_skip(user_id, target_user_id, game)
        logger.info(f"Пропуск в поиске: {user_id} пропустил {target_user_id}")
        await show_next_profile(callback, state)

    elif action == "report":
        success = await db.add_report(user_id, target_user_id, game)

        if success:
            await db._clear_pattern_cache(f"search:{user_id}:{game}:*")

            await callback.answer("Жалоба отправлена модератору!\n\nВаша жалоба будет рассмотрена в ближайшее время")
            await notify_admin_new_report(callback.bot, user_id, target_user_id, game)
            logger.info(f"Жалоба добавлена: {user_id} пожаловался на {target_user_id}")
            await show_next_profile(callback, state)
        else:
            await callback.answer("Вы уже жаловались на эту анкету", show_alert=True)

async def show_current_profile(callback: CallbackQuery, state: FSMContext):
    """Показ текущего профиля в поиске"""
    data = await state.get_data()
    profiles = data.get('profiles', [])
    index = data.get('current_index', 0)

    if index >= len(profiles):
        await state.clear()
        game_name = settings.GAMES.get(data.get('game', 'dota'), data.get('game', 'dota'))
        text = f"Больше анкет в {game_name} не найдено! Попробуйте изменить фильтры или зайти позже"

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

async def show_next_profile(callback: CallbackQuery, state: FSMContext):
    """Показ следующего профиля"""
    data = await state.get_data()
    current_index = data.get('current_index', 0)
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

@router.callback_query(F.data == "filter_region", SearchForm.filters)
async def set_region_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора региона"""
    await safe_edit_message(callback, "Выберите регион:", kb.regions_filter())
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
        region_filter=None,
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

@router.callback_query(F.data.startswith("region_filter_"), SearchForm.filters)
async def save_region_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранного региона"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        return

    region = parts[2]

    if region not in settings.REGIONS:
        return

    data = await state.get_data()
    current_region = data.get('region_filter')
    if current_region == region:
        await callback.answer("Этот регион уже выбран")
        return

    await state.update_data(region_filter=region)
    region_name = settings.REGIONS.get(region, region)
    await update_filters_display(callback, state, f"Фильтр по региону: {region_name}")

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

@router.callback_query(F.data == "region_reset", SearchForm.filters)
async def reset_region_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(region_filter=None)
    await update_filters_display(callback, state, "Фильтр по региону сброшен")

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

    # Если вызывается из меню поиска - переходим в filters состояние
    if current_state == SearchForm.menu:
        await state.set_state(SearchForm.filters)
        data = await state.get_data()

    await update_user_activity(data['user_id'], 'search_browsing', db)

    profiles = await db.get_potential_matches(
        user_id=data['user_id'],
        game=data['game'],
        rating_filter=data.get('rating_filter'),
        position_filter=data.get('position_filter'),
        region_filter=data.get('region_filter'),
        goals_filter=data.get('goals_filter'),
        limit=20
    )

    if not profiles:
        await state.clear()
        game_name = settings.GAMES.get(data['game'], data['game'])
        text = f"Анкеты в {game_name} не найдены! Попробуйте изменить фильтры или зайти позже"

        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Новый поиск", callback_data="search")],
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, text, keyboard)
        await callback.answer()
        return

    await state.set_state(SearchForm.browsing)
    await state.update_data(profiles=profiles, current_index=0)
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

@router.callback_query(F.data.startswith("like_"))
async def like_profile(callback: CallbackQuery, state: FSMContext, db):
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
async def continue_search(callback: CallbackQuery, state: FSMContext):
    """Продолжить поиск после лайка"""
    await show_next_profile(callback, state)