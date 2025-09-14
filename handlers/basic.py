import contextlib
from datetime import datetime, timedelta
import logging
import keyboards.keyboards as kb
import config.settings as settings
from functools import wraps
from typing import Optional
from functools import wraps
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()

class SearchForm(StatesGroup):
    filters = State()
    browsing = State()

__all__ = ['safe_edit_message', 'router', 'SearchForm']

# ==================== ДЕКОРАТОРЫ ДЛЯ ПРОВЕРОК ====================

def check_ban_and_profile(require_profile=True):
    """Декоратор для проверки бана и наличия профиля"""
    def decorator(func):
        @wraps(func)
        async def wrapper(callback: CallbackQuery, *args, db=None, **kwargs):
            if db is None:
                raise RuntimeError("Database instance not provided. Ensure DatabaseMiddleware injects 'db'.")

            user_id = callback.from_user.id

            if await db.is_user_banned(user_id):
                ban_info = await db.get_user_ban(user_id)
                if ban_info:
                    expires_at = ban_info['expires_at']
                    ban_end = _format_expire_date(expires_at)
                    text = f"Вы заблокированы до {ban_end} за: {ban_info.get('reason', 'нарушение правил')}"
                else:
                    text = "Вы заблокированы"

                await safe_edit_message(callback, text, kb.back())
                await callback.answer()
                return

            user = await db.get_user(user_id)
            if not user or not user.get('current_game'):
                await callback.answer("Ошибка", show_alert=True)
                return

            game = user['current_game']

            if require_profile:
                profile = await db.get_user_profile(user_id, game)
                has_profile = profile is not None
                if not has_profile:
                    game_name = settings.GAMES.get(game, game)
                    await callback.answer(f"Сначала создайте анкету для {game_name}", show_alert=True)
                    return

            return await func(callback, *args, db=db, **kwargs)
        return wrapper
    return decorator

def admin_only(func):
    """Декоратор для проверки прав администратора"""
    @wraps(func)
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("Нет прав", show_alert=True)
            return
        return await func(callback, *args, **kwargs)
    return wrapper

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Безопасное редактирование сообщения"""
    try:
        message = callback.message

        has_photo = bool(message.photo)
        current_text = message.caption if has_photo else (message.text or "")
        current_markup = message.reply_markup

        text_changed = current_text != text
        markup_changed = str(current_markup) != str(reply_markup)

        if not text_changed and not markup_changed:
            return

        if has_photo:
            await message.delete()
            await callback.bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await message.edit_text(text=text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        try:
            await callback.message.delete()
        except:
            pass
        try:
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e2:
            logger.error(f"Ошибка отправки нового сообщения: {e2}")

async def check_subscription(user_id: int, game: str, bot: Bot) -> bool:
    """Проверка подписки на канал"""
    if not settings.CHECK_SUBSCRIPTION:
        return True

    channel = settings.DOTA_CHANNEL if game == "dota" else settings.CS_CHANNEL
    if not channel:
        return True

    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except Exception as e:
        logger.error(f"Ошибка проверки подписки для канала {channel}: {e}")
        return False

def _format_expire_date(expires_at: str | datetime) -> str:
    """Приводим expires_at (str или datetime) к красивому виду"""
    if isinstance(expires_at, str):
        try:
            dt = datetime.fromisoformat(expires_at)
        except ValueError:
            return expires_at
    else:
        dt = expires_at

    return dt.strftime("%d.%m.%Y %H:%M (UTC)")


def get_main_menu_text(game: str, has_profile: bool) -> str:
    """Генерация текста главного меню"""
    game_name = settings.GAMES.get(game, game)
    text = f"Главное меню\n\nИгра: {game_name}"

    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += "\n\nСоздайте анкету для начала:"

    return text

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

@router.message(Command("start"))
async def cmd_start(message: Message, db):
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запустил бота")

    # Проверяем бан в самом начале
    if await db.is_user_banned(user_id):
        ban_info = await db.get_user_ban(user_id)
        if ban_info:
            expires_at = ban_info['expires_at']
            if isinstance(expires_at, str):
                ban_end = expires_at[:16]
            else:
                ban_end = expires_at.strftime("%Y-%m-%d %H:%M")
            text = f"Вы заблокированы до {ban_end}\n\nПричина: {ban_info.get('reason', 'нарушение правил')}"
        else:
            text = "Вы заблокированы"
        
        await message.answer(text, parse_mode='HTML')
        return

    user = await db.get_user(user_id)

    if user and user.get('current_game'):
        game = user['current_game']
        profile = await db.get_user_profile(user_id, game)
        has_profile = profile is not None
        text = get_main_menu_text(game, has_profile)
        await message.answer(text, reply_markup=kb.main_menu(has_profile, game), parse_mode='HTML')
    else:
        await message.answer(texts.WELCOME, reply_markup=kb.game_selection(), parse_mode='HTML')

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """TeammateBot - Помощь

