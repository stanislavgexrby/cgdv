import logging
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import keyboards.keyboards as kb
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from handlers.notifications import update_user_activity
from handlers.basic import check_ban_and_profile, safe_edit_message

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

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def validate_profile_input(field: str, value, game: str = None) -> tuple[bool, str]:
    """Валидация ввода при создании профиля"""
    if field == 'name':
        if len(value) < 2 or len(value) > settings.MAX_NAME_LENGTH:
            return False, f"Имя должно быть от 2 до {settings.MAX_NAME_LENGTH} символов"
        if len(value.split()) < 2:
            return False, "Введите имя и фамилию"

    elif field == 'nickname':
        if len(value) < 2 or len(value) > settings.MAX_NICKNAME_LENGTH:
            return False, f"Никнейм должен быть от 2 до {settings.MAX_NICKNAME_LENGTH} символов"

    elif field == 'age':
        try:
            age = int(value)
            if age < settings.MIN_AGE:
                return False, f"Возраст должен быть больше {settings.MIN_AGE}"
        except ValueError:
            return False, "Введите число"

    elif field == 'info':
        if len(value) > settings.MAX_INFO_LENGTH:
            return False, f"Слишком длинный текст (максимум {settings.MAX_INFO_LENGTH} символов)"

    return True, ""

async def save_profile_universal(user_id: int, data: dict, photo_id: str = None, db = None) -> bool:
    """Универсальная функция сохранения профиля"""
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
        logger.info(f"Профиль создан для {user_id} в {data['game']}")

    return success

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
    game_name = settings.GAMES.get(game, game)

    await state.update_data(
        user_id=user_id,
        game=game,
        positions_selected=[]
    )
    await state.set_state(ProfileForm.name)
    await update_user_activity(user_id, 'profile_creation', db)
    text = f"Создание анкеты для {game_name}\n\n{texts.QUESTIONS['name']}"

    await safe_edit_message(callback, text, kb.cancel_profile_creation())
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
    await state.set_state(ProfileForm.nickname)
    await message.answer(texts.QUESTIONS["nickname"], reply_markup=kb.cancel_profile_creation(), parse_mode='HTML')

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
    await state.set_state(ProfileForm.age)
    await message.answer(texts.QUESTIONS["age"], reply_markup=kb.cancel_profile_creation(), parse_mode='HTML')

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
    await state.set_state(ProfileForm.rating)

    data = await state.get_data()
    game = data['game']

    await message.answer("Выберите рейтинг:", reply_markup=kb.ratings(game, with_cancel=True), parse_mode='HTML')

@router.message(ProfileForm.age, ~F.text)
async def wrong_age_format(message: Message):
    await message.answer(f"Отправьте число больше {settings.MIN_AGE}", parse_mode='HTML')

@router.message(ProfileForm.additional_info)
async def process_additional_info(message: Message, state: FSMContext):
    """Обработка дополнительной информации"""
    if not message.text:
        await message.answer("Отправьте текстовое сообщение с описанием или нажмите 'Пропустить'", parse_mode='HTML')
        return

    info = message.text.strip()
    is_valid, error_msg = validate_profile_input('info', info)

    if not is_valid:
        await message.answer(error_msg, parse_mode='HTML')
        return

    await state.update_data(additional_info=info)
    await state.set_state(ProfileForm.photo)
    await message.answer(texts.QUESTIONS["photo"], reply_markup=kb.skip_photo(), parse_mode='HTML')

@router.message(ProfileForm.additional_info, ~F.text)
async def wrong_info_format(message: Message):
    await message.answer("Отправьте текстовое сообщение с описанием или нажмите 'Пропустить'", parse_mode='HTML')

@router.message(ProfileForm.photo, F.photo)
async def process_photo(message: Message, state: FSMContext, db):
    photo_id = message.photo[-1].file_id
    await save_profile_flow(message, state, photo_id, db)

@router.message(ProfileForm.photo)
async def wrong_photo_format(message: Message):
    await message.answer("Отправьте фотографию или нажмите 'Пропустить'", reply_markup=kb.skip_photo(), parse_mode='HTML')

# ==================== ОБРАБОТЧИКИ CALLBACK ====================

@router.callback_query(F.data.startswith("rating_"), ProfileForm.rating)
async def process_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора рейтинга"""
    rating = callback.data.split("_")[1]
    await state.update_data(rating=rating)
    await state.set_state(ProfileForm.region)

    await safe_edit_message(callback, "Выберите регион:", kb.regions(with_cancel=True))
    await callback.answer()

@router.callback_query(F.data.startswith("region_"), ProfileForm.region)
async def process_region(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора региона"""
    region = callback.data.split("_")[1]
    await state.update_data(region=region)
    await state.set_state(ProfileForm.positions)

    data = await state.get_data()
    game = data['game']

    await safe_edit_message(callback, "Выберите позиции (можно несколько):", kb.positions(game, []))
    await callback.answer()

