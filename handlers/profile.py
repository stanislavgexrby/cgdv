import logging
from aiogram.types import Message, CallbackQuery
from aiogram import Router, F
from aiogram.fsm.context import FSMContext

from handlers.notifications import update_user_activity
from handlers.basic import check_ban_and_profile, safe_edit_message
from handlers.validation import validate_profile_input, show_validation_error
from handlers.profile_enum import PROFILE_STEPS_ORDER, ProfileForm, ProfileStep, show_profile_step

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()

async def save_profile_unified(user_id: int, data: dict, photo_id: str = None, 
                             callback: CallbackQuery = None, message: Message = None, 
                             state: FSMContext = None, db = None) -> bool:
    """Единая функция сохранения профиля с универсальным выводом результата"""
    if not db:
        logger.error("База данных не передана в save_profile_unified")
        return False
    
    is_recreating = data.get('recreating', False)
    
    if is_recreating:
        old_profile = await db.get_user_profile(user_id, data['game'])
        if old_profile:
            await db.delete_profile(user_id, data['game'])
            logger.info(f"Старая анкета удалена при пересоздании: {user_id} в {data['game']}")
    
    profile_url = data.get('profile_url', '')
    goals = data.get('goals', []) or data.get('goals_selected', [])
    if not goals:
        goals = ['any']
    
    positions = data.get('positions', []) or data.get('positions_selected', [])
    if not positions:
        positions = ['any']
    
    success = await db.update_user_profile(
        telegram_id=user_id,
        game=data['game'],
        name=data['name'],
        nickname=data['nickname'],
        age=data['age'],
        rating=data['rating'],
        region=data.get('region', 'eeu'),
        positions=positions,
        goals=goals,
        additional_info=data.get('additional_info', ''),
        photo_id=photo_id,
        profile_url=profile_url
    )
    
    if state:
        await state.clear()
    await update_user_activity(user_id, 'available', db)
    
    game_name = settings.GAMES.get(data['game'], data['game'])
    if is_recreating:
        result_text = f"Новая анкета для {game_name} создана! Старая анкета была заменена"
    else:
        result_text = f"Анкета для {game_name} создана! Теперь можете искать сокомандников"
    
    if not success:
        await _show_save_error(callback, message, data)
        return False
    else:
        await _show_save_result(callback, message, data, result_text)
    
    action = "пересоздан" if is_recreating else "создан"
    logger.info(f"Профиль {action} для {user_id} в {data['game']}")
    return True

async def _show_save_error(callback: CallbackQuery, message: Message, data: dict):
    """Показ ошибки сохранения профиля"""
    error_text = "❌ Не удалось сохранить анкету! Попробуйте ещё раз"
    
    if callback:
        try:
            await callback.message.edit_text(text=error_text, reply_markup=kb.back(), parse_mode='HTML')
        except Exception as e:
            logger.error(f"Ошибка показа ошибки через callback: {e}")
    elif message:
        last_message_id = data.get('last_bot_message_id')
        if last_message_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=last_message_id,
                    text=error_text,
                    reply_markup=kb.skip_photo(),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Не удалось показать ошибку в сообщении {last_message_id}: {e}")

async def _show_save_result(callback: CallbackQuery, message: Message, data: dict, result_text: str):
    """Показ результата сохранения профиля"""
    if callback:
        try:
            await callback.message.edit_text(text=result_text, reply_markup=kb.back(), parse_mode='HTML')
        except Exception as e:
            logger.error(f"Ошибка показа результата через callback: {e}")
    elif message:
        last_message_id = data.get('last_bot_message_id')
        if last_message_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=last_message_id,
                    text=result_text,
                    reply_markup=kb.back(),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Не удалось отредактировать сообщение завершения: {e}")

