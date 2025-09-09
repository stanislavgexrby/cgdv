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

class EditProfileForm(StatesGroup):
    edit_name = State()
    edit_nickname = State()
    edit_age = State()
    edit_rating = State()
    edit_positions = State()
    edit_info = State()
    edit_photo = State()

@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']
    profile = db.get_user_profile(user_id, game)

    if not profile:
        await callback.answer("❌ Анкета не найдена", show_alert=True)
        return

    game_name = settings.GAMES.get(game, game)

    # current_info = f"📝 Текущая анкета в {game_name}:\n\n"
    # current_info += f"👤 Имя: {profile['name']}\n"
    # current_info += f"🎮 Никнейм: {profile['nickname']}\n"
    # current_info += f"🎂 Возраст: {profile['age']} лет\n"

    # rating_name = settings.RATINGS[game].get(profile['rating'], profile['rating'])
    # current_info += f"🏆 Рейтинг: {rating_name}\n"

    # if profile['positions']:
    #     positions_text = []
    #     for pos in profile['positions']:
    #         if pos in settings.POSITIONS.get(game, {}):
    #             positions_text.append(settings.POSITIONS[game][pos])
    #         else:
    #             positions_text.append(pos)
    #     current_info += f"⚔️ Позиции: {', '.join(positions_text)}\n"

    # current_info += f"📝 О себе: {profile.get('additional_info') or 'не указано'}\n"
    # current_info += f"📸 Фото: {'загружено' if profile.get('photo_id') else 'не загружено'}\n"
    # current_info += "\nЧто хотите изменить?"
    current_info = f"📝 Текущая анкета в {game_name}:\n\n"
    current_info += texts.format_profile(profile, show_contact=True)
    current_info += "\nЧто хотите изменить?"

    buttons = [
        [kb.InlineKeyboardButton(text="👤 Изменить имя", callback_data="edit_name")],
        [kb.InlineKeyboardButton(text="🎮 Изменить никнейм", callback_data="edit_nickname")],
        [kb.InlineKeyboardButton(text="🎂 Изменить возраст", callback_data="edit_age")],
        [kb.InlineKeyboardButton(text="🏆 Изменить рейтинг", callback_data="edit_rating")],
        [kb.InlineKeyboardButton(text="⚔️ Изменить позиции", callback_data="edit_positions")],
        [kb.InlineKeyboardButton(text="📝 Изменить описание", callback_data="edit_info")],
        [kb.InlineKeyboardButton(text="📸 Изменить фото", callback_data="edit_photo")],
        [kb.InlineKeyboardButton(text="🔄 Создать заново", callback_data="create_profile")],
        [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ]

    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(current_info, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "edit_name")
async def edit_name(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_name)
    
    await callback.message.edit_text(
        "👤 Введите новое имя и фамилию:",
        reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
    )
    await callback.answer()

@router.message(EditProfileForm.edit_name)
async def process_edit_name(message: Message, state: FSMContext):
    name = message.text.strip()

    if len(name) < 2 or len(name) > settings.MAX_NAME_LENGTH:
        await message.answer(f"❌ Имя должно быть от 2 до {settings.MAX_NAME_LENGTH} символов")
        return

    if len(name.split()) < 2:
        await message.answer("❌ Введите имя и фамилию")
        return

    data = await state.get_data()
    profile = db.get_user_profile(data['user_id'], data['game'])
    
    if profile:
        success = db.update_user_profile(
            telegram_id=data['user_id'],
            game=data['game'],
            name=name,
            nickname=profile['nickname'],
            age=profile['age'],
            rating=profile['rating'],
            positions=profile['positions'],
            additional_info=profile['additional_info'],
            photo_id=profile.get('photo_id')
        )
        
        await state.clear()
        
        if success:
            await message.answer("✅ Имя обновлено!", reply_markup=kb.back())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back())

@router.message(EditProfileForm.edit_name, ~F.text)
async def wrong_edit_name_format(message: Message, state: FSMContext):
    await message.answer("❌ Отправьте текстовое сообщение с именем и фамилией")

@router.callback_query(F.data == "edit_nickname")
async def edit_nickname(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_nickname)
    
    await callback.message.edit_text(
        "🎮 Введите новый игровой никнейм:",
        reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
    )
    await callback.answer()