@router.callback_query(F.data.startswith("pos_add_"), ProfileForm.positions)
async def add_position(callback: CallbackQuery, state: FSMContext):
    """Добавление позиции"""
    position = callback.data.split("_")[2]
    data = await state.get_data()
    selected = data.get('positions_selected', [])
    game = data['game']

    if position not in selected:
        selected.append(position)
        await state.update_data(positions_selected=selected)

    await callback.message.edit_reply_markup(reply_markup=kb.positions(game, selected))
    await callback.answer()

@router.callback_query(F.data.startswith("pos_remove_"), ProfileForm.positions)
async def remove_position(callback: CallbackQuery, state: FSMContext):
    """Удаление позиции"""
    position = callback.data.split("_")[2]
    data = await state.get_data()
    selected = data.get('positions_selected', [])
    game = data['game']

    if position in selected:
        selected.remove(position)
        await state.update_data(positions_selected=selected)

    await callback.message.edit_reply_markup(reply_markup=kb.positions(game, selected))
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
    await state.set_state(ProfileForm.additional_info)

    await safe_edit_message(callback, "Расскажите о себе:", kb.skip_info())
    await callback.answer()

@router.callback_query(F.data == "pos_any", ProfileForm.positions)
async def process_any_position(callback: CallbackQuery, state: FSMContext):
    """Выбор любой позиции"""
    await state.update_data(positions=["any"])
    await state.set_state(ProfileForm.additional_info)

    await safe_edit_message(callback, "Расскажите о себе:", kb.skip_info())
    await callback.answer()

@router.callback_query(F.data == "pos_need", ProfileForm.positions)
async def positions_need(callback: CallbackQuery):
    await callback.answer("Выберите хотя бы одну позицию", show_alert=True)

@router.callback_query(F.data == "skip_info", ProfileForm.additional_info)
async def skip_info(callback: CallbackQuery, state: FSMContext):
    """Пропуск дополнительной информации"""
    await state.update_data(additional_info="")
    await state.set_state(ProfileForm.photo)

    await safe_edit_message(callback, texts.QUESTIONS["photo"], kb.skip_photo())
    await callback.answer()

@router.callback_query(F.data == "skip_photo", ProfileForm.photo)
async def skip_photo(callback: CallbackQuery, state: FSMContext, db):
    await save_profile_flow_callback(callback, state, None, db)

@router.callback_query(F.data == "cancel")
async def cancel_profile(callback: CallbackQuery, state: FSMContext):
    """Отмена создания профиля"""
    await state.clear()
    await safe_edit_message(callback, "Создание анкеты отменено", kb.back())
    await callback.answer()

# ==================== СОХРАНЕНИЕ ПРОФИЛЯ ====================

async def save_profile_flow(message: Message, state: FSMContext, photo_id: str | None, db):
    """Финал создания анкеты: сохранение и показ результата."""
    user_id = message.from_user.id
    data = await state.get_data()

    payload = {
        'game': data.get('game'),
        'name': data.get('name', '').strip(),
        'nickname': data.get('nickname', '').strip(),
        'age': data.get('age'),
        'rating': data.get('rating'),
        'region': data.get('region', 'eeu'),
        'positions': data.get('positions', []) or data.get('positions_selected', []),
        'additional_info': data.get('additional_info', '').strip(),
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
        text = f"Анкета для {game_name} создана!\n\n" + texts.format_profile(profile, show_contact=True)

        if profile.get('photo_id'):
            await message.answer_photo(photo=profile['photo_id'], caption=text, reply_markup=kb.back(), parse_mode='HTML')
        else:
            await message.answer(text, reply_markup=kb.back(), parse_mode='HTML')
    else:
        text = f"Анкета для {game_name} создана!"
        await message.answer(text, reply_markup=kb.back(), parse_mode='HTML')

async def save_profile_flow_callback(callback: CallbackQuery, state: FSMContext, photo_id: str, db):
    """Сохранение профиля через callback"""
    data = await state.get_data()
    user_id = data.get('user_id', callback.from_user.id)

    success = await save_profile_universal(
        user_id=user_id,
        data=data,
        photo_id=photo_id,
        db=db
    )
    await state.clear()

    if success:
        game_name = settings.GAMES.get(data['game'], data['game'])
        text = f"Анкета для {game_name} создана! Теперь можете искать сокомандников."
        await safe_edit_message(callback, text, kb.back())
    else:
        await safe_edit_message(callback, "Ошибка сохранения", kb.back())

    await callback.answer()