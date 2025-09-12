import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

from handlers.basic import safe_edit_message

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
    
    # Проверка на бан
    if db.is_user_banned(user_id):
        ban_info = db.get_user_ban(user_id)
        if ban_info:
            await callback.answer(f"🚫 Вы заблокированы до {ban_info['expires_at'][:16]}", show_alert=True)
        else:
            await callback.answer("🚫 Вы заблокированы", show_alert=True)
        return
        
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
    current_info = f"📝 Текущая анкета в {game_name}:\n\n"
    current_info += texts.format_profile(profile, show_contact=True)
    current_info += "\n\nЧто хотите изменить?"

    keyboard = kb.edit_profile_menu()

    try:
        # Если есть фото, показываем с фото
        if profile.get('photo_id'):
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=current_info,
                reply_markup=keyboard
            )
        else:
            # Если фото нет, показываем текстом
            await callback.message.edit_text(current_info, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка отображения профиля для редактирования: {e}")
        # Fallback на текстовое сообщение
        try:
            await callback.message.edit_text(current_info, reply_markup=keyboard)
        except:
            await callback.message.delete()
            await callback.message.answer(current_info, reply_markup=keyboard)

    await callback.answer()

async def safe_edit_or_send(message, text: str, reply_markup=None):
    """Безопасное редактирование или отправка нового сообщения"""
    try:
        if message.photo:
            # Если сообщение с фото, удаляем его и отправляем новое
            await message.delete()
            await message.answer(text, reply_markup=reply_markup)
        else:
            # Если обычное текстовое сообщение, редактируем
            await message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        try:
            await message.delete()
            await message.answer(text, reply_markup=reply_markup)
        except:
            pass

@router.callback_query(F.data == "edit_name")
async def edit_name(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_name)
    
    await safe_edit_or_send(
        callback.message,
        "👤 Введите новое имя и фамилию:",
        kb.cancel_edit()
    )
    await callback.answer()

@router.callback_query(F.data == "edit_nickname")
async def edit_nickname(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_nickname)
    
    await safe_edit_or_send(
        callback.message,
        "🎮 Введите новый игровой никнейм:",
        kb.cancel_edit()
    )
    await callback.answer()

@router.callback_query(F.data == "edit_age")
async def edit_age(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_age)
    
    await safe_edit_or_send(
        callback.message,
        f"🎂 Введите новый возраст:",
        kb.cancel_edit()
    )
    await callback.answer()

@router.callback_query(F.data == "edit_rating")
async def edit_rating(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_rating)
    
    await safe_edit_or_send(
        callback.message,
        "🏆 Выберите новый рейтинг:",
        kb.ratings(user['current_game'])
    )
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
        positions_selected=current_positions.copy(),
        original_positions=current_positions.copy()
    )
    await state.set_state(EditProfileForm.edit_positions)
    
    await safe_edit_or_send(
        callback.message,
        "⚔️ Выберите новые позиции (можно несколько):",
        kb.positions(user['current_game'], current_positions)
    )
    await callback.answer()

@router.callback_query(F.data == "edit_info")
async def edit_info(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_info)
    
    await safe_edit_or_send(
        callback.message,
        "📝 Введите новое описание или выберите действие:",
        kb.edit_info_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "edit_photo")
async def edit_photo(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_photo)
    
    await safe_edit_or_send(
        callback.message,
        "📸 Отправьте новое фото или нажмите 'Удалить фото':",
        kb.edit_photo_menu()
    )
    await callback.answer()

# Обработчики сообщений для редактирования

@router.message(EditProfileForm.edit_name)
async def process_edit_name(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Отправьте текстовое сообщение с именем и фамилией")
        return
        
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
            await message.answer("✅ Имя обновлено!", reply_markup=kb.back_to_editing())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back_to_editing())

@router.message(EditProfileForm.edit_name, ~F.text)
async def wrong_edit_name_format(message: Message, state: FSMContext):
    await message.answer("❌ Отправьте текстовое сообщение с именем и фамилией")

@router.message(EditProfileForm.edit_nickname)
async def process_edit_nickname(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Отправьте текстовое сообщение с игровым никнеймом")
        return
        
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
            await message.answer("✅ Никнейм обновлен!", reply_markup=kb.back_to_editing())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back_to_editing())

@router.message(EditProfileForm.edit_nickname, ~F.text)
async def wrong_edit_nickname_format(message: Message, state: FSMContext):
    await message.answer("❌ Отправьте текстовое сообщение с игровым никнеймом")

@router.message(EditProfileForm.edit_age)
async def process_edit_age(message: Message, state: FSMContext):
    if not message.text:
        await message.answer(f"❌ Отправьте число большее {settings.MIN_AGE}:")
        return
        
    try:
        age = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return

    if age < settings.MIN_AGE:
        await message.answer(f"❌ Возраст должен быть большее {settings.MIN_AGE}:")
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
            await message.answer("✅ Возраст обновлен!", reply_markup=kb.back_to_editing())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back_to_editing())

