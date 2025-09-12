import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

from handlers.notifications import notify_about_match, notify_about_like
from handlers.basic import safe_edit_message, SearchForm

logger = logging.getLogger(__name__)
router = Router()
db = Database(settings.DATABASE_PATH)

@router.callback_query(F.data == "search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']

    if db.is_user_banned(user_id):
        ban_info = db.get_user_ban(user_id)
        if ban_info:
            game_name = settings.GAMES.get(game, game)
            ban_end = ban_info['expires_at']
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}\n\n"
            text += "Во время блокировки вы не можете участвовать в поиске."

            await safe_edit_message(callback, text, kb.back())
            await callback.answer()
            return

    if not db.has_profile(user_id, game):
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"❌ Сначала создайте анкету для {game_name}", show_alert=True)
        return

    await state.clear()

    await state.update_data(
        user_id=user_id,
        game=game,
        rating_filter=None,
        position_filter=None,
        profiles=[],
        current_index=0,
        message_with_photo=False
    )

    await state.set_state(SearchForm.filters)

    game_name = settings.GAMES.get(game, game)
    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += "🏆 Рейтинг: любой\n"
    text += "⚔️ Позиция: любая\n\n"
    text += "🌍 Регион: любой\n\n"
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

@router.callback_query(F.data == "filter_rating", SearchForm.filters)
async def set_rating_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game = data.get('game')

    if not game:
        logger.error("Нет данных об игре в состоянии FSM")
        await callback.answer("❌ Ошибка состояния", show_alert=True)
        return

    await safe_edit_message(callback, "🏆 Выберите рейтинг:", kb.ratings_filter(game))
    await callback.answer()

@router.callback_query(F.data == "filter_position", SearchForm.filters)
async def set_position_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game = data.get('game')

    if not game:
        logger.error("Нет данных об игре в состоянии FSM")
        await callback.answer("❌ Ошибка состояния", show_alert=True)
        return

    keyboard = kb.position_filter_menu(game)

    await safe_edit_message(callback, "⚔️ Выберите позицию:", keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("rating_") & F.data != "rating_reset", SearchForm.filters)
async def save_rating_filter(callback: CallbackQuery, state: FSMContext):
    rating = callback.data.split("_")[1]

    data = await state.get_data()

    if not data or 'game' not in data:
        logger.error("Некорректное состояние FSM в save_rating_filter")
        await callback.answer("❌ Ошибка состояния. Попробуйте начать поиск заново.", show_alert=True)
        return

    current_rating = data.get('rating_filter')

    if current_rating == rating:
        await callback.answer("Этот рейтинг уже выбран")
        return

    await state.update_data(rating_filter=rating)

    data = await state.get_data()
    game = data['game']
    game_name = settings.GAMES.get(game, game)
    rating_name = settings.RATINGS[game].get(rating, rating)

    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += f"🏆 Рейтинг: {rating_name}\n"

    position_text = "любая"
    if data.get('position_filter'):
        position_text = settings.POSITIONS[game].get(data['position_filter'], data['position_filter'])
    text += f"⚔️ Позиция: {position_text}\n\n"
    region_text = "любой"

    if data.get('region_filter'):
        region_text = settings.REGIONS.get(data['region_filter'], data['region_filter'])
    text += f"🌍 Регион: {region_text}\n\n"

    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer("✅ Фильтр по рейтингу установлен")

@router.callback_query(F.data.startswith("pos_filter_"), SearchForm.filters)
async def save_position_filter(callback: CallbackQuery, state: FSMContext):
    position = callback.data.split("_")[2]

    data = await state.get_data()

    if not data or 'game' not in data:
        logger.error("Некорректное состояние FSM в save_position_filter")
        await callback.answer("❌ Ошибка состояния. Попробуйте начать поиск заново.", show_alert=True)
        return

    current_position = data.get('position_filter')

    if current_position == position:
        await callback.answer("Эта позиция уже выбрана")
        return

    await state.update_data(position_filter=position)

    data = await state.get_data()
    game = data['game']
    game_name = settings.GAMES.get(game, game)

    rating_text = "любой"
    if data.get('rating_filter'):
        rating_text = settings.RATINGS[game].get(data['rating_filter'], data['rating_filter'])

    position_text = settings.POSITIONS[game].get(position, position)

    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += f"🏆 Рейтинг: {rating_text}\n"
    text += f"⚔️ Позиция: {position_text}\n\n"

    region_text = "любой"
    if data.get('region_filter'):
        region_text = settings.REGIONS.get(data['region_filter'], data['region_filter'])
    text += f"🌍 Регион: {region_text}\n\n"

    text += "Настройте фильтры или начните поиск:"
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer("✅ Фильтр по позиции установлен")

