import logging
from enum import Enum
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from handlers.notifications import update_user_activity
from handlers.basic import check_ban_and_profile, safe_edit_message
from handlers.validation import validate_profile_input

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()

class ProfileForm(StatesGroup):
    name = State()
    nickname = State()
    age = State()
    rating = State()
    region = State()
    positions = State()
    additional_info = State()
    photo = State()

class ProfileStep(Enum):
    NAME = "name"
    NICKNAME = "nickname" 
    AGE = "age"
    RATING = "rating"
    REGION = "region"
    POSITIONS = "positions"
    INFO = "additional_info"
    PHOTO = "photo"

# Порядок шагов
PROFILE_STEPS_ORDER = [
    ProfileStep.NAME,
    ProfileStep.NICKNAME,
    ProfileStep.AGE,
    ProfileStep.RATING,
    ProfileStep.REGION,
    ProfileStep.POSITIONS,
    ProfileStep.INFO,
    ProfileStep.PHOTO
]

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def save_profile_universal(user_id: int, data: dict, photo_id: str = None, db = None) -> bool:
    """Универсальная функция сохранения профиля"""
    is_recreating = data.get('recreating', False)
    
    if is_recreating:
        old_profile = await db.get_user_profile(user_id, data['game'])
        if old_profile:
            await db.delete_profile(user_id, data['game'])
            logger.info(f"Старая анкета удалена при пересоздании: {user_id} в {data['game']}")
    
    success = await db.update_user_profile(
        telegram_id=user_id,
        game=data['game'],
        name=data['name'],
        nickname=data['nickname'],
        age=data['age'],
        rating=data['rating'],
        region=data.get('region', 'eeu'),
        positions=data['positions'],
        additional_info=data['additional_info'],
        photo_id=photo_id
    )

    if success:
        action = "пересоздан" if is_recreating else "создан"
        logger.info(f"Профиль {action} для {user_id} в {data['game']}")

    return success

async def get_step_question_text(step: ProfileStep, data: dict = None, show_current: bool = False) -> str:
    """Получить текст вопроса для шага"""
    if show_current and data:
        if step == ProfileStep.NAME:
            current = data.get('name', '')
            return f"Текущее имя и фамилия: <b>{current}</b>\n\nВведите новое имя и фамилию или нажмите 'Продолжить':"
        elif step == ProfileStep.NICKNAME:
            current = data.get('nickname', '')
            return f"Текущий игровой никнейм: <b>{current}</b>\n\nВведите новый никнейм или нажмите 'Продолжить':"
        elif step == ProfileStep.AGE:
            current = data.get('age', '')
            return f"Текущий возраст: <b>{current}</b>\n\nВведите новый возраст или нажмите 'Продолжить':"
        elif step == ProfileStep.RATING:
            current = data.get('rating', '')
            if current:
                game = data.get('game', 'dota')
                rating_name = settings.RATINGS[game].get(current, current)
                return f"Текущий рейтинг: <b>{rating_name}</b>\n\nВыберите новый рейтинг или продолжите с текущим:"
        elif step == ProfileStep.REGION:
            current = data.get('region', '')
            if current:
                region_name = settings.REGIONS.get(current, current)
                return f"Текущий регион: <b>{region_name}</b>\n\nВыберите новый регион или продолжите с текущим:"
        elif step == ProfileStep.POSITIONS:
            current = data.get('positions_selected', [])
            if current:
                game = data.get('game', 'dota')
                if "any" in current:
                    pos_text = "Любая позиция"
                else:
                    position_names = [settings.POSITIONS[game].get(pos, pos) for pos in current]
                    pos_text = ", ".join(position_names)
                return f"Текущие позиции: <b>{pos_text}</b>\n\nИзмените выбор или продолжите с текущими:"
        elif step == ProfileStep.INFO:
            current = data.get('additional_info', '')
            if current:
                return f"Текущее описание: <b>{current}</b>\n\nВведите новое описание или нажмите 'Продолжить':"
            else:
                return "Описание не задано.\n\nВведите описание или нажмите 'Продолжить':"
        elif step == ProfileStep.PHOTO:
            current = data.get('photo_id', '')
            if current:
                return "Фото загружено.\n\nОтправьте новое фото или нажмите 'Продолжить':"
            else:
                return "Фото не загружено.\n\nОтправьте фото или нажмите 'Продолжить':"
    
    if step == ProfileStep.NAME:
        return texts.QUESTIONS['name']
    elif step == ProfileStep.NICKNAME:
        return texts.QUESTIONS['nickname'] 
    elif step == ProfileStep.AGE:
        return texts.QUESTIONS['age']
    elif step == ProfileStep.INFO:
        return "Введите описание или нажмите 'Пропустить':"
    elif step == ProfileStep.PHOTO:
        return texts.QUESTIONS['photo']
    elif step == ProfileStep.RATING:
        return "Выберите рейтинг:"
    elif step == ProfileStep.REGION:
        return "Выберите регион:"
    elif step == ProfileStep.POSITIONS:
        return "Выберите позиции (можно несколько):"
    
    return "Вопрос"

