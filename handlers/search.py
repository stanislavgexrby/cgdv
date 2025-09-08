import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

from .notifications import notify_about_match, notify_about_like

from .basic import safe_edit_message

logger = logging.getLogger(__name__)
router = Router()
db = Database(settings.DATABASE_PATH)

class SearchForm(StatesGroup):
    filters = State()
    browsing = State()

@router.callback_query(F.data == "search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']
    
    if not db.has_profile(user_id, game):
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"❌ Сначала создайте анкету для {game_name}", show_alert=True)
        return

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
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

@router.callback_query(F.data == "filter_rating", SearchForm.filters)
async def set_rating_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game = data['game']

    await safe_edit_message(callback, "🏆 Выберите рейтинг:", kb.ratings(game))
    await callback.answer()

@router.callback_query(F.data.startswith("rating_"), SearchForm.filters)
async def save_rating_filter(callback: CallbackQuery, state: FSMContext):
    rating = callback.data.split("_")[1]
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
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

@router.callback_query(F.data == "filter_position", SearchForm.filters)
async def set_position_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game = data['game']

    buttons = []
    for key, name in settings.POSITIONS[game].items():
        buttons.append([kb.InlineKeyboardButton(text=name, callback_data=f"pos_filter_{key}")])

    buttons.append([kb.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_filter")])

    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit_message(callback, "⚔️ Выберите позицию:", keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("pos_filter_"), SearchForm.filters)
async def save_position_filter(callback: CallbackQuery, state: FSMContext):
    position = callback.data.split("_")[2]
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
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

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

    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += f"🏆 Рейтинг: {rating_text}\n"
    text += f"⚔️ Позиция: {position_text}\n\n"
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

@router.callback_query(F.data == "start_search", SearchForm.filters)
async def begin_search(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    profiles = db.get_potential_matches(
        user_id=data['user_id'],
        game=data['game'],
        rating_filter=data.get('rating_filter'),
        position_filter=data.get('position_filter'),
        limit=20
    )

    if not profiles:
        game_name = settings.GAMES.get(data['game'], data['game'])
        text = f"😔 Анкеты в {game_name} не найдены. Попробуйте изменить фильтры или зайти позже."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    await state.set_state(SearchForm.browsing)
    await state.update_data(profiles=profiles, current_index=0, message_with_photo=False)

    await show_current_profile(callback, state)

async def show_current_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    profiles = data['profiles']
    index = data['current_index']

    if index >= len(profiles):
        game_name = settings.GAMES.get(data['game'], data['game'])
        text = f"😔 Больше анкет в {game_name} не найдено. Попробуйте изменить фильтры или зайти позже."
        await safe_edit_message(callback, text, kb.back())
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

async def show_next_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data['current_index']

    await state.update_data(current_index=current_index + 1)
    await show_current_profile(callback, state)

@router.callback_query(F.data.startswith("skip_"), SearchForm.browsing)
async def skip_profile(callback: CallbackQuery, state: FSMContext):
    if callback.data.startswith("skip_") and callback.data[5:].isdigit():
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

    is_match = db.add_like(from_user_id, target_user_id, game)

    if is_match:
        target_profile = db.get_user_profile(target_user_id, game)
        await notify_about_match(callback.bot, target_user_id, from_user_id)
        # При матче показываем контакты
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

        if data.get('message_with_photo'):
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer(text, reply_markup=keyboard)
        else:
            await safe_edit_message(callback, text, keyboard)

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

        await notify_about_like(callback.bot, target_user_id)

        logger.info(f"Лайк: {from_user_id} -> {target_user_id}")

    await callback.answer()

@router.callback_query(F.data == "continue_search", SearchForm.browsing)
async def continue_search(callback: CallbackQuery, state: FSMContext):
    await show_next_profile(callback, state)