@router.callback_query(F.data == "create_profile")
@check_ban_and_profile(require_profile=False)
async def start_create_profile(callback: CallbackQuery, state: FSMContext, db):
    """Начало создания нового профиля"""
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
        goals_selected=[],
        current_step=ProfileStep.NAME.value
    )
    
    try:
        for i in range(10):
            try:
                await callback.bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id - i
                )
            except Exception:
                break
    except Exception:
        pass
    
    text = texts.QUESTIONS['name']
    keyboard = kb.profile_creation_navigation("name", False)
    
    sent_message = await callback.message.answer(
        text=text,
        reply_markup=keyboard,
        parse_mode='HTML',
        disable_web_page_preview=True
    )
    
    await state.update_data(last_bot_message_id=sent_message.message_id)
    await state.set_state(ProfileForm.name)
    
    logger.info(f"Сохранен last_bot_message_id: {sent_message.message_id}")
    await callback.answer()

@router.callback_query(F.data == "profile_back")
async def profile_go_back(callback: CallbackQuery, state: FSMContext):
    """Переход к предыдущему шагу создания профиля"""
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

@router.callback_query(F.data == "profile_continue")
async def profile_continue(callback: CallbackQuery, state: FSMContext, db):
    """Продолжить создание профиля с текущими данными"""
    data = await state.get_data()
    current_step = data.get('current_step', ProfileStep.NAME.value)
    
    try:
        current_step_enum = ProfileStep(current_step)
        current_index = PROFILE_STEPS_ORDER.index(current_step_enum)
        
        if current_index < len(PROFILE_STEPS_ORDER) - 1:
            next_step = PROFILE_STEPS_ORDER[current_index + 1]
            
            next_has_data = False
            if next_step == ProfileStep.NAME and data.get('name'):
                next_has_data = True
            elif next_step == ProfileStep.NICKNAME and data.get('nickname'):
                next_has_data = True
            elif next_step == ProfileStep.AGE and data.get('age'):
                next_has_data = True
            elif next_step == ProfileStep.RATING and data.get('rating'):
                next_has_data = True
            elif next_step == ProfileStep.PROFILE_URL and data.get('profile_url') is not None:
                next_has_data = True
            elif next_step == ProfileStep.REGION and data.get('region'):
                next_has_data = True
            elif next_step == ProfileStep.POSITIONS and data.get('positions_selected'):
                next_has_data = True
            elif next_step == ProfileStep.GOALS and data.get('goals_selected'):
                next_has_data = True
            elif next_step == ProfileStep.INFO and 'additional_info' in data:
                next_has_data = True
            elif next_step == ProfileStep.PHOTO and data.get('photo_id'):
                next_has_data = True
            
            await show_profile_step(callback, state, next_step, show_current=next_has_data)
        else:
            user_id = data.get('user_id', callback.from_user.id)
            await save_profile_unified(
                user_id=user_id,
                data=data,
                photo_id=data.get('photo_id'),
                callback=callback,
                state=state,
                db=db
            )
    except Exception as e:
        logger.error(f"Ошибка продолжения: {e}")
        await callback.answer("Ошибка", show_alert=True)
        return
    
    await callback.answer()

@router.message(ProfileForm.name)
async def process_name(message: Message, state: FSMContext):
    """Обработка введенного имени и фамилии"""
    if not message.text:
        await show_validation_error(message, state, "Отправьте текстовое сообщение с именем и фамилией")
        return

    name = message.text.strip()
    is_valid, error_msg = validate_profile_input('name', name)

    if not is_valid:
        await show_validation_error(message, state, error_msg)
        return

    await state.update_data(name=name)
    
    data = await state.get_data()
    has_next_data = bool(data.get('nickname'))
    
    await show_profile_step(message, state, ProfileStep.NICKNAME, show_current=has_next_data)

@router.message(ProfileForm.name, ~F.text)
async def wrong_name_format(message: Message, state: FSMContext):
    """Обработка неправильного формата имени"""
    await show_validation_error(message, state, "Отправьте текстовое сообщение с именем и фамилией")

