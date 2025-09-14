import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings
from handlers.basic import check_ban_and_profile, safe_edit_message

logger = logging.getLogger(__name__)
router = Router()

class EditProfileForm(StatesGroup):
    edit_name = State()
    edit_nickname = State()
    edit_age = State()
    edit_rating = State()
    edit_region = State()
    edit_positions = State()
    edit_info = State()
    edit_photo = State()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

# async def update_profile_field(callback: CallbackQuery, field: str, value, state: FSMContext = None, db=None):
#     """Универсальная функция обновления поля профиля"""
#     user_id = callback.from_user.id
#     user = await db.get_user(user_id)

#     if not user or not user.get('current_game'):
#         await callback.answer("❌ Ошибка", show_alert=True)
#         return False

#     game = user['current_game']
#     profile = await db.get_user_profile(user_id, game)

#     if not profile:
#         await callback.answer("❌ Анкета не найдена", show_alert=True)
#         return False

#     update_data = {
#         'telegram_id': user_id,
#         'game': game,
#         'name': profile['name'],
#         'nickname': profile['nickname'],
#         'age': profile['age'],
#         'rating': profile['rating'],
#         'region': profile.get('region', 'eeu'),
#         'positions': profile['positions'],
#         'additional_info': profile['additional_info'],
#         'photo_id': profile.get('photo_id')
#     }

#     update_data[field] = value

#     success = await db.update_user_profile(**update_data)

#     if state:
#         await state.clear()

#     if success:
#         field_names = {
#             'name': 'Имя',
#             'nickname': 'Никнейм', 
#             'age': 'Возраст',
#             'rating': 'Рейтинг',
#             'region': 'Регион',
#             'positions': 'Позиции',
#             'additional_info': 'Описание',
#             'photo_id': 'Фото'
#         }

#         message = f"✅ {field_names.get(field, 'Поле')} обновлено!"
#         if field == 'additional_info' and value == "":
#             message = "✅ Описание удалено!"
#         elif field == 'photo_id' and value is None:
#             message = "✅ Фото удалено!"

#         await safe_edit_message(callback, message, kb.back_to_editing())
#     else:
#         await safe_edit_message(callback, "❌ Ошибка обновления", kb.back_to_editing())

#     return success

async def update_profile_field(user_id: int, field: str, value, db) -> bool:
    """Обновить поле профиля в базе. Без UI-логики."""
    user = await db.get_user(user_id)
    if not user or not user.get('current_game'):
        return False

    game = user['current_game']
    profile = await db.get_user_profile(user_id, game)
    if not profile:
        return False

    update_data = {
        'telegram_id': user_id,
        'game': game,
        'name': profile['name'],
        'nickname': profile['nickname'],
        'age': profile['age'],
        'rating': profile['rating'],
        'region': profile.get('region', 'eeu'),
        'positions': profile['positions'],
        'additional_info': profile['additional_info'],
        'photo_id': profile.get('photo_id')
    }

    update_data[field] = value
    return await db.update_user_profile(**update_data)

def validate_input(field: str, value, game: str = None) -> tuple[bool, str]:
    """Валидация ввода пользователя"""
    if field == 'name':
        if len(value) < 2 or len(value) > settings.MAX_NAME_LENGTH:
            return False, f"❌ Имя должно быть от 2 до {settings.MAX_NAME_LENGTH} символов"
        if len(value.split()) < 2:
            return False, "❌ Введите имя и фамилию"

    elif field == 'nickname':
        if len(value) < 2 or len(value) > settings.MAX_NICKNAME_LENGTH:
            return False, f"❌ Никнейм должен быть от 2 до {settings.MAX_NICKNAME_LENGTH} символов"

    elif field == 'age':
        try:
            age = int(value)
            if age < settings.MIN_AGE:
                return False, f"❌ Возраст должен быть больше {settings.MIN_AGE}"
        except ValueError:
            return False, "❌ Введите число"

    elif field == 'info':
        if len(value) > settings.MAX_INFO_LENGTH:
            return False, f"❌ Слишком длинный текст (максимум {settings.MAX_INFO_LENGTH} символов)"

    return True, ""

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "edit_profile")
@check_ban_and_profile()
async def edit_profile(callback: CallbackQuery, db):
    """Показ меню редактирования профиля"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']
    profile = await db.get_user_profile(user_id, game)

    game_name = settings.GAMES.get(game, game)
    current_info = f"📝 Текущая анкета в {game_name}:\n\n"
    current_info += texts.format_profile(profile, show_contact=True)
    current_info += "\n\nЧто хотите изменить?"

    keyboard = kb.edit_profile_menu()

    try:
        if profile.get('photo_id'):
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=current_info,
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(current_info, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка отображения профиля для редактирования: {e}")
        try:
            await callback.message.edit_text(current_info, reply_markup=keyboard)
        except:
            await callback.message.delete()
            await callback.message.answer(current_info, reply_markup=keyboard)

    await callback.answer()

@router.callback_query(F.data == "recreate_profile")
@check_ban_and_profile(require_profile=False)
async def recreate_profile(callback: CallbackQuery, state: FSMContext, db):
    """Создание анкеты заново (переход к форме создания профиля)"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']

    if await db.has_profile(user_id, game):
        await db.delete_profile(user_id, game)
        logger.info(f"Профиль удален для пересоздания: {user_id} в {game}")

    game_name = settings.GAMES.get(game, game)

    await state.clear()
    await state.update_data(
        user_id=user_id,
        game=game,
        positions_selected=[]
    )

    from handlers.profile import ProfileForm
    await state.set_state(ProfileForm.name)

    text = f"📝 Создание новой анкеты для {game_name}\n\n{texts.QUESTIONS['name']}"

    await callback.message.delete()
    await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text=text,
        reply_markup=kb.cancel_profile_creation()
    )
    await callback.answer()