Функции:
- Создание анкеты для каждой игры
- Поиск сокомандников
- Система лайков и матчей

Как пользоваться:
1. Выберите игру (Dota 2 или CS2)
2. Создайте анкету для выбранной игры
3. Ищите игроков с фильтрами
4. Лайкайте понравившихся
5. При взаимном лайке получите контакты

Команды:
/start - Главное меню
/help - Эта справка"""

    await message.answer(help_text, parse_mode='HTML')

@router.message(Command("admin"))
@admin_only
async def cmd_admin(message: Message):
    await message.answer("Админ панель", reply_markup=kb.admin_main_menu(), parse_mode='HTML')

# ==================== ВЫБОР И ПЕРЕКЛЮЧЕНИЕ ИГР ====================

@router.callback_query(F.data.startswith("game_"))
async def select_game(callback: CallbackQuery, db):
    game = callback.data.split("_")[1]
    user_id = callback.from_user.id
    username = callback.from_user.username

    if not await check_subscription(user_id, game, callback.bot):
        game_name = settings.GAMES.get(game, game)
        channel = settings.DOTA_CHANNEL if game == "dota" else settings.CS_CHANNEL

        text = (f"Чтобы использовать {game_name}, нужно подписаться на канал: {channel}\n\n"
               "1. Нажмите кнопку для перехода в канал\n"
               "2. Подпишитесь на канал\n"
               "3. Вернитесь в бота и нажмите 'Я подписался'\n\n"
               "Или нажмите 'Назад' для выбора другой игры:")

        await safe_edit_message(callback, text, kb.subscribe_channel_keyboard(game))
        await callback.answer()
        return

    logger.info(f"Пользователь {user_id} выбрал игру: {game}")

    await db.create_user(user_id, username, game)
    profile = await db.get_user_profile(user_id, game)
    has_profile = profile is not None
    text = get_main_menu_text(game, has_profile)

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()

@router.callback_query(F.data.startswith("switch_and_likes_"))
async def switch_and_show_likes(callback: CallbackQuery, state: FSMContext, db):
    """Переключение игры и показ лайков из уведомления"""
    parts = callback.data.split("_")

    if len(parts) < 4:
        logger.error(f"Неверный формат callback_data: {callback.data}")
        await callback.answer("Ошибка данных", show_alert=True)
        return

    game = parts[3]
    user_id = callback.from_user.id

    if game not in settings.GAMES:
        logger.error(f"Неверная игра в callback: {game}")
        await callback.answer("Неверная игра", show_alert=True)
        return

    logger.info(f"Переключение на игру {game} для показа лайков пользователя {user_id}")

    if not await db.switch_game(user_id, game):
        await callback.answer("Ошибка переключения игры", show_alert=True)
        return

    if await db.is_user_banned(user_id):
        ban_info = await db.get_user_ban(user_id)
        game_name = settings.GAMES.get(game, game)
        text = f"Вы заблокированы в {game_name}"
        if ban_info:
            expires_at = ban_info['expires_at']
            ban_end = _format_expire_date(expires_at)
            text += f" до {ban_end}"

        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    profile = await db.get_user_profile(user_id, game)
    if not profile:
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"Сначала создайте анкету для {game_name}", show_alert=True)
        return

    from handlers.likes import _show_likes_internal
    await _show_likes_internal(callback, user_id, game, state, db)
    await callback.answer(f"Переключено на {settings.GAMES.get(game, game)}")

@router.callback_query(F.data.startswith("switch_and_matches_"))
async def switch_and_show_matches(callback: CallbackQuery, state: FSMContext, db):
    """Переключение игры и показ матчей из уведомления"""
    parts = callback.data.split("_")

    if len(parts) < 4:
        logger.error(f"Неверный формат callback_data: {callback.data}")
        await callback.answer("Ошибка данных", show_alert=True)
        return

    game = parts[3]
    user_id = callback.from_user.id

    if game not in settings.GAMES:
        logger.error(f"Неверная игра в callback: {game}")
        await callback.answer("Неверная игра", show_alert=True)
        return

    logger.info(f"Переключение на игру {game} для показа матчей пользователя {user_id}")

    if not await db.switch_game(user_id, game):
        await callback.answer("Ошибка переключения игры", show_alert=True)
        return

    if await db.is_user_banned(user_id):
        ban_info = await db.get_user_ban(user_id)
        game_name = settings.GAMES.get(game, game)
        text = f"Вы заблокированы в {game_name}"
        if ban_info:
            expires_at = ban_info['expires_at']
            ban_end = _format_expire_date(expires_at)
            text += f" до {ban_end}"

        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    profile = await db.get_user_profile(user_id, game)
    if not profile:
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"Сначала создайте анкету для {game_name}", show_alert=True)
        return

    from handlers.likes import _show_matches_internal
    await _show_matches_internal(callback, user_id, game, state, db)
    await callback.answer(f"Переключено на {settings.GAMES.get(game, game)}")

@router.callback_query(F.data.startswith("switch_"))
async def switch_game(callback: CallbackQuery, db):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("Ошибка", show_alert=True)
        return

    game = parts[1]
    user_id = callback.from_user.id

    if not await check_subscription(user_id, game, callback.bot):
        game_name = settings.GAMES.get(game, game)
        channel = settings.DOTA_CHANNEL if game == "dota" else settings.CS_CHANNEL

        text = (f"Чтобы использовать {game_name}, нужно подписаться на канал: {channel}\n\n"
               "1. Нажмите кнопку для перехода в канал\n"
               "2. Подпишитесь на канал\n"
               "3. Вернитесь в бота и нажмите 'Я подписался'\n\n"
               "Или нажмите 'Назад' для выбора другой игры:")

        await callback.message.edit_text(text, reply_markup=kb.subscribe_channel_keyboard(game), parse_mode='HTML')
        await callback.answer()
        return

    logger.info(f"Переключение на игру: {game}")

    await db.switch_game(user_id, game)
    profile = await db.get_user_profile(user_id, game)
    has_profile = profile is not None
    text = get_main_menu_text(game, has_profile)

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()

# ==================== НАВИГАЦИЯ ПО МЕНЮ ====================

@router.callback_query(F.data.in_(["main_menu", "back_to_main"]))
async def show_main_menu(callback: CallbackQuery, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await safe_edit_message(callback, texts.WELCOME, kb.game_selection())
        await callback.answer()
        return

    game = user['current_game']
    profile = await db.get_user_profile(user_id, game)
    has_profile = profile is not None

    if not has_profile:
        other_game = "dota" if game == "cs" else "cs"
        other_profile = await db.get_user_profile(user_id, other_game)
        has_other_profile = other_profile is not None

        if has_other_profile:
            await db.switch_game(user_id, other_game)
            game = other_game
            has_profile = True

    text = get_main_menu_text(game, has_profile)
    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()

@router.callback_query(F.data == "back_to_games")
async def back_to_games(callback: CallbackQuery):
    await safe_edit_message(callback, texts.WELCOME, kb.game_selection())
    await callback.answer()

@router.callback_query(F.data == "view_profile")
@check_ban_and_profile()
async def view_profile(callback: CallbackQuery, db):
    """Показ анкеты пользователя"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']
    profile = await db.get_user_profile(user_id, game)

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
        logger.error(f"Ошибка отображения профиля: {e}")
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        except:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')

    await callback.answer()