@router.message(EditProfileForm.edit_nickname)
async def process_edit_nickname(message: Message, state: FSMContext):
    nickname = message.text.strip()

    if len(nickname) < 2 or len(nickname) > settings.MAX_NICKNAME_LENGTH:
        await message.answer(f"❌ Никнейм должен быть от 2 до {settings.MAX_NICKNAME_LENGTH} символов")
        return

    data = await state.get_data()
    profile = db.get_user_profile(data['user_id'], data['game'])
    
    if profile:
        success = db.update_user_profile(
            telegram_id=data['user_id'],
            game=data['game'],
            name=profile['name'],
            nickname=nickname,
            age=profile['age'],
            rating=profile['rating'],
            positions=profile['positions'],
            additional_info=profile['additional_info'],
            photo_id=profile.get('photo_id')
        )
        
        await state.clear()
        
        if success:
            await message.answer("✅ Никнейм обновлен!", reply_markup=kb.back())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back())

@router.message(EditProfileForm.edit_nickname, ~F.text)
async def wrong_edit_nickname_format(message: Message, state: FSMContext):
    await message.answer("❌ Отправьте текстовое сообщение с игровым никнеймом")

@router.callback_query(F.data == "edit_age")
async def edit_age(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_age)
    
    await callback.message.edit_text(
        f"🎂 Введите новый возраст ({settings.MIN_AGE}-{settings.MAX_AGE}):",
        reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
    )
    await callback.answer()

@router.message(EditProfileForm.edit_age)
async def process_edit_age(message: Message, state: FSMContext):
    try:
        age = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return

    if age < settings.MIN_AGE or age > settings.MAX_AGE:
        await message.answer(f"❌ Возраст должен быть от {settings.MIN_AGE} до {settings.MAX_AGE}")
        return

    data = await state.get_data()
    profile = db.get_user_profile(data['user_id'], data['game'])
    
    if profile:
        success = db.update_user_profile(
            telegram_id=data['user_id'],
            game=data['game'],
            name=profile['name'],
            nickname=profile['nickname'],
            age=age,
            rating=profile['rating'],
            positions=profile['positions'],
            additional_info=profile['additional_info'],
            photo_id=profile.get('photo_id')
        )
        
        await state.clear()
        
        if success:
            await message.answer("✅ Возраст обновлен!", reply_markup=kb.back())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back())

@router.message(EditProfileForm.edit_age, ~F.text)
async def wrong_edit_age_format(message: Message, state: FSMContext):
    await message.answer(f"❌ Отправьте число от {settings.MIN_AGE} до {settings.MAX_AGE}")