@router.callback_query(F.data == "filter_region", SearchForm.filters)
async def set_region_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game = data.get('game')

    if not game:
        logger.error("Нет данных об игре в состоянии FSM")
        await callback.answer("❌ Ошибка состояния", show_alert=True)
        return

    await safe_edit_message(callback, "🌍 Выберите регион:", kb.regions_filter())
    await callback.answer()

@router.callback_query(F.data.startswith("region_filter_"), SearchForm.filters)
async def save_region_filter(callback: CallbackQuery, state: FSMContext):
    region = callback.data.split("_")[2]

    data = await state.get_data()

    if not data or 'game' not in data:
        logger.error("Некорректное состояние FSM в save_region_filter")
        await callback.answer("❌ Ошибка состояния. Попробуйте начать поиск заново.", show_alert=True)
        return

    current_region = data.get('region_filter')

    if current_region == region:
        await callback.answer("Этот регион уже выбран")
        return

    await state.update_data(region_filter=region)

    data = await state.get_data()
    game = data['game']
    game_name = settings.GAMES.get(game, game)

    rating_text = "любой"
    if data.get('rating_filter'):
        rating_text = settings.RATINGS[game].get(data['rating_filter'], data['rating_filter'])

    position_text = "любая"
    if data.get('position_filter'):
        position_text = settings.POSITIONS[game].get(data['position_filter'], data['position_filter'])

    region_text = settings.REGIONS.get(region, region)

    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += f"🏆 Рейтинг: {rating_text}\n"
    text += f"⚔️ Позиция: {position_text}\n"
    text += f"🌍 Регион: {region_text}\n\n"
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer("✅ Фильтр по region установлен")

@router.callback_query(F.data == "cancel_filter", SearchForm.filters)
async def cancel_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game = data['game']
    game_name = settings.GAMES.get(game, game)

    rating_text = "любой"
    if data.get('rating_filter'):
        rating_text = settings.RATINGS[game].get(data['rating_filter'], data['rating_filter'])

    position_text = "любая"
    if data.get('position_filter'):
        position_text = settings.POSITIONS[game].get(data['position_filter'], data['position_filter'])

    region_text = "любой"
    if data.get('region_filter'):
        region_text = settings.REGIONS.get(data['region_filter'], data['region_filter'])

    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += f"🏆 Рейтинг: {rating_text}\n"
    text += f"⚔️ Позиция: {position_text}\n\n"
    text += f"🌍 Регион: {region_text}\n\n" 
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer("❌ Отменено")

@router.callback_query(F.data == "start_search", SearchForm.filters)
async def begin_search(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if db.is_user_banned(data['user_id']):
        await state.clear()
        game_name = settings.GAMES.get(data['game'], data['game'])
        ban_info = db.get_user_ban(data['user_id'])
        if ban_info:
            ban_end = ban_info['expires_at']
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}. Поиск недоступен."
        else:
            text = f"🚫 Вы заблокированы в {game_name}. Поиск недоступен."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    profiles = db.get_potential_matches(
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
            [kb.InlineKeyboardButton(text="🔍 Поиск", callback_data="back_to_search")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, text, keyboard)
        await callback.answer()
        return

    await state.set_state(SearchForm.browsing)
    await state.update_data(profiles=profiles, current_index=0, message_with_photo=False)

    await show_current_profile(callback, state)

async def show_current_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if not data or 'profiles' not in data:
        logger.error("Некорректное состояние FSM в show_current_profile")
        await state.clear()
        await callback.answer("❌ Ошибка поиска. Попробуйте начать заново.", show_alert=True)
        return

    profiles = data['profiles']
    index = data['current_index']

    if index >= len(profiles):
        await state.clear()

        game_name = settings.GAMES.get(data.get('game', 'dota'), data.get('game', 'dota'))
        text = f"😔 Больше анкет в {game_name} не найдено. Попробуйте изменить фильтры или зайти позже."

        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="🔍 Поиск", callback_data="back_to_search")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, text, keyboard)
        await state.update_data(message_with_photo=False)
        await callback.answer()
        return

    profile = profiles[index]
    profile_text = texts.format_profile(profile)

    try:
        if profile.get('photo_id'):
            try:
                await callback.message.delete()
            except:
                pass

            sent_message = await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=profile_text,
                reply_markup=kb.profile_actions(profile['telegram_id'])
            )

            await state.update_data(message_with_photo=True, last_message_id=sent_message.message_id)
        else:
            await safe_edit_message(
                callback,
                profile_text,
                kb.profile_actions(profile['telegram_id'])
            )
            await state.update_data(message_with_photo=False)

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа анкеты: {e}")
        await show_next_profile(callback, state)

