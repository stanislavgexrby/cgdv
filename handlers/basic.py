import os
from datetime import datetime
import logging
import keyboards.keyboards as kb
import config.settings as settings
from functools import wraps
from typing import Optional
from functools import wraps
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile

from handlers.notifications import update_user_activity

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()

class SearchForm(StatesGroup):
    menu = State()
    filters = State()
    rating_filter = State()
    position_filter = State()
    region_filter = State()
    country_filter_input = State()
    goals_filter = State()
    browsing = State()
    waiting_message = State()
    waiting_report_message = State()

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
        if not settings.is_admin(callback.from_user.id):
            await callback.answer("У Вас нет прав для использования этой команды", show_alert=True)
            return
        return await func(callback, *args, **kwargs)
    return wrapper

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Безопасное редактирование сообщения с обработкой ошибок"""
    try:
        message = callback.message
        has_photo = bool(message.photo)

        if has_photo:
            await message.delete()
            await callback.bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        else:
            current_text = message.text or ""
            current_markup = message.reply_markup

            text_changed = current_text != text
            markup_changed = str(current_markup) != str(reply_markup)

            if text_changed or markup_changed:
                await message.edit_text(
                    text=text, 
                    reply_markup=reply_markup, 
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )

    except Exception as e:
        error_str = str(e).lower()
        if "message to edit not found" in error_str or "message is not modified" in error_str:
            logger.info(f"Сообщение не найдено для редактирования, создаем новое: {e}")
        else:
            logger.warning(f"Ошибка редактирования сообщения: {e}")
        
        try:
            await callback.message.delete()
        except Exception:
            pass

        try:
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        except Exception as e2:
            logger.error(f"Критическая ошибка отправки сообщения: {e2}")
            try:
                await callback.answer("Ошибка загрузки. Попробуйте еще раз", show_alert=True)
            except Exception:
                pass

async def get_menu_photo(bot, game: str = None):
    """Получить фото для меню (с кешированием file_id)"""
    photo_key = game if game in ['dota', 'cs'] else 'default'
    
    cached_id = settings.get_cached_photo_id(photo_key)
    if cached_id:
        return cached_id
    
    photo_path = settings.MENU_PHOTOS.get(photo_key)
    if photo_path and os.path.exists(photo_path):
        return FSInputFile(photo_path)
    
    return None

async def _save_last_menu_message_id(user_id: int, message_id: int, db):
    """Сохранение ID последнего сообщения меню в Redis"""
    try:
        if db and hasattr(db, '_redis'):
            key = f"last_menu_msg:{user_id}"
            await db._redis.setex(key, 3600, str(message_id))  # 1 час
    except Exception as e:
        logger.warning(f"Не удалось сохранить last_menu_message: {e}")

async def send_main_menu_with_photo(callback_or_message, text: str, keyboard, game: str = None, db=None):
    """Отправка главного меню с фото (с кешированием)"""
    photo = await get_menu_photo(callback_or_message.bot if hasattr(callback_or_message, 'bot') else None, game)

    user_id = None
    if hasattr(callback_or_message, 'from_user'):
        user_id = callback_or_message.from_user.id
    elif hasattr(callback_or_message, 'message') and hasattr(callback_or_message.message, 'chat'):
        user_id = callback_or_message.message.chat.id

    if not photo:
        if hasattr(callback_or_message, 'message'):
            await safe_edit_message(callback_or_message, text, keyboard)
        else:
            sent_msg = await callback_or_message.answer(text, reply_markup=keyboard, parse_mode='HTML')
            if user_id and db:
                await _save_last_menu_message_id(user_id, sent_msg.message_id, db)
        return

    try:
        if hasattr(callback_or_message, 'message'):
            await callback_or_message.message.delete()
            sent_message = await callback_or_message.message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            sent_message = await callback_or_message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )

        if user_id and db and sent_message:
            await _save_last_menu_message_id(user_id, sent_message.message_id, db)

        if isinstance(photo, FSInputFile) and sent_message.photo:
            photo_key = game if game in ['dota', 'cs'] else 'default'
            file_id = sent_message.photo[-1].file_id
            settings.cache_photo_id(photo_key, file_id)
            logger.info(f"Кеширован file_id для {photo_key}: {file_id}")

    except Exception as e:
        logger.warning(f"Ошибка отправки главного меню с фото для игры {game}: {e}")
        if hasattr(callback_or_message, 'message'):
            await safe_edit_message(callback_or_message, text, keyboard)
        else:
            sent_msg = await callback_or_message.answer(text, reply_markup=keyboard, parse_mode='HTML')
            if user_id and db and sent_msg:
                await _save_last_menu_message_id(user_id, sent_msg.message_id, db)

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

@router.callback_query(F.data == "rules_understood")
async def rules_understood(callback: CallbackQuery, db):
    """Понимание правил и переход в главное меню"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("Ошибка", show_alert=True)
        return

    game = user['current_game']
    profile = await db.get_user_profile(user_id, game)
    has_profile = profile is not None
    text = get_main_menu_text(game, has_profile)

    await send_main_menu_with_photo(callback, text, kb.main_menu(has_profile, game), game=game, db=db)
    await callback.answer()

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
    text = f"<b>Главное меню</b>\n\nИгра: {game_name}"

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

    await send_main_menu_with_photo(message, texts.WELCOME, kb.game_selection(), game=None, db=db)

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """Cardigans Gaming Team Finder - Помощь

Функции:
- Создание анкеты для каждой игры
- Поиск сокомандников
- Система лайков и мэтчей

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
async def cmd_admin(message: Message):
    if not settings.is_admin(message.from_user.id):
        await message.answer("Нет прав доступа", parse_mode='HTML')
        return

    await message.answer("🔧 Админ панель", reply_markup=kb.admin_main_menu(), parse_mode='HTML')

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

    await safe_edit_message(callback, texts.COMMUNITY_RULES_SIMPLE, kb.community_rules_simple())
    await callback.answer()

@router.callback_query(F.data.startswith("switch_"))
async def switch_game(callback: CallbackQuery, db):
    # Пропускаем callback'и типа switch_and_likes_ и switch_and_matches_
    if callback.data.startswith("switch_and_"):
        return

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

    await safe_edit_message(callback, texts.COMMUNITY_RULES_SIMPLE, kb.community_rules_simple())
    await callback.answer()

# ==================== НАВИГАЦИЯ ПО МЕНЮ ====================

@router.callback_query(F.data.in_(["main_menu", "back_to_main"]))
async def show_main_menu(callback: CallbackQuery, db):
    """Показ главного меню без автоматического переключения игр"""
    user_id = callback.from_user.id

    await update_user_activity(user_id, 'available', db)

    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await send_main_menu_with_photo(callback, texts.WELCOME, kb.game_selection(), game=None, db=db)
        await callback.answer()
        return

    game = user['current_game']
    profile = await db.get_user_profile(user_id, game)
    has_profile = profile is not None

    text = get_main_menu_text(game, has_profile)
    await send_main_menu_with_photo(callback, text, kb.main_menu(has_profile, game), game=game, db=db)
    await callback.answer()

@router.callback_query(F.data == "back_to_games")
async def back_to_games(callback: CallbackQuery):
    await send_main_menu_with_photo(callback, texts.WELCOME, kb.game_selection(), game=None)
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
    profile_text = texts.format_profile(profile)
    text = f"Ваша анкета в {game_name}:\n\n{profile_text}"

    keyboard = kb.view_profile_menu()

    try:
        await callback.message.delete()
        if profile.get('photo_id'):
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        else:
            await callback.message.answer(
                text=text,
                reply_markup=keyboard,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Ошибка отображения профиля: {e}")
        try:
            if profile.get('photo_id'):
                await callback.bot.send_photo(
                    chat_id=callback.message.chat.id,
                    photo=profile['photo_id'],
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            else:
                await callback.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
        except Exception as e2:
            logger.error(f"Критическая ошибка отображения профиля: {e2}")
            await callback.answer("Ошибка загрузки профиля", show_alert=True)

    await callback.answer()

# ==================== ОБРАБОТЧИК УВЕДОМЛЕНИЙ ====================

@router.callback_query(F.data == "dismiss_notification")
async def dismiss_notification(callback: CallbackQuery, db):
    """Удаление уведомления"""
    try:
        await callback.message.delete()
        await callback.answer("✅")
    except Exception as e:
        logger.warning(f"Ошибка удаления уведомления: {e}")
        await callback.answer("Скрыто")

    await update_user_activity(callback.from_user.id, db=db)

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
    current_info += texts.format_profile(profile)
    current_info += "\n\nЧто хотите изменить?"

    role = profile.get('role', 'player')
    keyboard = kb.edit_profile_menu(game, role)

    try:
        if profile.get('photo_id'):
            try:
                await callback.message.delete()
            except Exception:
                pass

            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=current_info,
                reply_markup=keyboard,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        else:
            await callback.message.edit_text(
                current_info, 
                reply_markup=keyboard, 
                parse_mode='HTML', 
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Ошибка отображения меню редактирования: {e}")
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=current_info, 
            reply_markup=keyboard, 
            parse_mode='HTML'
        )

    await callback.answer()