# ==================== ВОЗВРАТ К РЕДАКТИРОВАНИЮ И ПОИСКУ ====================

@router.callback_query(F.data == "back_to_editing")
@check_ban_and_profile()
async def back_to_editing_handler(callback: CallbackQuery, db):
    """Возврат к меню редактирования"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']
    profile = await db.get_user_profile(user_id, game)

    game_name = settings.GAMES.get(game, game)
    current_info = f"Редактирование анкеты в {game_name}:\n\n"
    current_info += texts.format_profile(profile, show_contact=True)
    current_info += "\n\nЧто хотите изменить?"

    keyboard = kb.edit_profile_menu()

    try:
        if profile.get('photo_id'):
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=current_info,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            await callback.message.edit_text(current_info, reply_markup=keyboard, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка отображения профиля для редактирования: {e}")
        try:
            await callback.message.edit_text(current_info, reply_markup=keyboard, parse_mode='HTML')
        except:
            await callback.message.delete()
            await callback.message.answer(current_info, reply_markup=keyboard, parse_mode='HTML')

    await callback.answer()

@router.callback_query(F.data == "back_to_search")
@check_ban_and_profile()
async def back_to_search_handler(callback: CallbackQuery, state: FSMContext, db):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    await state.clear()
    await state.update_data(
        user_id=user_id,
        game=game,
        rating_filter=None,
        position_filter=None,
        profiles=[],
        current_index=0,
        message_with_photo=False
    )
    await state.set_state(SearchForm.filters)

    game_name = settings.GAMES.get(game, game)
    text = f"Поиск в {game_name}\n\nФильтры:\n\n"
    text += "<b>Рейтинг:</b> любой\n"
    text += "<b>Позиция:</b> любая\n\n"
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()