@router.callback_query(F.data.in_(["filter_rating", "filter_position", "start_search"]))
async def handle_search_outside_state(callback: CallbackQuery, state: FSMContext):
    logger.warning(f"Обработчик поиска вызван вне состояния FSM: {callback.data}")

    await state.clear()
    await callback.answer("🔄 Перезапуск поиска...", show_alert=False)

    callback.data = "search"
    await start_search(callback, state)

async def show_next_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data['current_index']

    await state.update_data(current_index=current_index + 1)
    await show_current_profile(callback, state)

@router.callback_query(F.data.startswith("skip_"), SearchForm.browsing)
async def skip_profile(callback: CallbackQuery, state: FSMContext):
    if callback.data.startswith("skip_") and callback.data[5:].isdigit():
        try:
            skipped_user_id = int(callback.data[5:])

            data = await state.get_data()
            user_id = data['user_id']
            game = data['game']

            if db.is_user_banned(user_id):
                await state.clear()
                game_name = settings.GAMES.get(game, game)
                ban_info = db.get_user_ban(user_id)
                if ban_info:
                    ban_end = ban_info['expires_at']
                    text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}."
                else:
                    text = f"🚫 Вы заблокированы в {game_name}."
                await safe_edit_message(callback, text, kb.back())
                await callback.answer()
                return

            db.add_search_skip(user_id, skipped_user_id, game)

            logger.info(f"Пропуск в поиске: {user_id} пропустил {skipped_user_id}")

        except (ValueError, KeyError) as e:
            logger.error(f"Ошибка обработки пропуска: {e}")

        await show_next_profile(callback, state)

