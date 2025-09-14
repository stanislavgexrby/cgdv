import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings
from handlers.basic import check_ban_and_profile, safe_edit_message, SearchForm
from handlers.notifications import notify_about_match, notify_about_like

logger = logging.getLogger(__name__)
router = Router()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def update_filter_display(callback: CallbackQuery, state: FSMContext, message: str = None):
    """Обновление отображения фильтров"""
    data = await state.get_data()
    game = data.get('game', 'dota')
    game_name = settings.GAMES.get(game, game)

    filters_text = []

    rating_filter = data.get('rating_filter')
    if rating_filter:
        rating_name = settings.RATINGS[game].get(rating_filter, rating_filter)
        filters_text.append(f"🏆 Рейтинг: {rating_name}")
    else:
        filters_text.append("🏆 Рейтинг: любой")

    position_filter = data.get('position_filter')
    if position_filter:
        position_name = settings.POSITIONS[game].get(position_filter, position_filter)
        filters_text.append(f"⚔️ Позиция: {position_name}")
    else:
        filters_text.append("⚔️ Позиция: любая")

    region_filter = data.get('region_filter')
    if region_filter:
        region_name = settings.REGIONS.get(region_filter, region_filter)
        filters_text.append(f"🌍 Регион: {region_name}")
    else:
        filters_text.append("🌍 Регион: любой")

    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += "\n".join(filters_text)
    text += "\n\nНастройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())

    if message:
        await callback.answer(message)