@router.message(ProfileForm.nickname)
async def process_nickname(message: Message, state: FSMContext):
    """Обработка введенного игрового никнейма"""
    if not message.text:
        await show_validation_error(message, state, "Отправьте текстовое сообщение с игровым никнеймом")
        return

    nickname = message.text.strip()
    is_valid, error_msg = validate_profile_input('nickname', nickname)

    if not is_valid:
        await show_validation_error(message, state, error_msg)
        return

    await state.update_data(nickname=nickname)
    
    data = await state.get_data()
    has_next_data = bool(data.get('age'))
    
    await show_profile_step(message, state, ProfileStep.AGE, show_current=has_next_data)

@router.message(ProfileForm.nickname, ~F.text)
async def wrong_nickname_format(message: Message, state: FSMContext):
    """Обработка неправильного формата никнейма"""
    await show_validation_error(message, state, "Отправьте текстовое сообщение с игровым никнеймом")

@router.message(ProfileForm.age)
async def process_age(message: Message, state: FSMContext):
    """Обработка введенного возраста"""
    if not message.text:
        await show_validation_error(message, state, f"Отправьте число больше {settings.MIN_AGE}")
        return

    is_valid, error_msg = validate_profile_input('age', message.text.strip())

    if not is_valid:
        await show_validation_error(message, state, error_msg)
        return

    age = int(message.text.strip())
    await state.update_data(age=age)
    
    data = await state.get_data()
    has_next_data = bool(data.get('rating'))
    
    await show_profile_step(message, state, ProfileStep.RATING, show_current=has_next_data)

@router.message(ProfileForm.age, ~F.text)
async def wrong_age_format(message: Message, state: FSMContext):
    """Обработка неправильного формата возраста"""
    await show_validation_error(message, state, f"Отправьте число больше {settings.MIN_AGE}")

@router.message(ProfileForm.profile_url)
async def process_profile_url(message: Message, state: FSMContext):
    """Обработка введенной ссылки на профиль"""
    if not message.text:
        await show_validation_error(message, state, "Отправьте ссылку на профиль или нажмите 'Пропустить'")
        return

    data = await state.get_data()
    game = data.get('game', 'dota')
    
    profile_url = message.text.strip()
    is_valid, error_msg = validate_profile_input('profile_url', profile_url, game)

    if not is_valid:
        await show_validation_error(message, state, error_msg)
        return

    await state.update_data(profile_url=profile_url)
    
    data = await state.get_data()
    has_next_data = bool(data.get('region'))
    
    await show_profile_step(message, state, ProfileStep.REGION, show_current=has_next_data)

@router.message(ProfileForm.profile_url, ~F.text)
async def wrong_profile_url_format(message: Message, state: FSMContext):
    """Обработка неправильного формата ссылки профиля"""
    await show_validation_error(message, state, "Отправьте ссылку на профиль или используйте кнопки")

@router.message(ProfileForm.additional_info)
async def process_additional_info(message: Message, state: FSMContext):
    """Обработка введенной дополнительной информации"""
    if not message.text:
        await show_validation_error(message, state, "Отправьте текстовое сообщение с описанием или используйте кнопки")
        return

    info = message.text.strip()
    is_valid, error_msg = validate_profile_input('info', info)

    if not is_valid:
        await show_validation_error(message, state, error_msg)
        return

    await state.update_data(additional_info=info)
    
    data = await state.get_data()
    has_next_data = bool(data.get('photo_id'))
    
    await show_profile_step(message, state, ProfileStep.PHOTO, show_current=has_next_data)

@router.message(ProfileForm.additional_info, ~F.text)
async def wrong_info_format(message: Message, state: FSMContext):
    """Обработка неправильного формата дополнительной информации"""
    await show_validation_error(message, state, "Отправьте текстовое сообщение с описанием или нажмите 'Пропустить'")