@router.callback_query(F.data == "edit_rating")
async def edit_rating(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_rating)
    
    await callback.message.edit_text(
        "🏆 Выберите новый рейтинг:",
        reply_markup=kb.ratings(user['current_game'])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rating_"), EditProfileForm.edit_rating)
async def process_edit_rating(callback: CallbackQuery, state: FSMContext):
    rating = callback.data.split("_")[1]
    
    data = await state.get_data()
    profile = db.get_user_profile(data['user_id'], data['game'])
    
    if profile:
        success = db.update_user_profile(
            telegram_id=data['user_id'],
            game=data['game'],
            name=profile['name'],
            nickname=profile['nickname'],
            age=profile['age'],
            rating=rating,
            positions=profile['positions'],
            additional_info=profile['additional_info'],
            photo_id=profile.get('photo_id')
        )
        
        await state.clear()
        
        if success:
            await callback.message.edit_text("✅ Рейтинг обновлен!", reply_markup=kb.back())
        else:
            await callback.message.edit_text("❌ Ошибка обновления", reply_markup=kb.back())
    
    await callback.answer()

@router.callback_query(F.data == "edit_positions")
async def edit_positions(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    profile = db.get_user_profile(user_id, user['current_game'])
    current_positions = profile['positions'] if profile else []
    
    await state.update_data(
        user_id=user_id, 
        game=user['current_game'],
        positions_selected=current_positions.copy()
    )
    await state.set_state(EditProfileForm.edit_positions)
    
    await callback.message.edit_text(
        "⚔️ Выберите новые позиции (можно несколько):",
        reply_markup=kb.positions(user['current_game'], current_positions)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pos_add_"), EditProfileForm.edit_positions)
async def edit_add_position(callback: CallbackQuery, state: FSMContext):
    position = callback.data.split("_")[2]

    data = await state.get_data()
    selected = data.get('positions_selected', [])
    game = data['game']

    if position not in selected:
        selected.append(position)
        await state.update_data(positions_selected=selected)

    await callback.message.edit_reply_markup(reply_markup=kb.positions(game, selected))
    await callback.answer()

@router.callback_query(F.data.startswith("pos_remove_"), EditProfileForm.edit_positions)
async def edit_remove_position(callback: CallbackQuery, state: FSMContext):
    position = callback.data.split("_")[2]

    data = await state.get_data()
    selected = data.get('positions_selected', [])
    game = data['game']

    if position in selected:
        selected.remove(position)
        await state.update_data(positions_selected=selected)

    await callback.message.edit_reply_markup(reply_markup=kb.positions(game, selected))
    await callback.answer()

@router.callback_query(F.data == "pos_done", EditProfileForm.edit_positions)
async def edit_positions_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get('positions_selected', [])

    if not selected:
        await callback.answer("❌ Выберите хотя бы одну позицию", show_alert=True)
        return

    profile = db.get_user_profile(data['user_id'], data['game'])
    
    if profile:
        success = db.update_user_profile(
            telegram_id=data['user_id'],
            game=data['game'],
            name=profile['name'],
            nickname=profile['nickname'],
            age=profile['age'],
            rating=profile['rating'],
            positions=selected,
            additional_info=profile['additional_info'],
            photo_id=profile.get('photo_id')
        )
        
        await state.clear()
        
        if success:
            await callback.message.edit_text("✅ Позиции обновлены!", reply_markup=kb.back())
        else:
            await callback.message.edit_text("❌ Ошибка обновления", reply_markup=kb.back())
    
    await callback.answer()

@router.callback_query(F.data == "pos_need", EditProfileForm.edit_positions)
async def edit_positions_need(callback: CallbackQuery):
    await callback.answer("⚠️ Выберите хотя бы одну позицию", show_alert=True)

@router.callback_query(F.data == "edit_info")
async def edit_info(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_info)
    
    await callback.message.edit_text(
        "📝 Введите новое описание (или отправьте '-' чтобы удалить):",
        reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
    )
    await callback.answer()

@router.message(EditProfileForm.edit_info)
async def process_edit_info(message: Message, state: FSMContext):
    info = message.text.strip()

    if info == "-":
        info = ""

    if len(info) > settings.MAX_INFO_LENGTH:
        await message.answer(f"❌ Слишком длинный текст (максимум {settings.MAX_INFO_LENGTH} символов)")
        return

    data = await state.get_data()
    profile = db.get_user_profile(data['user_id'], data['game'])
    
    if profile:
        success = db.update_user_profile(
            telegram_id=data['user_id'],
            game=data['game'],
            name=profile['name'],
            nickname=profile['nickname'],
            age=profile['age'],
            rating=profile['rating'],
            positions=profile['positions'],
            additional_info=info,
            photo_id=profile.get('photo_id')
        )
        
        await state.clear()
        
        if success:
            await message.answer("✅ Описание обновлено!", reply_markup=kb.back())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back())

# Обработчик неправильного типа сообщения для редактирования описания
@router.message(EditProfileForm.edit_info, ~F.text)
async def wrong_edit_info_format(message: Message, state: FSMContext):
    await message.answer("❌ Отправьте текстовое сообщение с описанием или '-' чтобы удалить")

@router.callback_query(F.data == "edit_photo")
async def edit_photo(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_photo)
    
    await callback.message.edit_text(
        "📸 Отправьте новое фото или нажмите 'Удалить фото':",
        reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="🗑️ Удалить фото", callback_data="delete_photo")],
            [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
    )
    await callback.answer()

@router.message(EditProfileForm.edit_photo, F.photo)
async def process_edit_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    
    data = await state.get_data()
    profile = db.get_user_profile(data['user_id'], data['game'])
    
    if profile:
        success = db.update_user_profile(
            telegram_id=data['user_id'],
            game=data['game'],
            name=profile['name'],
            nickname=profile['nickname'],
            age=profile['age'],
            rating=profile['rating'],
            positions=profile['positions'],
            additional_info=profile['additional_info'],
            photo_id=photo_id
        )
        
        await state.clear()
        
        if success:
            await message.answer("✅ Фото обновлено!", reply_markup=kb.back())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back())

@router.callback_query(F.data == "delete_photo", EditProfileForm.edit_photo)
async def delete_photo(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    profile = db.get_user_profile(data['user_id'], data['game'])
    
    if profile:
        success = db.update_user_profile(
            telegram_id=data['user_id'],
            game=data['game'],
            name=profile['name'],
            nickname=profile['nickname'],
            age=profile['age'],
            rating=profile['rating'],
            positions=profile['positions'],
            additional_info=profile['additional_info'],
            photo_id=None
        )
        
        await state.clear()
        
        if success:
            await callback.message.edit_text("✅ Фото удалено!", reply_markup=kb.back())
        else:
            await callback.message.edit_text("❌ Ошибка обновления", reply_markup=kb.back())
    
    await callback.answer()

@router.message(EditProfileForm.edit_photo)
async def wrong_edit_photo_format(message: Message, state: FSMContext):
    await message.answer(
        "❌ Отправьте фотографию или используйте кнопки",
        reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="🗑️ Удалить фото", callback_data="delete_photo")],
            [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
    )

@router.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Редактирование отменено", reply_markup=kb.back())
    await callback.answer()