# ==================== ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ ПОЛЕЙ ====================

@router.callback_query(F.data == "edit_name")
@check_ban_and_profile()
async def edit_name(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_name)

    await safe_edit_message(callback, "👤 Введите новое имя и фамилию:", kb.cancel_edit())
    await callback.answer()

@router.callback_query(F.data == "edit_nickname")
@check_ban_and_profile()
async def edit_nickname(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_nickname)

    await safe_edit_message(callback, "🎮 Введите новый игровой никнейм:", kb.cancel_edit())
    await callback.answer()

@router.callback_query(F.data == "edit_age")
@check_ban_and_profile()
async def edit_age(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_age)

    await safe_edit_message(callback, "🎂 Введите новый возраст:", kb.cancel_edit())
    await callback.answer()

@router.callback_query(F.data == "edit_rating")
@check_ban_and_profile()
async def edit_rating(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_rating)
    await safe_edit_message(callback, "🏆 Выберите новый рейтинг:", kb.ratings(user['current_game']))
    await callback.answer()

@router.callback_query(F.data == "edit_region")
@check_ban_and_profile()
async def edit_region(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_region)
    await safe_edit_message(callback, "🌍 Выберите новый регион:", kb.regions())
    await callback.answer()

@router.callback_query(F.data == "edit_positions")
@check_ban_and_profile()
async def edit_positions(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    profile = await db.get_user_profile(user_id, user['current_game'])
    current_positions = profile['positions'] if profile else []
    await state.update_data(
        user_id=user_id,
        game=user['current_game'],
        positions_selected=current_positions.copy(),
        original_positions=current_positions.copy()
    )
    await state.set_state(EditProfileForm.edit_positions)
    await safe_edit_message(callback, "⚔️ Выберите новые позиции (можно несколько):", kb.positions(user['current_game'], current_positions))
    await callback.answer()

@router.callback_query(F.data == "edit_info")
@check_ban_and_profile()
async def edit_info(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_info)
    await safe_edit_message(callback, "📝 Введите новое описание или выберите действие:", kb.edit_info_menu())
    await callback.answer()

@router.callback_query(F.data == "edit_photo")
@check_ban_and_profile()
async def edit_photo(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    await state.update_data(user_id=user_id, game=user['current_game'])
    await state.set_state(EditProfileForm.edit_photo)

    await safe_edit_message(
        callback,
        "📸 Отправьте новое фото или нажмите 'Удалить фото':",
        kb.edit_photo_menu()
    )
    await callback.answer()

# ==================== ОБРАБОТЧИКИ СООБЩЕНИЙ ====================

@router.message(EditProfileForm.edit_name)
async def process_edit_name(message: Message, state: FSMContext, db):
    if not message.text:
        await message.answer("❌ Отправьте текстовое сообщение с именем и фамилией")
        return

    name = message.text.strip()
    is_valid, error_msg = validate_input('name', name)
    if not is_valid:
        await message.answer(error_msg)
        return

    success = await update_profile_field(message, 'name', name, state=state, db=db)
    if success:
        await state.clear()
        await message.answer("✅ Имя обновлено!", reply_markup=kb.back_to_editing())
    else:
        await message.answer("❌ Ошибка обновления", reply_markup=kb.back_to_editing())

@router.message(EditProfileForm.edit_nickname)
async def process_edit_nickname(message: Message, state: FSMContext, db):
    if not message.text:
        await message.answer("❌ Отправьте текстовое сообщение с игровым никнеймом")
        return

    nickname = message.text.strip()
    is_valid, error_msg = validate_input('nickname', nickname)
    if not is_valid:
        await message.answer(error_msg)
        return

    success = await update_profile_field(message, 'nickname', nickname, state=state, db=db)
    if success:
        await state.clear()
        await message.answer("✅ Никнейм обновлён!", reply_markup=kb.back_to_editing())
    else:
        await message.answer("❌ Ошибка обновления", reply_markup=kb.back_to_editing())

@router.message(EditProfileForm.edit_age)
async def process_edit_age(message: Message, state: FSMContext, db):
    if not message.text:
        await message.answer("❌ Отправьте число")
        return

    is_valid, error_msg = validate_input('age', message.text.strip())
    if not is_valid:
        await message.answer(error_msg)
        return

    age = int(message.text.strip())
    success = await update_profile_field(message, 'age', age, state=state, db=db)
    if success:
        await state.clear()
        await message.answer("✅ Возраст обновлён!", reply_markup=kb.back_to_editing())
    else:
        await message.answer("❌ Ошибка обновления", reply_markup=kb.back_to_editing())

@router.message(EditProfileForm.edit_info)
async def process_edit_info(message: Message, state: FSMContext, db):
    if not message.text:
        await message.answer("❌ Отправьте текст или используйте кнопки")
        return

    info = message.text.strip()
    is_valid, error_msg = validate_input('info', info)
    if not is_valid:
        await message.answer(error_msg)
        return

    success = await update_profile_field(message, 'additional_info', info, state=state, db=db)
    if success:
        await state.clear()
        await message.answer("✅ Описание обновлено!", reply_markup=kb.back_to_editing())
    else:
        await message.answer("❌ Ошибка обновления", reply_markup=kb.back_to_editing())

@router.callback_query(F.data == "info_clear", EditProfileForm.edit_info)
async def clear_info(callback: CallbackQuery, state: FSMContext, db):
    success = await update_profile_field(callback, 'additional_info', "", state=state, db=db)
    await callback.answer("✅ Описание удалено" if success else "❌ Ошибка")

@router.message(EditProfileForm.edit_photo, F.photo)
async def process_edit_photo(message: Message, state: FSMContext, db):
    """Пользователь прислал новое фото — обновляем поле photo_id."""
    photo_id = message.photo[-1].file_id

    success = await update_profile_field(message, 'photo_id', photo_id, state=state, db=db)
    if success:
        await state.clear()
        await message.answer("✅ Фото обновлено!", reply_markup=kb.back_to_editing())
    else:
        await message.answer("❌ Ошибка обновления фото", reply_markup=kb.back_to_editing())

@router.message(EditProfileForm.edit_name, ~F.text)
async def wrong_edit_name_format(message: Message):
    await message.answer("❌ Отправьте текстовое сообщение с именем и фамилией")

@router.message(EditProfileForm.edit_nickname, ~F.text)
async def wrong_edit_nickname_format(message: Message):
    await message.answer("❌ Отправьте текстовое сообщение с игровым никнеймом")

@router.message(EditProfileForm.edit_age, ~F.text)
async def wrong_edit_age_format(message: Message):
    await message.answer(f"❌ Отправьте число больше {settings.MIN_AGE}")

@router.message(EditProfileForm.edit_info, ~F.text)
async def wrong_edit_info_format(message: Message):
    await message.answer("❌ Отправьте текстовое сообщение с описанием")

@router.message(EditProfileForm.edit_photo)
async def wrong_edit_photo_format(message: Message):
    await message.answer(
        "❌ Отправьте фотографию или используйте кнопки",
        reply_markup=kb.edit_photo_menu()
    )

# ==================== ОБРАБОТЧИКИ CALLBACK ====================

@router.callback_query(F.data.startswith("rating_"), EditProfileForm.edit_rating)
async def process_edit_rating(callback: CallbackQuery, state: FSMContext, db):
    rating = callback.data.split("_")[1]
    success = await update_profile_field(callback, 'rating', rating, state, db=db)
    await callback.answer("✅ Обновлено" if success else "❌ Ошибка")

@router.callback_query(F.data.startswith("region_"), EditProfileForm.edit_region)
async def process_edit_region(callback: CallbackQuery, state: FSMContext, db):
    region = callback.data.split("_")[1]
    success = await update_profile_field(callback, 'region', region, state, db=db)
    await callback.answer("✅ Обновлено" if success else "❌ Ошибка")

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
async def edit_positions_done(callback: CallbackQuery, state: FSMContext, db):
    data = await state.get_data()
    selected = data.get('positions_selected', [])
    original = data.get('original_positions', [])

    if not selected:
        await callback.answer("❌ Выберите хотя бы одну позицию", show_alert=True)
        return

    if set(selected) == set(original):
        await callback.answer("✅ Позиции не изменились")
        await state.clear()
        await safe_edit_message(callback, "ℹ️ Позиции остались прежними", kb.back_to_editing())
        return

    await update_profile_field(callback, 'positions', selected, state, db=db)
    await callback.answer()

@router.callback_query(F.data == "pos_need", EditProfileForm.edit_positions)
async def edit_positions_need(callback: CallbackQuery):
    await callback.answer("⚠️ Выберите хотя бы одну позицию", show_alert=True)

@router.callback_query(F.data == "delete_info", EditProfileForm.edit_info)
async def delete_info(callback: CallbackQuery, state: FSMContext):
    await update_profile_field(callback, 'additional_info', "", state)
    await callback.answer()

@router.callback_query(F.data == "photo_delete", EditProfileForm.edit_photo)
async def delete_photo(callback: CallbackQuery, state: FSMContext, db):
    success = await update_profile_field(callback, 'photo_id', None, state, db=db)
    await callback.answer("✅ Фото удалено" if success else "❌ Ошибка")

@router.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit_message(callback, "❌ Редактирование отменено", kb.back_to_editing())
    await callback.answer()

# ==================== УДАЛЕНИЕ ПРОФИЛЯ ====================

@router.callback_query(F.data == "delete_profile")
@check_ban_and_profile()
async def confirm_delete_profile(callback: CallbackQuery, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']
    game_name = settings.GAMES.get(game, game)

    text = (f"🗑️ Удаление анкеты в {game_name}\n\n" +
           "Вы уверены? Это действие нельзя отменить.\n" +
           f"Все лайки и матчи в {game_name} будут удалены.")

    try:
        profile = await db.get_user_profile(user_id, game)
        if profile and profile.get('photo_id'):
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb.confirm_delete())
        else:
            await callback.message.edit_text(text, reply_markup=kb.confirm_delete())
    except Exception:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=kb.confirm_delete())

    await callback.answer()

@router.callback_query(F.data == "confirm_delete")
@check_ban_and_profile()
async def delete_profile(callback: CallbackQuery, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    success = await db.delete_profile(user_id, game)

    if success:
        game_name = settings.GAMES.get(game, game)
        text = f"✅ Анкета в {game_name} успешно удалена!\n\n"
        text += "Все связанные данные (лайки и матчи) также удалены.\n\n"
        text += "Вы можете создать новую анкету в любое время."

        buttons = [
            [kb.InlineKeyboardButton(text="📝 Создать новую анкету", callback_data="recreate_profile")],
            [kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(text, reply_markup=keyboard)
        logger.info(f"Профиль удален для {user_id} в {game}")
    else:
        text = "❌ Произошла ошибка при удалении анкеты.\n\nПопробуйте еще раз."
        await callback.message.edit_text(text, reply_markup=kb.back())

    await callback.answer()

@router.message(EditProfileForm.edit_photo, F.photo)
async def process_edit_photo_message(message: Message, state: FSMContext, db):
    """Пользователь прислал новое фото — обновляем поле photo_id."""
    photo_id = message.photo[-1].file_id

    success = await update_profile_field(message, 'photo_id', photo_id, state=state, db=db)

    if success:
        await state.clear()
        await message.answer("✅ Фото обновлено!", reply_markup=kb.back_to_editing())
    else:
        await message.answer("❌ Ошибка обновления фото", reply_markup=kb.back_to_editing())


@router.callback_query(F.data == "photo_delete", EditProfileForm.edit_photo)
async def process_edit_photo_delete(callback: CallbackQuery, state: FSMContext, db):
    success = await update_profile_field(callback, 'photo_id', None, state, db=db)
    await callback.answer("✅ Фото удалено" if success else "❌ Ошибка", show_alert=not success)