@router.message(ProfileForm.photo, F.photo)
async def process_photo(message: Message, state: FSMContext, db):
    """Обработка загруженного фото и сохранение профиля"""
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    
    try:
        await message.delete()
    except Exception:
        pass
    
    data = await state.get_data()
    user_id = message.from_user.id
    
    await save_profile_unified(
        user_id=user_id,
        data=data,
        photo_id=photo_id,
        message=message,
        state=state,
        db=db
    )

@router.message(ProfileForm.photo)
async def wrong_photo_format(message: Message, state: FSMContext):
    """Обработка неправильного формата при загрузке фото"""
    await show_validation_error(message, state, "Отправьте фотографию или нажмите 'Пропустить'")

@router.callback_query(F.data == "rating_select_any", ProfileForm.rating)
async def select_any_rating(callback: CallbackQuery, state: FSMContext):
    """Выбор опции 'Любой рейтинг'"""
    data = await state.get_data()
    game = data['game']
    current_rating = data.get('rating')
    
    if current_rating == "any":
        await callback.answer("Уже выбрано 'Не указан'")
        return
    
    await state.update_data(rating="any")
    
    keyboard = kb.ratings(game, selected_rating="any", with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры рейтинга: {e}")
    
    await callback.answer()

@router.callback_query(F.data == "rating_remove_any", ProfileForm.rating)
async def remove_any_rating(callback: CallbackQuery, state: FSMContext):
    """Сброс выбора 'Любой рейтинг'"""
    data = await state.get_data()
    game = data['game']
    current_rating = data.get('rating')
    
    if current_rating != "any":
        await callback.answer("'Не указан' не выбран")
        return
    
    if 'rating' in data:
        del data['rating']
        await state.set_data(data)
    
    keyboard = kb.ratings(game, selected_rating=None, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры рейтинга: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("rating_select_"), ProfileForm.rating)
async def select_rating(callback: CallbackQuery, state: FSMContext):
    """Выбор конкретного рейтинга"""
    rating = callback.data.split("_", 2)[2]
    data = await state.get_data()
    game = data['game']
    current_rating = data.get('rating')
    
    if current_rating == rating:
        await callback.answer("Этот рейтинг уже выбран")
        return
    
    await state.update_data(rating=rating)
    
    keyboard = kb.ratings(game, selected_rating=rating, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры рейтинга: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("rating_remove_"), ProfileForm.rating)
async def remove_rating(callback: CallbackQuery, state: FSMContext):
    """Сброс выбора конкретного рейтинга"""
    rating = callback.data.split("_", 2)[2]
    data = await state.get_data()
    game = data['game']
    current_rating = data.get('rating')
    
    if current_rating != rating:
        await callback.answer("Этот рейтинг не выбран")
        return
    
    if 'rating' in data:
        del data['rating']
        await state.set_data(data)
    
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
    
    has_next_data = data.get('profile_url') is not None
    
    await show_profile_step(callback, state, ProfileStep.PROFILE_URL, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "rating_need", ProfileForm.rating)
async def rating_need(callback: CallbackQuery):
    """Напоминание о необходимости выбора рейтинга"""
    await callback.answer("Выберите рейтинг", show_alert=True)

@router.callback_query(F.data == "region_select_any", ProfileForm.region)
async def select_any_region(callback: CallbackQuery, state: FSMContext):
    """Выбор опции 'Любой регион'"""
    data = await state.get_data()
    current_region = data.get('region')
    
    if current_region == "any":
        await callback.answer("Уже выбрано 'Не указан'")
        return
    
    await state.update_data(region="any")
    
    keyboard = kb.regions(selected_region="any", with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры региона: {e}")
    
    await callback.answer()

@router.callback_query(F.data == "region_remove_any", ProfileForm.region)
async def remove_any_region(callback: CallbackQuery, state: FSMContext):
    """Сброс выбора 'Любой регион'"""
    data = await state.get_data()
    current_region = data.get('region')
    
    if current_region != "any":
        await callback.answer("'Не указан' не выбран")
        return
    
    if 'region' in data:
        del data['region']
        await state.set_data(data)
    
    keyboard = kb.regions(selected_region=None, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры региона: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("region_select_"), ProfileForm.region)
async def select_region(callback: CallbackQuery, state: FSMContext):
    """Выбор конкретного региона"""
    region = callback.data.split("_", 2)[2]
    data = await state.get_data()
    current_region = data.get('region')
    
    if current_region == region:
        await callback.answer("Этот регион уже выбран")
        return
    
    await state.update_data(region=region)
    
    keyboard = kb.regions(selected_region=region, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры региона: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("region_remove_"), ProfileForm.region)
async def remove_region(callback: CallbackQuery, state: FSMContext):
    """Сброс выбора конкретного региона"""
    region = callback.data.split("_", 2)[2]
    data = await state.get_data()
    current_region = data.get('region')
    
    if current_region != region:
        await callback.answer("Этот регион не выбран")
        return
    
    if 'region' in data:
        del data['region']
        await state.set_data(data)
    
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
    
    has_next_data = bool(data.get('positions_selected'))
    
    await show_profile_step(callback, state, ProfileStep.POSITIONS, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "region_need", ProfileForm.region)
async def region_need(callback: CallbackQuery):
    """Напоминание о необходимости выбора региона"""
    await callback.answer("Выберите регион", show_alert=True)

@router.callback_query(F.data == "pos_add_any", ProfileForm.positions)
async def add_any_position(callback: CallbackQuery, state: FSMContext):
    """Добавление опции 'Любая позиция'"""
    data = await state.get_data()
    game = data['game']
    
    await state.update_data(positions_selected=["any"])
    
    keyboard = kb.positions(game, ["any"], with_navigation=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "pos_remove_any", ProfileForm.positions)
async def remove_any_position(callback: CallbackQuery, state: FSMContext):
    """Удаление опции 'Любая позиция'"""
    data = await state.get_data()
    game = data['game']
    
    selected = data.get('positions_selected', [])
    if "any" in selected:
        selected.remove("any")
    
    await state.update_data(positions_selected=selected)
    
    keyboard = kb.positions(game, selected, with_navigation=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("pos_add_"), ProfileForm.positions)
async def add_position(callback: CallbackQuery, state: FSMContext):
    """Добавление конкретной позиции"""
    position = callback.data.split("_", 2)[2]
    data = await state.get_data()
    selected = data.get('positions_selected', [])
    game = data['game']
    
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

    keyboard = kb.positions(game, selected, with_navigation=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка обновления клавиатуры позиций: {e}")
    
    await callback.answer()

@router.callback_query(F.data.startswith("pos_remove_"), ProfileForm.positions)
async def remove_position(callback: CallbackQuery, state: FSMContext):
    """Удаление конкретной позиции"""
    position = callback.data.split("_", 2)[2]
    data = await state.get_data()
    selected = data.get('positions_selected', [])
    game = data['game']

    if position not in selected:
        await callback.answer("Эта позиция не выбрана")
        return

    selected.remove(position)
    await state.update_data(positions_selected=selected)

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
    
    has_next_data = bool(data.get('goals_selected'))
    
    await show_profile_step(callback, state, ProfileStep.GOALS, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "pos_need", ProfileForm.positions)
async def positions_need(callback: CallbackQuery):
    """Напоминание о необходимости выбора позиции"""
    await callback.answer("Выберите хотя бы одну позицию", show_alert=True)

@router.callback_query(F.data == "goals_add_any", ProfileForm.goals)
async def add_any_goal(callback: CallbackQuery, state: FSMContext):
    """Добавление опции 'Любая цель'"""
    await state.update_data(goals_selected=["any"])
    
    keyboard = kb.goals(["any"], with_navigation=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "goals_remove_any", ProfileForm.goals)
async def remove_any_goal(callback: CallbackQuery, state: FSMContext):
    """Удаление опции 'Любая цель'"""
    data = await state.get_data()
    selected = data.get('goals_selected', [])
    if "any" in selected:
        selected.remove("any")
    
    await state.update_data(goals_selected=selected)
    
    keyboard = kb.goals(selected, with_navigation=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("goals_add_"), ProfileForm.goals)
async def add_goal(callback: CallbackQuery, state: FSMContext):
    """Добавление конкретной цели"""
    goal = callback.data.split("_", 2)[2]
    data = await state.get_data()
    selected = data.get('goals_selected', [])
    
    if goal in selected:
        await callback.answer("Эта цель уже выбрана")
        return

    if goal == "any":
        selected = ["any"]
    else:
        if "any" in selected:
            selected.remove("any")
        selected.append(goal)
    
    await state.update_data(goals_selected=selected)

    keyboard = kb.goals(selected, with_navigation=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("goals_remove_"), ProfileForm.goals)
async def remove_goal(callback: CallbackQuery, state: FSMContext):
    """Удаление конкретной цели"""
    goal = callback.data.split("_", 2)[2]
    data = await state.get_data()
    selected = data.get('goals_selected', [])

    if goal not in selected:
        await callback.answer("Эта цель не выбрана")
        return

    selected.remove(goal)
    await state.update_data(goals_selected=selected)

    keyboard = kb.goals(selected, with_navigation=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "goals_done", ProfileForm.goals)
async def goals_done(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора целей"""
    data = await state.get_data()
    selected = data.get('goals_selected', [])

    if not selected:
        await callback.answer("Выберите хотя бы одну цель", show_alert=True)
        return

    await state.update_data(goals=selected)
    
    has_next_data = 'additional_info' in data
    
    await show_profile_step(callback, state, ProfileStep.INFO, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "goals_need", ProfileForm.goals)
async def goals_need(callback: CallbackQuery):
    """Напоминание о необходимости выбора цели"""
    await callback.answer("Выберите хотя бы одну цель", show_alert=True)

@router.callback_query(F.data == "skip_profile_url", ProfileForm.profile_url)
async def skip_profile_url(callback: CallbackQuery, state: FSMContext):
    """Пропуск ввода ссылки на профиль"""
    await state.update_data(profile_url="")
    
    data = await state.get_data()
    has_next_data = bool(data.get('region'))
    
    await show_profile_step(callback, state, ProfileStep.REGION, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "skip_info", ProfileForm.additional_info)
async def skip_info(callback: CallbackQuery, state: FSMContext):
    """Пропуск ввода дополнительной информации"""
    await state.update_data(additional_info="")
    
    data = await state.get_data()
    has_next_data = bool(data.get('photo_id'))
    
    await show_profile_step(callback, state, ProfileStep.PHOTO, show_current=has_next_data)
    await callback.answer()

@router.callback_query(F.data == "skip_photo", ProfileForm.photo)
async def skip_photo(callback: CallbackQuery, state: FSMContext, db):
    """Пропуск загрузки фото и сохранение профиля"""
    data = await state.get_data()
    user_id = data.get('user_id', callback.from_user.id)
    
    await save_profile_unified(
        user_id=user_id,
        data=data,
        photo_id=None,
        callback=callback,
        state=state,
        db=db
    )
    
    await callback.answer()

@router.callback_query(F.data == "cancel")
async def confirm_cancel_profile(callback: CallbackQuery, state: FSMContext):
    """Подтверждение отмены создания профиля"""
    data = await state.get_data()
    game_name = settings.GAMES.get(data.get('game', 'dota'), 'игры')
    
    text = (f"Отменить создание анкеты?\n\n"
            f"Вся введенная информация для {game_name} будет потеряна\n\n"
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
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                else:
                    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML', disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Ошибка отображения профиля при отмене пересоздания: {e}")
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML', disable_web_page_preview=True)
            
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
    """Продолжить создание профиля после подтверждения"""
    data = await state.get_data()
    current_step = data.get('current_step', ProfileStep.NAME.value)
    
    try:
        current_step_enum = ProfileStep(current_step)
        
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