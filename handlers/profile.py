# handlers/profile.py
"""
Создание и редактирование профилей
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()
db = Database(settings.DATABASE_PATH)

# FSM состояния
class ProfileForm(StatesGroup):
    name = State()
    nickname = State()
    age = State()
    rating = State()
    positions = State()
    additional_info = State()
    photo = State()

@router.callback_query(F.data == "create_profile")
async def start_create_profile(callback: CallbackQuery, state: FSMContext):
    """Начать создание профиля"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    # Сохраняем данные
    await state.update_data(
        user_id=user_id,
        game=user['current_game'],
        positions_selected=[]
    )
    
    await state.set_state(ProfileForm.name)
    await callback.message.edit_text(texts.QUESTIONS["name"])
    await callback.answer()

@router.message(ProfileForm.name)
async def process_name(message: Message, state: FSMContext):
    """Обработка имени"""
    name = message.text.strip()
    
    # Простая валидация
    if len(name) < 2 or len(name) > settings.MAX_NAME_LENGTH:
        await message.answer(f"❌ Имя должно быть от 2 до {settings.MAX_NAME_LENGTH} символов")
        return
    
    if len(name.split()) < 2:
        await message.answer("❌ Введите имя и фамилию")
        return
    
    await state.update_data(name=name)
    await state.set_state(ProfileForm.nickname)
    await message.answer(texts.QUESTIONS["nickname"])

@router.message(ProfileForm.nickname)
async def process_nickname(message: Message, state: FSMContext):
    """Обработка никнейма"""
    nickname = message.text.strip()
    
    if len(nickname) < 2 or len(nickname) > settings.MAX_NICKNAME_LENGTH:
        await message.answer(f"❌ Никнейм должен быть от 2 до {settings.MAX_NICKNAME_LENGTH} символов")
        return
    
    await state.update_data(nickname=nickname)
    await state.set_state(ProfileForm.age)
    await message.answer(texts.QUESTIONS["age"])

@router.message(ProfileForm.age)
async def process_age(message: Message, state: FSMContext):
    """Обработка возраста"""
    try:
        age = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return
    
    if age < settings.MIN_AGE or age > settings.MAX_AGE:
        await message.answer(f"❌ Возраст должен быть от {settings.MIN_AGE} до {settings.MAX_AGE}")
        return
    
    await state.update_data(age=age)
    await state.set_state(ProfileForm.rating)
    
    # Показываем рейтинги
    data = await state.get_data()
    game = data['game']
    
    rating_text = "🏆 Выберите рейтинг:"
    await message.answer(rating_text, reply_markup=kb.ratings(game))

@router.callback_query(F.data.startswith("rating_"), ProfileForm.rating)
async def process_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка рейтинга"""
    rating = callback.data.split("_")[1]
    
    await state.update_data(rating=rating)
    await state.set_state(ProfileForm.positions)
    
    # Показываем позиции
    data = await state.get_data()
    game = data['game']
    
    position_text = "⚔️ Выберите позиции (можно несколько):"
    await callback.message.edit_text(position_text, reply_markup=kb.positions(game, []))
    await callback.answer()

@router.callback_query(F.data.startswith("pos_add_"), ProfileForm.positions)
async def add_position(callback: CallbackQuery, state: FSMContext):
    """Добавить позицию"""
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
    """Удалить позицию"""
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
        await callback.answer("❌ Выберите хотя бы одну позицию", show_alert=True)
        return
    
    await state.update_data(positions=selected)
    await state.set_state(ProfileForm.additional_info)
    
    await callback.message.edit_text(texts.QUESTIONS["info"])
    await callback.answer()

@router.callback_query(F.data == "pos_need", ProfileForm.positions)
async def positions_need(callback: CallbackQuery):
    """Напоминание о выборе позиции"""
    await callback.answer("⚠️ Выберите хотя бы одну позицию", show_alert=True)

@router.message(ProfileForm.additional_info)
async def process_additional_info(message: Message, state: FSMContext):
    """Обработка дополнительной информации"""
    info = message.text.strip()
    
    # Пропускаем если ввели "-"
    if info == "-":
        info = ""
    
    if len(info) > settings.MAX_INFO_LENGTH:
        await message.answer(f"❌ Слишком длинный текст (максимум {settings.MAX_INFO_LENGTH} символов)")
        return
    
    await state.update_data(additional_info=info)
    await state.set_state(ProfileForm.photo)
    
    await message.answer(texts.QUESTIONS["photo"], reply_markup=kb.skip_photo())

@router.message(ProfileForm.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка фото"""
    photo_id = message.photo[-1].file_id
    await save_profile(message, state, photo_id)