async def show_profile_in_search(callback: CallbackQuery, profile: dict, text: str, keyboard):
    """Универсальная функция показа профиля в поиске"""
    try:
        if profile.get('photo_id'):
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=keyboard
            )
        else:
            await safe_edit_message(callback, text, keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа профиля в поиске: {e}")
        await callback.answer("❌ Ошибка загрузки")

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
                    text += f"\n\n💬 @{target_profile['username']}"
                else:
                    text += "\n\n(У пользователя нет @username)"

            keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
                [kb.InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="continue_search")],
                [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])

            await safe_edit_message(callback, text, keyboard)
            logger.info(f"Матч: {user_id} <-> {target_user_id}")
        else:
            await safe_edit_message(
                callback, 
                texts.LIKE_SENT,
                kb.InlineKeyboardMarkup(inline_keyboard=[
                    [kb.InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="continue_search")],
                    [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            await notify_about_like(callback.bot, target_user_id, game, db)
            logger.info(f"Лайк: {user_id} -> {target_user_id}")

    elif action == "skip":
        await db.add_search_skip(user_id, target_user_id, game)
        logger.info(f"Пропуск в поиске: {user_id} пропустил {target_user_id}")
        await show_next_profile(callback, state)

    elif action == "report":
        success = await db.add_report(user_id, target_user_id, game)

        if success:
            text = "🚩 Жалоба отправлена модератору!\n\nВаша жалоба будет рассмотрена в ближайшее время."
            keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
                [kb.InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="continue_search")],
                [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
            await safe_edit_message(callback, text, keyboard)
            logger.info(f"Жалоба добавлена: {user_id} пожаловался на {target_user_id}")
            await callback.answer("✅ Жалоба отправлена")

            if settings.ADMIN_ID and settings.ADMIN_ID != 0:
                try:
                    await callback.bot.send_message(
                        settings.ADMIN_ID,
                        f"🚩 Новая жалоба!\n\nПользователь {user_id} пожаловался на анкету {target_user_id} в игре {settings.GAMES.get(game, game)}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу: {e}")
        else:
            await callback.answer("❌ Вы уже жаловались на эту анкету", show_alert=True)

async def show_current_profile(callback: CallbackQuery, state: FSMContext):
    """Показ текущего профиля в поиске"""
    data = await state.get_data()
    profiles = data.get('profiles', [])
    index = data.get('current_index', 0)

    if index >= len(profiles):
        await state.clear()
        game_name = settings.GAMES.get(data.get('game', 'dota'), data.get('game', 'dota'))
        text = f"😔 Больше анкет в {game_name} не найдено. Попробуйте изменить фильтры или зайти позже."

        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="🔍 Новый поиск", callback_data="search")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, text, keyboard)
        await callback.answer()
        return

    profile = profiles[index]
    profile_text = texts.format_profile(profile)

    await show_profile_in_search(
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
async def start_search(callback: CallbackQuery, state: FSMContext, db):
    """Начало поиска - установка фильтров"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    await state.clear()
    await state.update_data(
        user_id=user_id,
        game=game,
        rating_filter=None,
        position_filter=None,
        region_filter=None,
        profiles=[],
        current_index=0
    )
    await state.set_state(SearchForm.filters)

    await update_filter_display(callback, state)
    await callback.answer()

# ==================== ОБРАБОТЧИКИ ФИЛЬТРОВ ====================

@router.callback_query(F.data == "filter_rating", SearchForm.filters)
async def set_rating_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора рейтинга"""
    data = await state.get_data()
    game = data.get('game')
    await safe_edit_message(callback, "🏆 Выберите рейтинг:", kb.ratings_filter(game))
    await callback.answer()

@router.callback_query(F.data == "filter_position", SearchForm.filters)
async def set_position_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора позиции"""
    data = await state.get_data()
    game = data.get('game')
    await safe_edit_message(callback, "⚔️ Выберите позицию:", kb.position_filter_menu(game))
    await callback.answer()

@router.callback_query(F.data == "filter_region", SearchForm.filters)
async def set_region_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора региона"""
    await safe_edit_message(callback, "🌍 Выберите регион:", kb.regions_filter())
    await callback.answer()

# ==================== ОБРАБОТЧИКИ УСТАНОВКИ ФИЛЬТРОВ ====================

@router.callback_query(F.data.startswith("rating_"), SearchForm.filters)
async def save_rating_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранного рейтинга"""
    if callback.data.endswith("_reset"):
        await state.update_data(rating_filter=None)
        await update_filter_display(callback, state, "🔄 Фильтр по рейтингу сброшен")
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
    await update_filter_display(callback, state, f"✅ Фильтр по рейтингу: {rating_name}")

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
    await update_filter_display(callback, state, f"✅ Фильтр по позиции: {position_name}")

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
    await update_filter_display(callback, state, f"✅ Фильтр по региону: {region_name}")

# ==================== ОБРАБОТЧИКИ СБРОСА ФИЛЬТРОВ ====================

@router.callback_query(F.data == "rating_reset", SearchForm.filters)
async def reset_rating_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(rating_filter=None)
    await update_filter_display(callback, state, "🔄 Фильтр по рейтингу сброшен")

@router.callback_query(F.data == "position_reset", SearchForm.filters)
async def reset_position_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(position_filter=None)
    await update_filter_display(callback, state, "🔄 Фильтр по позиции сброшен")

@router.callback_query(F.data == "region_reset", SearchForm.filters)
async def reset_region_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(region_filter=None)
    await update_filter_display(callback, state, "🔄 Фильтр по региону сброшен")

@router.callback_query(F.data == "cancel_filter", SearchForm.filters)
async def cancel_filter(callback: CallbackQuery, state: FSMContext):
    await update_filter_display(callback, state, "❌ Отменено")

# ==================== НАЧАЛО ПОИСКА ====================

@router.callback_query(F.data == "start_search", SearchForm.filters)
async def begin_search(callback: CallbackQuery, state: FSMContext, db):
    """Начать поиск с применением фильтров"""
    data = await state.get_data()

    profiles = await db.get_potential_matches(
        user_id=data['user_id'],
        game=data['game'],
        rating_filter=data.get('rating_filter'),
        position_filter=data.get('position_filter'),
        region_filter=data.get('region_filter'),
        limit=20
    )

    if not profiles:
        await state.clear()
        game_name = settings.GAMES.get(data['game'], data['game'])
        text = f"😔 Анкеты в {game_name} не найдены. Попробуйте изменить фильтры или зайти позже."

        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="🔍 Новый поиск", callback_data="search")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
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
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    await handle_search_action(callback, "skip", target_user_id, state, db)

@router.callback_query(F.data.startswith("like_"))
async def like_profile(callback: CallbackQuery, state: FSMContext, db):
    try:
        target_user_id = int(callback.data.split("_")[1])
    except Exception:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    await handle_search_action(callback, "like", target_user_id, state, db)

@router.callback_query(F.data.startswith("report_"))
async def report_profile(callback: CallbackQuery, state: FSMContext, db):
    try:
        target_user_id = int(callback.data.split("_")[1])
    except Exception:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    await handle_search_action(callback, "report", target_user_id, state, db)

@router.callback_query(F.data == "continue_search", SearchForm.browsing)
async def continue_search(callback: CallbackQuery, state: FSMContext):
    """Продолжить поиск после лайка"""
    await show_next_profile(callback, state)

# ==================== ОБРАБОТЧИК ДЛЯ СОСТОЯНИЙ ВНЕ FSM ====================

@router.callback_query(F.data.in_(["filter_rating", "filter_position", "filter_region", "start_search"]))
async def handle_search_outside_state(callback: CallbackQuery, state: FSMContext):
    """Обработчик для случаев, когда поиск вызывается вне состояния FSM"""
    current_state = await state.get_state()

    if current_state is None or current_state != SearchForm.filters:
        logger.warning(f"Обработчик поиска вызван вне состояния FSM: {callback.data}")
        await state.clear()
        await callback.answer("🔄 Перезапуск поиска...")
        await start_search(callback, state)