@router.callback_query(F.data.startswith("like_"), SearchForm.browsing)
async def like_profile(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    try:
        target_user_id = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    data = await state.get_data()
    from_user_id = data['user_id']
    game = data['game']

    if db.is_user_banned(from_user_id):
        await state.clear()
        game_name = settings.GAMES.get(game, game)
        ban_info = db.get_user_ban(from_user_id)
        if ban_info:
            ban_end = ban_info['expires_at']
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}. Нельзя отправлять лайки."
        else:
            text = f"🚫 Вы заблокированы в {game_name}. Нельзя отправлять лайки."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    is_match = db.add_like(from_user_id, target_user_id, game)

    if is_match:
        target_profile = db.get_user_profile(target_user_id, game)
        await notify_about_match(callback.bot, target_user_id, from_user_id)

        if target_profile:
            match_text = texts.format_profile(target_profile, show_contact=True)
            text = f"{texts.MATCH_CREATED}\n\n{match_text}"
        else:
            text = texts.MATCH_CREATED
            if target_profile and target_profile.get('username'):
                text += f"\n\n💬 @{target_profile['username']}"
            else:
                text += "\n\n(У пользователя нет @username)"

        keyboard = kb.contact(target_profile.get('username') if target_profile else None)

        try:
            if target_profile and target_profile.get('photo_id'):
                await callback.message.answer_photo(
                    photo=target_profile['photo_id'],
                    caption=text,
                    reply_markup=keyboard
                )
            else:
                await callback.message.answer(text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка отображения матча: {e}")
            await callback.message.answer(text, reply_markup=keyboard)

        logger.info(f"Матч: {from_user_id} <-> {target_user_id}")
    else:
        await safe_edit_message(
            callback, 
            texts.LIKE_SENT,
            kb.InlineKeyboardMarkup(
                inline_keyboard=[
                    [kb.InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="continue_search")],
                    [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )

        await notify_about_like(callback.bot, target_user_id, game)

        logger.info(f"Лайк: {from_user_id} -> {target_user_id}")

    await callback.answer()

@router.callback_query(F.data == "continue_search", SearchForm.browsing)
async def continue_search(callback: CallbackQuery, state: FSMContext):
    await show_next_profile(callback, state)

@router.callback_query(F.data.startswith("report_"), SearchForm.browsing)
async def report_profile(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    try:
        reported_user_id = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    data = await state.get_data()
    reporter_id = data['user_id']
    game = data['game']

    if db.is_user_banned(reporter_id):
        await state.clear()
        game_name = settings.GAMES.get(game, game)
        ban_info = db.get_user_ban(reporter_id)
        if ban_info:
            ban_end = ban_info['expires_at']
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}."
        else:
            text = f"🚫 Вы заблокированы в {game_name}."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    success = db.add_report(reporter_id, reported_user_id, game)

    if success:
        text = "🚩 Жалоба отправлена модератору!\n\nВаша жалоба будет рассмотрена в ближайшее время."

        keyboard = kb.InlineKeyboardMarkup(
            inline_keyboard=[
                [kb.InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="continue_search")],
                [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )

        await safe_edit_message(callback, text, keyboard)

        logger.info(f"Жалоба добавлена: {reporter_id} пожаловался на {reported_user_id}")
        await callback.answer("✅ Жалоба отправлена")

        if settings.ADMIN_ID and settings.ADMIN_ID != 0:
            try:
                await callback.bot.send_message(
                    settings.ADMIN_ID,
                    f"🚩 Новая жалоба!\n\nПользователь {reporter_id} пожаловался на анкету {reported_user_id} в игре {settings.GAMES.get(game, game)}"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")

    else:
        await callback.answer("❌ Вы уже жаловались на эту анкету", show_alert=True)

@router.callback_query(F.data.startswith("report_"))
async def report_profile_general(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    try:
        reported_user_id = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']

    if db.is_user_banned(user_id):
        game_name = settings.GAMES.get(game, game)
        ban_info = db.get_user_ban(user_id)
        if ban_info:
            ban_end = ban_info['expires_at']
            await callback.answer(f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}", show_alert=True)
        else:
            await callback.answer(f"🚫 Вы заблокированы в {game_name}", show_alert=True)
        return

    success = db.add_report(user_id, reported_user_id, game)

    if success:
        text = "🚩 Жалоба отправлена модератору!\n\nВаша жалоба будет рассмотрена в ближайшее время."
        await safe_edit_message(callback, text, kb.back())

        logger.info(f"Жалоба добавлена: {user_id} пожаловался на {reported_user_id}")
        await callback.answer("✅ Жалоба отправлена")

        if settings.ADMIN_ID and settings.ADMIN_ID != 0:
            try:
                await callback.bot.send_message(
                    settings.ADMIN_ID,
                    f"🚩 Новая жалоба!\n\nПользователь {user_id} пожаловался на анкету {reported_user_id} в игре {settings.GAMES.get(game, game)}"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")
    else:
        await callback.answer("❌ Вы уже жаловались на эту анкету", show_alert=True)

@router.callback_query(F.data == "rating_reset", SearchForm.filters)
async def reset_rating_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(rating_filter=None)

    data = await state.get_data()
    game = data['game']
    game_name = settings.GAMES.get(game, game)

    position_text = "любая"
    if data.get('position_filter'):
        position_text = settings.POSITIONS[game].get(data['position_filter'], data['position_filter'])

    region_text = "любой"
    if data.get('region_filter'):
        region_text = settings.REGIONS.get(data['region_filter'], data['region_filter'])

    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += f"🏆 Рейтинг: любой\n"
    text += f"⚔️ Позиция: {position_text}\n"
    text += f"🌍 Регион: {region_text}\n\n"
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer("🔄 Фильтр по рейтингу сброшен")

@router.callback_query(F.data == "region_reset", SearchForm.filters)
async def reset_region_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(region_filter=None)

    data = await state.get_data()
    game = data['game']
    game_name = settings.GAMES.get(game, game)

    rating_text = "любой"
    if data.get('rating_filter'):
        rating_text = settings.RATINGS[game].get(data['rating_filter'], data['rating_filter'])

    position_text = "любая"
    if data.get('position_filter'):
        position_text = settings.POSITIONS[game].get(data['position_filter'], data['position_filter'])

    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += f"🏆 Рейтинг: {rating_text}\n"
    text += f"⚔️ Позиция: {position_text}\n"
    text += f"🌍 Регион: любой\n\n"
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer("🔄 Фильтр по региону сброшен")

@router.callback_query(F.data == "position_reset", SearchForm.filters)
async def reset_position_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(position_filter=None)

    data = await state.get_data()
    game = data['game']
    game_name = settings.GAMES.get(game, game)

    rating_text = "любой"
    if data.get('rating_filter'):
        rating_text = settings.RATINGS[game].get(data['rating_filter'], data['rating_filter'])

    region_text = "любой"
    if data.get('region_filter'):
        region_text = settings.REGIONS.get(data['region_filter'], data['region_filter'])

    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += f"🏆 Рейтинг: {rating_text}\n"
    text += f"⚔️ Позиция: любая\n"
    text += f"🌍 Регион: {region_text}\n\n"
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer("🔄 Фильтр по региону сброшен")