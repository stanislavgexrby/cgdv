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
    country_input = State()
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
    edit_country = State()
    edit_country_input = State()
    edit_positions = State()
    edit_goals = State()
    edit_info = State()
    edit_photo = State()

async def get_step_question_text(step: ProfileStep, data: dict = None, show_current: bool = False) -> str:
    if show_current and data:
        if step == ProfileStep.NAME:
            current = data.get('name', '')
            return f"Текущее имя: <b>{current}</b>\n\nВведите новое имя или нажмите 'Продолжить':"
        elif step == ProfileStep.NICKNAME:
            current = data.get('nickname', '')
            return f"Текущий игровой никнейм: <b>{current}</b>\n\nВведите новый никнейм или нажмите 'Продолжить':"
        elif step == ProfileStep.AGE:
            current = data.get('age', '')
            return f"Текущий возраст: <b>{current}</b>\n\nВведите новый возраст или нажмите 'Продолжить':"
        elif step == ProfileStep.RATING:
            current_rating = data.get('rating')
            if current_rating == 'any':
                current_text = 'Не указан'
            elif current_rating:
                current_text = settings.RATINGS.get(data.get('game', 'dota'), {}).get(current_rating, current_rating)
            else:
                current_text = 'Не указан'
            return f"Текущий рейтинг: <b>{current_text}</b>\n\nВыберите новый рейтинг или нажмите 'Продолжить':"
        elif step == ProfileStep.PROFILE_URL:
            current = data.get('profile_url', 'Не указана')
            return f"Текущая ссылка: <b>{current}</b>\n\nВведите новую ссылку или нажмите 'Продолжить':"
        elif step == ProfileStep.REGION:
            current_country = data.get('region')
            if current_country == 'any':
                current_text = 'Не указана'
            elif current_country:
                current_text = settings.MAIN_COUNTRIES.get(current_country) or settings.COUNTRIES_DICT.get(current_country, current_country)
            else:
                current_text = 'Не указана'
            return f"Текущая страна: <b>{current_text}</b>\n\nВыберите новую страну или нажмите 'Продолжить':"
        elif step == ProfileStep.POSITIONS:
            selected_positions = data.get('positions_selected', [])
            if 'any' in selected_positions:
                current_text = 'Не указаны'
            elif selected_positions:
                game = data.get('game', 'dota')
                pos_names = []
                for pos in selected_positions:
                    pos_names.append(settings.POSITIONS.get(game, {}).get(pos, pos))
                current_text = ', '.join(pos_names)
            else:
                current_text = 'Не указаны'
            return f"Текущие позиции: <b>{current_text}</b>\n\nВыберите новые позиции или нажмите 'Продолжить':"
        elif step == ProfileStep.GOALS:
            selected_goals = data.get('goals_selected', [])
            if 'any' in selected_goals:
                current_text = 'Не указаны'
            elif selected_goals:
                goal_names = []
                for goal in selected_goals:
                    goal_names.append(settings.GOALS.get(goal, goal))
                current_text = ', '.join(goal_names)
            else:
                current_text = 'Не указаны'
            return f"Текущие цели: <b>{current_text}</b>\n\nВыберите новые цели или нажмите 'Продолжить':"
        elif step == ProfileStep.INFO:
            current = data.get('additional_info', 'Не указано')
            return f"Текущее описание: <b>{current}</b>\n\nВведите новое описание или нажмите 'Продолжить':"
        elif step == ProfileStep.PHOTO:
            current = 'Установлено' if data.get('photo_id') else 'Не указано'
            return f"Текущее фото: <b>{current}</b>\n\nОтправьте новое фото или нажмите 'Продолжить':"
    
    if step == ProfileStep.NAME:
        return texts.QUESTIONS.get('name', "Введите имя:")
    elif step == ProfileStep.NICKNAME:
        return texts.QUESTIONS.get('nickname', "Введите никнейм:")
    elif step == ProfileStep.AGE:
        return texts.QUESTIONS.get('age', "Введите возраст:")
    elif step == ProfileStep.INFO:
        return texts.QUESTIONS['info']
    elif step == ProfileStep.PHOTO:
        return texts.QUESTIONS['photo']
    elif step == ProfileStep.RATING:
        return "Выберите рейтинг:"
    elif step == ProfileStep.PROFILE_URL:
        game = data.get('game', 'dota') if data else 'dota'
        if game == 'dota':
            return "Введите ссылку на профиль Dotabuff/OpenDota или нажмите 'Пропустить':\n\nНапример: https://www.dotabuff.com/players/123456789"
        elif game == 'cs':
            return "Введите ссылку на профиль Steam/FACEIT или нажмите 'Пропустить':\n\nНапример: https://www.faceit.com/en/players/nickname"
    elif step == ProfileStep.REGION:
        return "Выберите страну:"
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
        region = data.get('region') if show_existing_data else None
        keyboard = kb.countries(selected_country=region, with_navigation=True)
        
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