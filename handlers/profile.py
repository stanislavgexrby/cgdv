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

class ProfileForm(StatesGroup):
    name = State()
    nickname = State()
    age = State()
    rating = State()
    region = State()  # Добавить это состояние
    positions = State()
    additional_info = State()
    photo = State()

@router.callback_query(F.data == "create_profile")
async def start_create_profile(callback: CallbackQuery, state: FSMContext):
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
    game_name = settings.GAMES.get(game, game)

    await state.update_data(
        user_id=user_id,
        game=game,
        positions_selected=[]
    )

    await state.set_state(ProfileForm.name)
    text = f"📝 Создание анкеты для {game_name}\n\n{texts.QUESTIONS['name']}"
    await callback.message.edit_text(text, reply_markup=kb.cancel_profile_creation())
    await callback.answer()

@router.message(ProfileForm.name)
async def process_name(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Отправьте текстовое сообщение с именем и фамилией")
        return
        
    name = message.text.strip()

    if len(name) < 2 or len(name) > settings.MAX_NAME_LENGTH:
        await message.answer(
            f"❌ Имя должно быть от 2 до {settings.MAX_NAME_LENGTH} символов"
        )
        return

    if len(name.split()) < 2:
        await message.answer(
            "❌ Введите имя и фамилию"
        )
        return

    await state.update_data(name=name)
    await state.set_state(ProfileForm.nickname)
    await message.answer(
        texts.QUESTIONS["nickname"],
        reply_markup=kb.cancel_profile_creation()
    )

# Обработчик неправильного типа сообщения для имени
@router.message(ProfileForm.name, ~F.text)
async def wrong_name_format(message: Message, state: FSMContext):
    await message.answer(
        "❌ Отправьте текстовое сообщение с именем и фамилией"
    )

@router.message(ProfileForm.nickname)
async def process_nickname(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Отправьте текстовое сообщение с игровым никнеймом")
        return
        
    nickname = message.text.strip()

    if len(nickname) < 2 or len(nickname) > settings.MAX_NICKNAME_LENGTH:
        await message.answer(
            f"❌ Никнейм должен быть от 2 до {settings.MAX_NICKNAME_LENGTH} символов"
        )
        return

    await state.update_data(nickname=nickname)
    await state.set_state(ProfileForm.age)
    await message.answer(
        texts.QUESTIONS["age"],
        reply_markup=kb.cancel_profile_creation()
    )

@router.message(ProfileForm.nickname, ~F.text)
async def wrong_nickname_format(message: Message, state: FSMContext):
    await message.answer(
        "❌ Отправьте текстовое сообщение с игровым никнеймом"
    )

@router.message(ProfileForm.age)
async def process_age(message: Message, state: FSMContext):
    if not message.text:
        await message.answer(f"❌ Отправьте число больше {settings.MIN_AGE}:")
        return
        
    try:
        age = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Введите число"
        )
        return

    if age < settings.MIN_AGE:
        await message.answer(
            f"❌ Возраст должен быть больше {settings.MIN_AGE}:"
        )
        return

    await state.update_data(age=age)
    await state.set_state(ProfileForm.rating)

    data = await state.get_data()
    game = data['game']

    rating_text = "🏆 Выберите рейтинг:"
    await message.answer(rating_text, reply_markup=kb.ratings(game))

# Обработчик неправильного типа сообщения для возраста
@router.message(ProfileForm.age, ~F.text)
async def wrong_age_format(message: Message, state: FSMContext):
    await message.answer(
        f"❌ Отправьте число большее {settings.MIN_AGE}:"
    )

@router.callback_query(F.data.startswith("rating_"), ProfileForm.rating)
async def process_rating(callback: CallbackQuery, state: FSMContext):
    rating = callback.data.split("_")[1]

    await state.update_data(rating=rating)
    await state.set_state(ProfileForm.region)  # ИЗМЕНИТЬ: было ProfileForm.positions

    region_text = "🌍 Выберите регион:"  # ИЗМЕНИТЬ: было position_text
    await callback.message.edit_text(region_text, reply_markup=kb.regions())  # ИЗМЕНИТЬ: было kb.positions(game, [])
    await callback.answer()

@router.callback_query(F.data.startswith("region_"), ProfileForm.region)
async def process_region(callback: CallbackQuery, state: FSMContext):
    region = callback.data.split("_")[1]

    await state.update_data(region=region)
    await state.set_state(ProfileForm.positions)  # Теперь переходим к позициям

    data = await state.get_data()
    game = data['game']

    position_text = "⚔️ Выберите позиции (можно несколько):"
    await callback.message.edit_text(position_text, reply_markup=kb.positions(game, []))
    await callback.answer()

@router.callback_query(F.data.startswith("pos_add_"), ProfileForm.positions)
async def add_position(callback: CallbackQuery, state: FSMContext):
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
    data = await state.get_data()
    selected = data.get('positions_selected', [])

    if not selected:
        await callback.answer("❌ Выберите хотя бы одну позицию", show_alert=True)
        return

    await state.update_data(positions=selected)
    await state.set_state(ProfileForm.additional_info)

    await callback.message.edit_text(
        "📝 Расскажите о себе:",
        reply_markup=kb.skip_info()
    )
    await callback.answer()

@router.callback_query(F.data == "pos_need", ProfileForm.positions)
async def positions_need(callback: CallbackQuery):
    await callback.answer("⚠️ Выберите хотя бы одну позицию", show_alert=True)

@router.message(ProfileForm.additional_info)
async def process_additional_info(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Отправьте текстовое сообщение с описанием или нажмите 'Пропустить'")
        return
        
    info = message.text.strip()

    if len(info) > settings.MAX_INFO_LENGTH:
        await message.answer(
            f"❌ Слишком длинный текст (максимум {settings.MAX_INFO_LENGTH} символов)"
        )
        return

    await state.update_data(additional_info=info)
    await state.set_state(ProfileForm.photo)

    await message.answer(texts.QUESTIONS["photo"], reply_markup=kb.skip_photo())

@router.message(ProfileForm.additional_info, ~F.text)
async def wrong_info_format(message: Message, state: FSMContext):
    await message.answer("❌ Отправьте текстовое сообщение с описанием или нажмите 'Пропустить'")

@router.message(ProfileForm.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await save_profile(message, state, photo_id)

@router.callback_query(F.data == "skip_photo", ProfileForm.photo)
async def skip_photo(callback: CallbackQuery, state: FSMContext):
    await save_profile_callback(callback, state, None)

@router.callback_query(F.data == "skip_info", ProfileForm.additional_info)
async def skip_info(callback: CallbackQuery, state: FSMContext):
    await state.update_data(additional_info="")
    await state.set_state(ProfileForm.photo)

    await callback.message.edit_text(
        texts.QUESTIONS["photo"],
        reply_markup=kb.skip_photo()
    )
    await callback.answer()

@router.message(ProfileForm.photo)
async def wrong_photo_format(message: Message, state: FSMContext):
    await message.answer("❌ Отправьте фотографию или нажмите 'Пропустить'", reply_markup=kb.skip_photo())

async def save_profile(message: Message, state: FSMContext, photo_id: str):
    data = await state.get_data()

    success = db.update_user_profile(
        telegram_id=data['user_id'],
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

    await state.clear()

    if success:
        game_name = settings.GAMES.get(data['game'], data['game'])
        text = f"✅ Анкета для {game_name} создана! Теперь можете искать сокомандников."
        await message.answer(text, reply_markup=kb.back())
        logger.info(f"Профиль создан для {data['user_id']} в {data['game']}")
    else:
        await message.answer("❌ Ошибка сохранения", reply_markup=kb.back())

async def save_profile_callback(callback: CallbackQuery, state: FSMContext, photo_id: str):
    data = await state.get_data()

    success = db.update_user_profile(
        telegram_id=data['user_id'],
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

    await state.clear()

    if success:
        game_name = settings.GAMES.get(data['game'], data['game'])
        text = f"✅ Анкета для {game_name} создана! Теперь можете искать сокомандников."
        await callback.message.edit_text(text, reply_markup=kb.back())
        logger.info(f"Профиль создан для {data['user_id']} в {data['game']}")
    else:
        await callback.message.edit_text("❌ Ошибка сохранения", reply_markup=kb.back())

    await callback.answer()

@router.callback_query(F.data == "cancel")
async def cancel_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание анкеты отменено", reply_markup=kb.back())
    await callback.answer()