async def show_profile_step(callback_or_message, state: FSMContext, step: ProfileStep, show_current: bool = False):
    """Показать шаг создания профиля"""
    data = await state.get_data()
    game = data.get('game', 'dota')
    
    has_data = False
    if step == ProfileStep.NAME and data.get('name'):
        has_data = True
    elif step == ProfileStep.NICKNAME and data.get('nickname'):
        has_data = True
    elif step == ProfileStep.AGE and data.get('age'):
        has_data = True
    elif step == ProfileStep.RATING and data.get('rating'):
        has_data = True
    elif step == ProfileStep.REGION and data.get('region'):
        has_data = True
    elif step == ProfileStep.POSITIONS and data.get('positions_selected'):
        has_data = True
    elif step == ProfileStep.INFO and 'additional_info' in data:
        has_data = True
    elif step == ProfileStep.PHOTO and data.get('photo_id'):
        has_data = True
    
    await state.update_data(current_step=step.value)
    
    show_existing_data = has_data and show_current
    question_text = await get_step_question_text(step, data, show_existing_data)
    
    game_name = settings.GAMES.get(game, game)
    text = f"Создание анкеты для {game_name}\n\n{question_text}"
    
    show_continue_button = show_existing_data
    
    if step == ProfileStep.NAME:
        await state.set_state(ProfileForm.name)
        keyboard = kb.profile_creation_navigation(step.value, show_continue_button)
        
    elif step == ProfileStep.NICKNAME:
        await state.set_state(ProfileForm.nickname)
        keyboard = kb.profile_creation_navigation(step.value, show_continue_button)
        
    elif step == ProfileStep.AGE:
        await state.set_state(ProfileForm.age)
        keyboard = kb.profile_creation_navigation(step.value, show_continue_button)
        
    elif step == ProfileStep.RATING:
        await state.set_state(ProfileForm.rating)
        current_rating = data.get('rating') if show_existing_data else None
        keyboard = kb.ratings(game, selected_rating=current_rating, with_navigation=True)
        
    elif step == ProfileStep.REGION:
        await state.set_state(ProfileForm.region)
        current_region = data.get('region') if show_existing_data else None
        keyboard = kb.regions(selected_region=current_region, with_navigation=True)
        
    elif step == ProfileStep.POSITIONS:
        await state.set_state(ProfileForm.positions)
        selected = data.get('positions_selected', []) if show_existing_data else []
        keyboard = kb.positions(game, selected=selected, with_navigation=True)

    elif step == ProfileStep.INFO:
        await state.set_state(ProfileForm.additional_info)
        if show_continue_button:
            keyboard = kb.profile_creation_navigation(step.value, show_continue_button)
        else:
            keyboard = kb.skip_info()

    elif step == ProfileStep.PHOTO:
        await state.set_state(ProfileForm.photo)
        if show_continue_button:
            keyboard = kb.profile_creation_navigation(step.value, show_continue_button)
        else:
            keyboard = kb.skip_photo()
    
    if hasattr(callback_or_message, 'message'):
        await safe_edit_message(callback_or_message, text, keyboard)
    else:
        await callback_or_message.answer(text, reply_markup=keyboard, parse_mode='HTML')

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "create_profile")
@check_ban_and_profile(require_profile=False)
async def start_create_profile(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("Ошибка", show_alert=True)
        return

    await update_user_activity(user_id, 'profile_creation', db)

    game = user['current_game']

    await state.clear()
    await state.update_data(
        user_id=user_id,
        game=game,
        positions_selected=[],
        current_step=ProfileStep.NAME.value
    )
    
    await show_profile_step(callback, state, ProfileStep.NAME)
    await callback.answer()

@router.callback_query(F.data == "profile_back")
async def profile_go_back(callback: CallbackQuery, state: FSMContext):
    """Переход к предыдущему шагу"""
    data = await state.get_data()
    current_step = data.get('current_step', ProfileStep.NAME.value)
    
    try:
        current_step_enum = ProfileStep(current_step)
        current_index = PROFILE_STEPS_ORDER.index(current_step_enum)
        
        if current_index > 0:
            prev_step = PROFILE_STEPS_ORDER[current_index - 1]
            await show_profile_step(callback, state, prev_step, show_current=True)
        else:
            await callback.answer("Это первый шаг", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка навигации назад: {e}")
        await callback.answer("Ошибка навигации", show_alert=True)
    
    await callback.answer()

# Заменить в handlers/profile.py

@router.callback_query(F.data == "profile_continue")
async def profile_continue(callback: CallbackQuery, state: FSMContext, db):
    """Продолжить с текущими данными"""
    data = await state.get_data()
    current_step = data.get('current_step', ProfileStep.NAME.value)
    
    try:
        current_step_enum = ProfileStep(current_step)
        current_index = PROFILE_STEPS_ORDER.index(current_step_enum)
        
        if current_index < len(PROFILE_STEPS_ORDER) - 1:
            next_step = PROFILE_STEPS_ORDER[current_index + 1]
            
            # Проверяем есть ли данные на следующем шаге
            next_has_data = False
            if next_step == ProfileStep.NAME and data.get('name'):
                next_has_data = True
            elif next_step == ProfileStep.NICKNAME and data.get('nickname'):
                next_has_data = True
            elif next_step == ProfileStep.AGE and data.get('age'):
                next_has_data = True
            elif next_step == ProfileStep.RATING and data.get('rating'):
                next_has_data = True
            elif next_step == ProfileStep.REGION and data.get('region'):
                next_has_data = True
            elif next_step == ProfileStep.POSITIONS and data.get('positions_selected'):
                next_has_data = True
            elif next_step == ProfileStep.INFO and 'additional_info' in data:
                next_has_data = True
            elif next_step == ProfileStep.PHOTO and data.get('photo_id'):
                next_has_data = True
            
            # Если на следующем шаге есть данные - показываем их
            await show_profile_step(callback, state, next_step, show_current=next_has_data)
        else:
            # Последний шаг - сохраняем профиль
            await save_profile_flow_callback(callback, state, None, db)
    except Exception as e:
        logger.error(f"Ошибка продолжения: {e}")
        await callback.answer("Ошибка", show_alert=True)
    
    await callback.answer()

# ==================== ОБРАБОТЧИКИ ТЕКСТОВЫХ СООБЩЕНИЙ ====================

@router.message(ProfileForm.name)
async def process_name(message: Message, state: FSMContext):
    """Обработка имени"""
    if not message.text:
        await message.answer("Отправьте текстовое сообщение с именем и фамилией", parse_mode='HTML')
        return

    name = message.text.strip()
    is_valid, error_msg = validate_profile_input('name', name)

    if not is_valid:
        await message.answer(error_msg, parse_mode='HTML')
        return

    await state.update_data(name=name)
    
    # Проверяем есть ли данные на следующем шаге (nickname)
    data = await state.get_data()
    has_next_data = bool(data.get('nickname'))
    
    # Показываем следующий шаг с учетом наличия данных
    await show_profile_step(message, state, ProfileStep.NICKNAME, show_current=has_next_data)

@router.message(ProfileForm.name, ~F.text)
async def wrong_name_format(message: Message):
    await message.answer("Отправьте текстовое сообщение с именем и фамилией", parse_mode='HTML')

@router.message(ProfileForm.nickname)
async def process_nickname(message: Message, state: FSMContext):
    """Обработка никнейма"""
    if not message.text:
        await message.answer("Отправьте текстовое сообщение с игровым никнеймом", parse_mode='HTML')
        return

    nickname = message.text.strip()
    is_valid, error_msg = validate_profile_input('nickname', nickname)

    if not is_valid:
        await message.answer(error_msg, parse_mode='HTML')
        return

    await state.update_data(nickname=nickname)
    
    # Проверяем есть ли данные на следующем шаге (age)
    data = await state.get_data()
    has_next_data = bool(data.get('age'))
    
    # Показываем следующий шаг с учетом наличия данных
    await show_profile_step(message, state, ProfileStep.AGE, show_current=has_next_data)

@router.message(ProfileForm.nickname, ~F.text)
async def wrong_nickname_format(message: Message):
    await message.answer("Отправьте текстовое сообщение с игровым никнеймом", parse_mode='HTML')

@router.message(ProfileForm.age)
async def process_age(message: Message, state: FSMContext):
    """Обработка возраста"""
    if not message.text:
        await message.answer(f"Отправьте число больше {settings.MIN_AGE}", parse_mode='HTML')
        return

    is_valid, error_msg = validate_profile_input('age', message.text.strip())

    if not is_valid:
        await message.answer(error_msg, parse_mode='HTML')
        return

    age = int(message.text.strip())
    await state.update_data(age=age)
    
    # Проверяем есть ли данные на следующем шаге (rating)
    data = await state.get_data()
    has_next_data = bool(data.get('rating'))
    
    # Показываем следующий шаг с учетом наличия данных
    await show_profile_step(message, state, ProfileStep.RATING, show_current=has_next_data)

@router.message(ProfileForm.age, ~F.text)
async def wrong_age_format(message: Message):
    await message.answer(f"Отправьте число больше {settings.MIN_AGE}", parse_mode='HTML')

@router.message(ProfileForm.additional_info)
async def process_additional_info(message: Message, state: FSMContext):
    """Обработка дополнительной информации"""
    if not message.text:
        await message.answer("Отправьте текстовое сообщение с описанием или используйте кнопки", parse_mode='HTML')
        return

    info = message.text.strip()
    is_valid, error_msg = validate_profile_input('info', info)

    if not is_valid:
        await message.answer(error_msg, parse_mode='HTML')
        return

    await state.update_data(additional_info=info)
    
    # Проверяем есть ли данные на следующем шаге (photo)
    data = await state.get_data()
    has_next_data = bool(data.get('photo_id'))
    
    # Показываем следующий шаг с учетом наличия данных
    await show_profile_step(message, state, ProfileStep.PHOTO, show_current=has_next_data)

@router.message(ProfileForm.additional_info, ~F.text)
async def wrong_info_format(message: Message):
    await message.answer("Отправьте текстовое сообщение с описанием или нажмите 'Пропустить'", parse_mode='HTML')

@router.message(ProfileForm.photo, F.photo)
async def process_photo(message: Message, state: FSMContext, db):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    
    # Фото - последний шаг, сохраняем профиль
    await save_profile_flow(message, state, photo_id, db)

@router.message(ProfileForm.photo)
async def wrong_photo_format(message: Message):
    await message.answer("Отправьте фотографию или нажмите 'Пропустить'", reply_markup=kb.skip_photo(), parse_mode='HTML')

# ==================== ОБРАБОТЧИКИ CALLBACK ====================

@router.callback_query(F.data == "rating_select_any", ProfileForm.rating)
async def select_any_rating(callback: CallbackQuery, state: FSMContext):
    """Выбор любого рейтинга"""
    data = await state.get_data()
    game = data['game']
    current_rating = data.get('rating')
    
    # Если уже выбран "any" - ничего не делаем
    if current_rating == "any":
        await callback.answer("Уже выбрано 'Любой рейтинг'")
        return
    
    await state.update_data(rating="any")
    
    # Обновляем клавиатуру
    keyboard = kb.ratings(game, selected_rating="any", with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры рейтинга: {e}")
    
    await callback.answer()

@router.callback_query(F.data == "rating_remove_any", ProfileForm.rating)
async def remove_any_rating(callback: CallbackQuery, state: FSMContext):
    """Сброс выбора любого рейтинга"""
    data = await state.get_data()
    game = data['game']
    current_rating = data.get('rating')
    
    # Если "any" не выбран - ничего не делаем
    if current_rating != "any":
        await callback.answer("'Любой рейтинг' не выбран")
        return
    
    # Убираем рейтинг из state
    if 'rating' in data:
        del data['rating']
        await state.set_data(data)
    
    # Обновляем клавиатуру
    keyboard = kb.ratings(game, selected_rating=None, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры рейтинга: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("rating_select_"), ProfileForm.rating)
async def select_rating(callback: CallbackQuery, state: FSMContext):
    """Выбор рейтинга"""
    rating = callback.data.split("_", 2)[2]  # Более безопасный парсинг
    data = await state.get_data()
    game = data['game']
    current_rating = data.get('rating')
    
    # Если уже выбран этот же рейтинг - ничего не делаем
    if current_rating == rating:
        await callback.answer("Этот рейтинг уже выбран")
        return
    
    await state.update_data(rating=rating)
    
    # Обновляем клавиатуру только если что-то изменилось
    keyboard = kb.ratings(game, selected_rating=rating, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры рейтинга: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("rating_remove_"), ProfileForm.rating)
async def remove_rating(callback: CallbackQuery, state: FSMContext):
    """Сброс выбора рейтинга"""
    rating = callback.data.split("_", 2)[2]
    data = await state.get_data()
    game = data['game']
    current_rating = data.get('rating')
    
    # Если этот рейтинг не выбран - ничего не делаем
    if current_rating != rating:
        await callback.answer("Этот рейтинг не выбран")
        return
    
    # Убираем рейтинг из state
    if 'rating' in data:
        del data['rating']
        await state.set_data(data)
    
    # Обновляем клавиатуру
    keyboard = kb.ratings(game, selected_rating=None, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры рейтинга: {e}")
    
    await callback.answer()

@router.callback_query(F.data == "rating_done", ProfileForm.rating)
async def rating_done(callback: CallbackQuery, state: FSMContext):
    """Подтверждение выбора рейтинга"""
    data = await state.get_data()
    if not data.get('rating'):
        await callback.answer("Выберите рейтинг", show_alert=True)
        return
    
    # Проверяем есть ли данные на следующем шаге (region)
    has_next_data = bool(data.get('region'))
    
    # Показываем следующий шаг с учетом наличия данных
    await show_profile_step(callback, state, ProfileStep.REGION, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "rating_need", ProfileForm.rating)
async def rating_need(callback: CallbackQuery):
    """Напоминание о необходимости выбора рейтинга"""
    await callback.answer("Выберите рейтинг", show_alert=True)

@router.callback_query(F.data == "region_select_any", ProfileForm.region)
async def select_any_region(callback: CallbackQuery, state: FSMContext):
    """Выбор любого региона"""
    data = await state.get_data()
    current_region = data.get('region')
    
    # Если уже выбран "any" - ничего не делаем
    if current_region == "any":
        await callback.answer("Уже выбрано 'Любой регион'")
        return
    
    await state.update_data(region="any")
    
    # Обновляем клавиатуру
    keyboard = kb.regions(selected_region="any", with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры региона: {e}")
    
    await callback.answer()

@router.callback_query(F.data == "region_remove_any", ProfileForm.region)
async def remove_any_region(callback: CallbackQuery, state: FSMContext):
    """Сброс выбора любого региона"""
    data = await state.get_data()
    current_region = data.get('region')
    
    # Если "any" не выбран - ничего не делаем
    if current_region != "any":
        await callback.answer("'Любой регион' не выбран")
        return
    
    # Убираем регион из state
    if 'region' in data:
        del data['region']
        await state.set_data(data)
    
    # Обновляем клавиатуру
    keyboard = kb.regions(selected_region=None, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры региона: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("region_select_"), ProfileForm.region)
async def select_region(callback: CallbackQuery, state: FSMContext):
    """Выбор региона"""
    region = callback.data.split("_", 2)[2]
    data = await state.get_data()
    current_region = data.get('region')
    
    # Если уже выбран этот же регион - ничего не делаем
    if current_region == region:
        await callback.answer("Этот регион уже выбран")
        return
    
    await state.update_data(region=region)
    
    # Обновляем клавиатуру
    keyboard = kb.regions(selected_region=region, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры региона: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("region_remove_"), ProfileForm.region)
async def remove_region(callback: CallbackQuery, state: FSMContext):
    """Сброс выбора региона"""
    region = callback.data.split("_", 2)[2]
    data = await state.get_data()
    current_region = data.get('region')
    
    # Если этот регион не выбран - ничего не делаем
    if current_region != region:
        await callback.answer("Этот регион не выбран")
        return
    
    # Убираем регион из state
    if 'region' in data:
        del data['region']
        await state.set_data(data)
    
    # Обновляем клавиатуру
    keyboard = kb.regions(selected_region=None, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры региона: {e}")
    
    await callback.answer()

@router.callback_query(F.data == "region_done", ProfileForm.region)
async def region_done(callback: CallbackQuery, state: FSMContext):
    """Подтверждение выбора региона"""
    data = await state.get_data()
    if not data.get('region'):
        await callback.answer("Выберите регион", show_alert=True)
        return
    
    # Проверяем есть ли данные на следующем шаге (positions)
    has_next_data = bool(data.get('positions_selected'))
    
    # Показываем следующий шаг с учетом наличия данных
    await show_profile_step(callback, state, ProfileStep.POSITIONS, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "region_need", ProfileForm.region)
async def region_need(callback: CallbackQuery):
    """Напоминание о необходимости выбора региона"""
    await callback.answer("Выберите регион", show_alert=True)

@router.callback_query(F.data == "pos_add_any", ProfileForm.positions)
async def add_any_position(callback: CallbackQuery, state: FSMContext):
    """Добавление 'любой позиции'"""
    data = await state.get_data()
    game = data['game']
    
    # Устанавливаем только "any"
    await state.update_data(positions_selected=["any"])
    
    # Обновляем клавиатуру
    keyboard = kb.positions(game, ["any"], with_navigation=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "pos_remove_any", ProfileForm.positions)
async def remove_any_position(callback: CallbackQuery, state: FSMContext):
    """Удаление 'любой позиции'"""
    data = await state.get_data()
    game = data['game']
    
    # Убираем "any"
    selected = data.get('positions_selected', [])
    if "any" in selected:
        selected.remove("any")
    
    await state.update_data(positions_selected=selected)
    
    # Обновляем клавиатуру
    keyboard = kb.positions(game, selected, with_navigation=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("pos_add_"), ProfileForm.positions)
async def add_position(callback: CallbackQuery, state: FSMContext):
    """Добавление позиции"""
    position = callback.data.split("_", 2)[2]
    data = await state.get_data()
    selected = data.get('positions_selected', [])
    game = data['game']
    
    # Если позиция уже выбрана - ничего не делаем
    if position in selected:
        await callback.answer("Эта позиция уже выбрана")
        return

    if position == "any":
        selected = ["any"]
    else:
        if "any" in selected:
            selected.remove("any")
        selected.append(position)
    
    await state.update_data(positions_selected=selected)

    # Обновляем клавиатуру
    keyboard = kb.positions(game, selected, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры позиций: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("pos_remove_"), ProfileForm.positions)
async def remove_position(callback: CallbackQuery, state: FSMContext):
    """Удаление позиции"""
    position = callback.data.split("_", 2)[2]
    data = await state.get_data()
    selected = data.get('positions_selected', [])
    game = data['game']

    # Если позиция не выбрана - ничего не делаем
    if position not in selected:
        await callback.answer("Эта позиция не выбрана")
        return

    selected.remove(position)
    await state.update_data(positions_selected=selected)

    # Обновляем клавиатуру
    keyboard = kb.positions(game, selected, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры позиций: {e}")
    
    await callback.answer()

@router.callback_query(F.data == "pos_done", ProfileForm.positions)
async def positions_done(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора позиций"""
    data = await state.get_data()
    selected = data.get('positions_selected', [])

    if not selected:
        await callback.answer("Выберите хотя бы одну позицию", show_alert=True)
        return

    await state.update_data(positions=selected)
    
    # Проверяем есть ли данные на следующем шаге (info)
    has_next_data = 'additional_info' in data
    
    # Показываем следующий шаг с учетом наличия данных
    await show_profile_step(callback, state, ProfileStep.INFO, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "pos_need", ProfileForm.positions)
async def positions_need(callback: CallbackQuery):
    await callback.answer("Выберите хотя бы одну позицию", show_alert=True)

@router.callback_query(F.data == "skip_info", ProfileForm.additional_info)
async def skip_info(callback: CallbackQuery, state: FSMContext):
    """Пропуск дополнительной информации"""
    await state.update_data(additional_info="")
    
    # Проверяем есть ли данные на следующем шаге (photo)
    data = await state.get_data()
    has_next_data = bool(data.get('photo_id'))
    
    # Показываем следующий шаг с учетом наличия данных
    await show_profile_step(callback, state, ProfileStep.PHOTO, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "skip_photo", ProfileForm.photo)
async def skip_photo(callback: CallbackQuery, state: FSMContext, db):
    await save_profile_flow_callback(callback, state, None, db)

@router.callback_query(F.data == "cancel")
async def confirm_cancel_profile(callback: CallbackQuery, state: FSMContext):
    """Подтверждение отмены создания профиля"""
    data = await state.get_data()
    game_name = settings.GAMES.get(data.get('game', 'dota'), 'игры')
    
    text = (f"Отменить создание анкеты?\n\n"
            f"Вся введенная информация для {game_name} будет потеряна.\n\n"
            f"Вы уверены?")
    
    await safe_edit_message(callback, text, kb.confirm_cancel_profile())
    await callback.answer()

@router.callback_query(F.data == "confirm_cancel")
async def cancel_profile_confirmed(callback: CallbackQuery, state: FSMContext, db):
    """Подтвержденная отмена создания профиля"""
    data = await state.get_data()
    is_recreating = data.get('recreating', False)
    
    await state.clear()
    
    user_id = callback.from_user.id
    await update_user_activity(user_id, 'available', db)
    
    user = await db.get_user(user_id)
    if user and user.get('current_game'):
        game = user['current_game']
        profile = await db.get_user_profile(user_id, game)
        has_profile = profile is not None
        
        if is_recreating and has_profile:
            game_name = settings.GAMES.get(game, game)
            profile_text = texts.format_profile(profile, show_contact=True)
            text = f"Ваша анкета в {game_name}:\n\n{profile_text}"

            keyboard = kb.view_profile_menu()

            try:
                if profile.get('photo_id'):
                    await callback.message.delete()
                    await callback.message.answer_photo(
                        photo=profile['photo_id'],
                        caption=text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                else:
                    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Ошибка отображения профиля при отмене пересоздания: {e}")
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')
            
            await callback.answer("Возвращение к анкете")
        else:
            from handlers.basic import get_main_menu_text
            text = get_main_menu_text(game, has_profile)
            await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
            await callback.answer("Создание анкеты отменено")
    else:
        await safe_edit_message(callback, "Создание анкеты отменено", kb.back())
        await callback.answer("Создание анкеты отменено")

@router.callback_query(F.data == "continue_profile")
async def continue_profile_creation(callback: CallbackQuery, state: FSMContext):
    """Продолжить создание профиля"""
    data = await state.get_data()
    current_step = data.get('current_step', ProfileStep.NAME.value)
    
    try:
        current_step_enum = ProfileStep(current_step)
        
        # Проверяем есть ли данные для ТЕКУЩЕГО шага
        has_current_data = False
        if current_step_enum == ProfileStep.NAME and data.get('name'):
            has_current_data = True
        elif current_step_enum == ProfileStep.NICKNAME and data.get('nickname'):
            has_current_data = True
        elif current_step_enum == ProfileStep.AGE and data.get('age'):
            has_current_data = True
        elif current_step_enum == ProfileStep.RATING and data.get('rating'):
            has_current_data = True
        elif current_step_enum == ProfileStep.REGION and data.get('region'):
            has_current_data = True
        elif current_step_enum == ProfileStep.POSITIONS and data.get('positions_selected'):
            has_current_data = True
        elif current_step_enum == ProfileStep.INFO and 'additional_info' in data:
            has_current_data = True
        elif current_step_enum == ProfileStep.PHOTO and data.get('photo_id'):
            has_current_data = True
        
        await show_profile_step(callback, state, current_step_enum, show_current=has_current_data)
        
    except Exception as e:
        logger.error(f"Ошибка возврата к созданию профиля: {e}")
        await show_profile_step(callback, state, ProfileStep.NAME)
    
    await callback.answer("Продолжаем создание анкеты")

# ==================== СОХРАНЕНИЕ ПРОФИЛЯ ====================

async def save_profile_flow(message: Message, state: FSMContext, photo_id: str | None, db):
    """Финал создания анкеты: сохранение и показ результата."""
    user_id = message.from_user.id
    data = await state.get_data()
    is_recreating = data.get('recreating', False)

    payload = {
        'game': data.get('game'),
        'name': data.get('name', '').strip(),
        'nickname': data.get('nickname', '').strip(),
        'age': data.get('age'),
        'rating': data.get('rating'),
        'region': data.get('region', 'eeu'),
        'positions': data.get('positions', []) or data.get('positions_selected', []),
        'additional_info': data.get('additional_info', '').strip(),
        'recreating': is_recreating
    }

    if not payload['positions']:
        payload['positions'] = ['any']

    success = await save_profile_universal(
        user_id=user_id,
        data=payload,
        photo_id=photo_id,
        db=db
    )

    if not success:
        await message.answer("Не удалось сохранить анкету. Попробуйте ещё раз.", parse_mode='HTML')
        return

    await state.clear()
    await update_user_activity(user_id, 'available', db)

    profile = await db.get_user_profile(user_id, payload['game'])
    game_name = settings.GAMES.get(payload['game'], payload['game'])

    if profile:
        if is_recreating:
            text = f"Новая анкета для {game_name} создана! Старая анкета была заменена.\n\n" + texts.format_profile(profile, show_contact=True)
        else:
            text = f"Анкета для {game_name} создана!\n\n" + texts.format_profile(profile, show_contact=True)

        if profile.get('photo_id'):
            await message.answer_photo(photo=profile['photo_id'], caption=text, reply_markup=kb.back(), parse_mode='HTML')
        else:
            await message.answer(text, reply_markup=kb.back(), parse_mode='HTML')
    else:
        action = "пересоздана" if is_recreating else "создана"
        text = f"Анкета для {game_name} {action}!"
        await message.answer(text, reply_markup=kb.back(), parse_mode='HTML')

async def save_profile_flow_callback(callback: CallbackQuery, state: FSMContext, photo_id: str, db):
    """Сохранение профиля через callback"""
    data = await state.get_data()
    user_id = data.get('user_id', callback.from_user.id)
    is_recreating = data.get('recreating', False)

    success = await save_profile_universal(
        user_id=user_id,
        data=data,
        photo_id=photo_id,
        db=db
    )
    await state.clear()

    if success:
        game_name = settings.GAMES.get(data['game'], data['game'])
        if is_recreating:
            text = f"Новая анкета для {game_name} создана! Старая анкета была заменена."
        else:
            text = f"Анкета для {game_name} создана! Теперь можете искать сокомандников."
        await safe_edit_message(callback, text, kb.back())
    else:
        await safe_edit_message(callback, "Ошибка сохранения", kb.back())

    await callback.answer()