@router.callback_query(F.data == "skip_photo", ProfileForm.photo)
async def skip_photo(callback: CallbackQuery, state: FSMContext):
    """Пропустить фото"""
    await save_profile_callback(callback, state, None)

@router.message(ProfileForm.photo)
async def wrong_photo_format(message: Message, state: FSMContext):
    """Неправильный формат фото"""
    await message.answer("❌ Отправьте фотографию или нажмите 'Пропустить'", 
                        reply_markup=kb.skip_photo())

async def save_profile(message: Message, state: FSMContext, photo_id: str):
    """Сохранение профиля"""
    data = await state.get_data()
    
    success = db.update_user_profile(
        telegram_id=data['user_id'],
        name=data['name'],
        nickname=data['nickname'],
        age=data['age'],
        rating=data['rating'],
        positions=data['positions'],
        additional_info=data['additional_info'],
        photo_id=photo_id
    )
    
    await state.clear()
    
    if success:
        await message.answer(texts.PROFILE_CREATED, reply_markup=kb.back())
        logger.info(f"Профиль создан для {data['user_id']}")
    else:
        await message.answer("❌ Ошибка сохранения", reply_markup=kb.back())

async def save_profile_callback(callback: CallbackQuery, state: FSMContext, photo_id: str):
    """Сохранение профиля из callback"""
    data = await state.get_data()
    
    success = db.update_user_profile(
        telegram_id=data['user_id'],
        name=data['name'],
        nickname=data['nickname'],
        age=data['age'],
        rating=data['rating'],
        positions=data['positions'],
        additional_info=data['additional_info'],
        photo_id=photo_id
    )
    
    await state.clear()
    
    if success:
        await callback.message.edit_text(texts.PROFILE_CREATED, reply_markup=kb.back())
        logger.info(f"Профиль создан для {data['user_id']}")
    else:
        await callback.message.edit_text("❌ Ошибка сохранения", reply_markup=kb.back())
    
    await callback.answer()

@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery):
    """Редактирование профиля (упрощенное)"""
    await callback.message.edit_text(
        "✏️ Редактирование профиля\n\n" +
        "Пока доступно только полное пересоздание анкеты.\n" +
        "Хотите создать новую анкету?",
        reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="📝 Создать заново", callback_data="create_profile")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "delete_profile")
async def confirm_delete_profile(callback: CallbackQuery):
    """Подтверждение удаления"""
    text = ("🗑️ Удаление анкеты\n\n" +
           "Вы уверены? Это действие нельзя отменить.\n" +
           "Все лайки и матчи будут удалены.")
    
    await callback.message.edit_text(text, reply_markup=kb.confirm_delete())
    await callback.answer()

@router.callback_query(F.data == "confirm_delete")
async def delete_profile(callback: CallbackQuery):
    """Удаление профиля"""
    user_id = callback.from_user.id
    
    success = db.delete_profile(user_id)
    
    if success:
        await callback.message.edit_text(texts.PROFILE_DELETED, reply_markup=kb.back())
        logger.info(f"Профиль удален для {user_id}")
    else:
        await callback.message.edit_text("❌ Ошибка удаления", reply_markup=kb.back())
    
    await callback.answer()

# Отмена в любом состоянии
@router.callback_query(F.data == "cancel")
async def cancel_profile(callback: CallbackQuery, state: FSMContext):
    """Отмена создания профиля"""
    await state.clear()
    await callback.message.edit_text("❌ Создание анкеты отменено", reply_markup=kb.back())
    await callback.answer()