@router.message(EditProfileForm.edit_age, ~F.text)
async def wrong_edit_age_format(message: Message, state: FSMContext):
    await message.answer(f"❌ Отправьте число большее {settings.MIN_AGE}:")

@router.message(EditProfileForm.edit_info)
async def process_edit_info(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Отправьте текстовое сообщение с описанием")
        return
        
    info = message.text.strip()

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
            await message.answer("✅ Описание обновлено!", reply_markup=kb.back_to_editing())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back_to_editing())

@router.message(EditProfileForm.edit_info, ~F.text)
async def wrong_edit_info_format(message: Message, state: FSMContext):
    await message.answer("❌ Отправьте текстовое сообщение с описанием")

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
            await message.answer("✅ Фото обновлено!", reply_markup=kb.back_to_editing())
        else:
            await message.answer("❌ Ошибка обновления", reply_markup=kb.back_to_editing())

@router.message(EditProfileForm.edit_photo)
async def wrong_edit_photo_format(message: Message, state: FSMContext):
    await message.answer(
        "❌ Отправьте фотографию или используйте кнопки",
        reply_markup=kb.edit_photo_menu()
    )

# Обработчики callback для редактирования

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
            await safe_edit_or_send(callback.message, "✅ Рейтинг обновлен!", kb.back_to_editing())
        else:
            await safe_edit_or_send(callback.message, "❌ Ошибка обновления", kb.back_to_editing())
    
    await callback.answer()

# Обработчики позиций

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
    original = data.get('original_positions', [])

    if not selected:
        await callback.answer("❌ Выберите хотя бы одну позицию", show_alert=True)
        return

    # Проверяем, изменились ли позиции
    if set(selected) == set(original):
        await callback.answer("✅ Позиции не изменились")
        await state.clear()
        await safe_edit_or_send(callback.message, "ℹ️ Позиции остались прежними", kb.back_to_editing())
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
            await safe_edit_or_send(callback.message, "✅ Позиции обновлены!", kb.back_to_editing())
        else:
            await safe_edit_or_send(callback.message, "❌ Ошибка обновления", kb.back_to_editing())
    
    await callback.answer()

@router.callback_query(F.data == "pos_need", EditProfileForm.edit_positions)
async def edit_positions_need(callback: CallbackQuery):
    await callback.answer("⚠️ Выберите хотя бы одну позицию", show_alert=True)

# Обработчики удаления

@router.callback_query(F.data == "delete_info", EditProfileForm.edit_info)
async def delete_info(callback: CallbackQuery, state: FSMContext):
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
            additional_info="",  # Удаляем описание
            photo_id=profile.get('photo_id')
        )
        
        await state.clear()
        
        if success:
            await safe_edit_or_send(callback.message, "✅ Описание удалено!", kb.back_to_editing())
        else:
            await safe_edit_or_send(callback.message, "❌ Ошибка обновления", kb.back_to_editing())
    
    await callback.answer()

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
            await safe_edit_or_send(callback.message, "✅ Фото удалено!", kb.back_to_editing())
        else:
            await safe_edit_or_send(callback.message, "❌ Ошибка обновления", kb.back_to_editing())
    
    await callback.answer()

@router.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit_or_send(callback.message, "❌ Редактирование отменено", kb.back_to_editing())
    await callback.answer()

@router.callback_query(F.data == "delete_profile")
async def confirm_delete_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']
    game_name = settings.GAMES.get(game, game)

    text = (f"🗑️ Удаление анкеты в {game_name}\n\n" +
           "Вы уверены? Это действие нельзя отменить.\n" +
           f"Все лайки и матчи в {game_name} будут удалены.")

    try:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb.confirm_delete())
        else:
            await callback.message.edit_text(text, reply_markup=kb.confirm_delete())
    except Exception as e:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.confirm_delete())
        await callback.answer()

@router.callback_query(F.data == "confirm_delete")
async def delete_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']
    success = db.delete_profile(user_id, game)

    if success:
        game_name = settings.GAMES.get(game, game)
        
        text = f"✅ Анкета в {game_name} успешно удалена!\n\n"
        text += f"Все связанные данные (лайки и матчи) также удалены.\n\n"
        text += f"Вы можете создать новую анкету в любое время."
        
        buttons = [
            [kb.InlineKeyboardButton(text="📝 Создать новую анкету", callback_data="create_profile")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
        
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        logger.info(f"Профиль удален для {user_id} в {game}")
    else:
        text = "❌ Произошла ошибка при удалении анкеты.\n\nПопробуйте еще раз."
        await callback.message.edit_text(text, reply_markup=kb.back())

    await callback.answer()