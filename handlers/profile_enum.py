from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from enum import Enum
import logging
from aiogram import Router

import config.settings as settings
import keyboards.keyboards as kb
import utils.texts as texts

logger = logging.getLogger(__name__)
router = Router()

class ProfileForm(StatesGroup):
    name = State()
    nickname = State()
    age = State()
    rating = State()
    profile_url = State()
    region = State()
    positions = State()
    goals = State()
    additional_info = State()
    photo = State()

class ProfileStep(Enum):
    NAME = "name"
    NICKNAME = "nickname"
    AGE = "age"
    RATING = "rating"
    PROFILE_URL = "profile_url"
    REGION = "region"
    POSITIONS = "positions"
    GOALS = "goals"
    INFO = "additional_info"
    PHOTO = "photo"

PROFILE_STEPS_ORDER = [
    ProfileStep.NAME,
    ProfileStep.NICKNAME,
    ProfileStep.AGE,
    ProfileStep.RATING,
    ProfileStep.PROFILE_URL,
    ProfileStep.REGION,
    ProfileStep.POSITIONS,
    ProfileStep.GOALS,
    ProfileStep.INFO,
    ProfileStep.PHOTO
]

class EditProfileForm(StatesGroup):
    edit_name = State()
    edit_nickname = State()
    edit_age = State()
    edit_rating = State()
    edit_profile_url = State()
    edit_region = State()
    edit_positions = State()
    edit_goals = State()
    edit_info = State()
    edit_photo = State()

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
        elif step == ProfileStep.PROFILE_URL:
            current = data.get('profile_url', '')
            game = data.get('game', 'dota')
            if current:
                if game == 'dota':
                    return f"Текущая ссылка: <b>{current}</b>\n\nВведите новую ссылку на Dotabuff или нажмите 'Продолжить':"
                else:
                    return f"Текущая ссылка: <b>{current}</b>\n\nВведите новую ссылку на FACEIT или нажмите 'Продолжить':"
            else:
                if game == 'dota':
                    return "Ссылка не задана\n\nВведите ссылку на Dotabuff или нажмите 'Продолжить':"
                else:
                    return "Ссылка не задана\n\nВведите ссылку на FACEIT или нажмите 'Продолжить':"
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
        elif step == ProfileStep.GOALS:
            current = data.get('goals_selected', []) if show_current else []
            if current and show_current:
                if "any" in current:
                    goals_text = "Любая цель"
                else:
                    goals_names = [settings.GOALS.get(goal, goal) for goal in current]
                    goals_text = ", ".join(goals_names)
                return f"Текущие цели: <b>{goals_text}</b>\n\nИзмените выбор или продолжите с текущими:"
            return "Выберите ваши цели (можно несколько):"
        elif step == ProfileStep.INFO:
            current = data.get('additional_info', '')
            if current:
                return f"Текущее описание: <b>{current}</b>\n\nВведите новое описание или нажмите 'Продолжить':"
            else:
                return "Описание не задано\n\nВведите описание или нажмите 'Продолжить':"
        elif step == ProfileStep.PHOTO:
            current = data.get('photo_id', '')
            if current:
                return "Фото загружено\n\nОтправьте новое фото или нажмите 'Продолжить':"
            else:
                return "Фото не загружено\n\nОтправьте фото или нажмите 'Продолжить':"
    
    if step == ProfileStep.NAME:
        return texts.QUESTIONS['name']
    elif step == ProfileStep.NICKNAME:
        return texts.QUESTIONS['nickname'] 
    elif step == ProfileStep.AGE:
        return texts.QUESTIONS['age']
    elif step == ProfileStep.INFO:
        return texts.QUESTIONS['info']
    elif step == ProfileStep.PHOTO:
        return texts.QUESTIONS['photo']
    elif step == ProfileStep.RATING:
        return "Выберите рейтинг:"
    if step == ProfileStep.PROFILE_URL:
        game = data.get('game', 'dota') if data else 'dota'
        if game == 'dota':
            return "Введите ссылку на ваш Dotabuff профиль или нажмите 'Пропустить':\n\nПример: https://www.dotabuff.com/players/123456789"
        else:
            return "Введите ссылку на ваш FACEIT профиль или нажмите 'Пропустить':\n\nПример: https://www.faceit.com/en/players/nickname"
    elif step == ProfileStep.REGION:
        return "Выберите регион:"
    elif step == ProfileStep.POSITIONS:
        return "Выберите позиции (можно несколько):"
    elif step == ProfileStep.GOALS:
        return "Выберите ваши цели (можно несколько):"
    return "Вопрос"

async def show_profile_step(callback_or_message, state: FSMContext, step: ProfileStep, show_current: bool = False):
    """Показать шаг создания профиля с улучшенной навигацией"""
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
    elif step == ProfileStep.PROFILE_URL and data.get('profile_url') is not None:
        has_data = True
    elif step == ProfileStep.REGION and data.get('region'):
        has_data = True
    elif step == ProfileStep.POSITIONS and data.get('positions_selected'):
        has_data = True
    elif step == ProfileStep.GOALS and data.get('goals_selected'):
        has_data = True
    elif step == ProfileStep.INFO and 'additional_info' in data:
        has_data = True
    elif step == ProfileStep.PHOTO and data.get('photo_id'):
        has_data = True
    
    await state.update_data(current_step=step.value)
    
    show_existing_data = has_data and show_current
    text = await get_step_question_text(step, data, show_existing_data)
    
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
        
    elif step == ProfileStep.PROFILE_URL:
        await state.set_state(ProfileForm.profile_url)
        if show_continue_button:
            keyboard = kb.profile_creation_navigation(step.value, show_continue_button)
        else:
            keyboard = kb.skip_profile_url()

    elif step == ProfileStep.REGION:
        await state.set_state(ProfileForm.region)
        current_region = data.get('region') if show_existing_data else None
        keyboard = kb.regions(selected_region=current_region, with_navigation=True)
        
    elif step == ProfileStep.POSITIONS:
        await state.set_state(ProfileForm.positions)
        selected = data.get('positions_selected', []) if show_existing_data else []
        keyboard = kb.positions(game, selected=selected, with_navigation=True)

    elif step == ProfileStep.GOALS:
        await state.set_state(ProfileForm.goals)
        selected = data.get('goals_selected', []) if show_existing_data else []
        keyboard = kb.goals(selected=selected, with_navigation=True)

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
        try:
            await callback_or_message.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения в CallbackQuery: {e}")
        
    else:
        bot = callback_or_message.bot
        chat_id = callback_or_message.chat.id
        last_message_id = data.get('last_bot_message_id')
        
        try:
            await callback_or_message.delete()
        except Exception:
            pass
        
        if last_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=last_message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                logger.info(f"Успешно отредактировано сообщение {last_message_id}")
            except Exception as e:
                logger.error(f"Не удалось отредактировать сообщение {last_message_id}: {e}")
                sent_message = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                await state.update_data(last_bot_message_id=sent_message.message_id)
        else:
            logger.warning("Нет last_bot_message_id, создаю новое сообщение")
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            await state.update_data(last_bot_message_id=sent_message.message_id)