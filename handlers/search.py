import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

from .basic import edit_text_with_photo

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

    if not user or not user.get('name'):
        await callback.answer("❌ Сначала создайте анкету", show_alert=True)
        return

    await state.update_data(
        user_id=user_id,
        game=user['current_game'],
        rating_filter=None,
        position_filter=None,
        profiles=[],
        current_index=0
    )

    await state.set_state(SearchForm.filters)

    text = "🔍 Фильтры поиска:\n\n"
    text += "🏆 Рейтинг: любой\n"
    text += "⚔️ Позиция: любая\n\n"
    text += "Настройте фильтры или начните поиск:"

    await callback.message.edit_text(text, reply_markup=kb.search_filters())
    await callback.answer()

@router.callback_query(F.data == "filter_rating", SearchForm.filters)
async def set_rating_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    game = data['game']

    await callback.message.edit_text("🏆 Выберите рейтинг:", reply_markup=kb.ratings(game))
    await callback.answer()

@router.callback_query(F.data.startswith("rating_"), SearchForm.filters)
async def save_rating_filter(callback: CallbackQuery, state: FSMContext):
    rating = callback.data.split("_")[1]
    await state.update_data(rating_filter=rating)

    data = await state.get_data()
    rating_name = settings.RATINGS[data['game']].get(rating, rating)

    text = "🔍 Фильтры поиска:\n\n"
    text += f"🏆 Рейтинг: {rating_name}\n"
    text += "⚔️ Позиция: любая\n\n"
    text += "Настройте фильтры или начните поиск:"

    await callback.message.edit_text(text, reply_markup=kb.search_filters())
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

    await callback.message.edit_text("⚔️ Выберите позицию:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("pos_filter_"), SearchForm.filters)
async def save_position_filter(callback: CallbackQuery, state: FSMContext):
    position = callback.data.split("_")[2]
    await state.update_data(position_filter=position)

    data = await state.get_data()
    rating_text = "любой"
    if data.get('rating_filter'):
        rating_text = settings.RATINGS[data['game']].get(data['rating_filter'], data['rating_filter'])

    position_text = settings.POSITIONS[data['game']].get(position, position)

    text = "🔍 Фильтры поиска:\n\n"
    text += f"🏆 Рейтинг: {rating_text}\n"
    text += f"⚔️ Позиция: {position_text}\n\n"
    text += "Настройте фильтры или начните поиск:"

    await callback.message.edit_text(text, reply_markup=kb.search_filters())
    await callback.answer()

@router.callback_query(F.data == "cancel_filter", SearchForm.filters)
async def cancel_filter(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    rating_text = "любой"
    if data.get('rating_filter'):
        rating_text = settings.RATINGS[data['game']].get(data['rating_filter'], data['rating_filter'])

    position_text = "любая"
    if data.get('position_filter'):
        position_text = settings.POSITIONS[data['game']].get(data['position_filter'], data['position_filter'])

    text = "🔍 Фильтры поиска:\n\n"
    text += f"🏆 Рейтинг: {rating_text}\n"
    text += f"⚔️ Позиция: {position_text}\n\n"
    text += "Настройте фильтры или начните поиск:"

    await callback.message.edit_text(text, reply_markup=kb.search_filters())
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
        # await callback.message.edit_text(texts.NO_PROFILES, reply_markup=kb.back())
        await edit_text_with_photo(callback, texts.NO_PROFILES, kb.back())
        await callback.answer()
        return

    await state.set_state(SearchForm.browsing)
    await state.update_data(profiles=profiles, current_index=0)

    await show_current_profile(callback, state)

async def show_current_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    profiles = data['profiles']
    index = data['current_index']

    if index >= len(profiles):
        # await callback.message.edit_text(texts.NO_PROFILES, reply_markup=kb.back())
        # if callback.message.photo:
        #     await callback.message.edit_caption(
        #         caption=texts.NO_PROFILES,
        #         reply_markup=kb.back()
        #     )
        # else:
        #     await callback.message.edit_text(
        #         texts.NO_PROFILES,
        #         reply_markup=kb.back()
        #     )
        await edit_text_with_photo(callback, texts.NO_PROFILES, kb.back())
        await callback.answer()
        return

    profile = profiles[index]
    profile_text = texts.format_profile(profile)

    try:
        if profile.get('photo_id'):
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=profile_text,
                reply_markup=kb.profile_actions(profile['telegram_id'])
            )
        else:
            await callback.message.edit_text(
                profile_text,
                reply_markup=kb.profile_actions(profile['telegram_id'])
            )

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
    await show_next_profile(callback, state)

@router.callback_query(F.data.startswith("like_"), SearchForm.browsing)
async def like_profile(callback: CallbackQuery, state: FSMContext):
    try:
        target_user_id = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    data = await state.get_data()
    from_user_id = data['user_id']
    game = data['game']

    is_match = db.add_like(from_user_id, target_user_id, game)

    if is_match:
        target_user = db.get_user(target_user_id)

        if target_user and target_user.get('username'):
            contact_text = f"\n\n💬 @{target_user['username']}"
        else:
            contact_text = "\n\n(У пользователя нет @username)"

        text = texts.MATCH_CREATED + contact_text
        keyboard = kb.contact(target_user.get('username') if target_user else None)

        await callback.message.delete()
        # await callback.message.answer(text, reply_markup=keyboard)
        # await callback.message.edit_text(text, reply_markup=keyboard)
        await edit_text_with_photo(callback, text, keyboard)
        logger.info(f"Матч: {from_user_id} <-> {target_user_id}")
    else:
        # await callback.message.edit_text(
        #     texts.LIKE_SENT,
        #     reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
        #         [kb.InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="continue_search")],
        #         [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        #     ])
        # )
        # logger.info(f"Лайк: {from_user_id} -> {target_user_id}")
        # if callback.message.photo:
        #     await callback.message.edit_caption(
        #         caption=texts.LIKE_SENT,
        #         reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
        #             [kb.InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="continue_search")],
        #             [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        #         ])
        #     )
        # else:
        #     await callback.message.edit_text(
        #         texts.LIKE_SENT,
        #         reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
        #             [kb.InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="continue_search")],
        #             [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        #     ])
        #     )
        await edit_text_with_photo(callback, texts.LIKE_SENT,
            kb.InlineKeyboardMarkup(
                inline_keyboard=[
                    [kb.InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="continue_search")],
                    [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )
        logger.info(f"Лайк: {from_user_id} -> {target_user_id}")

    await callback.answer()

@router.callback_query(F.data == "continue_search", SearchForm.browsing)
async def continue_search(callback: CallbackQuery, state: FSMContext):
    """Продолжить поиск"""
    await show_next_profile(callback, state)