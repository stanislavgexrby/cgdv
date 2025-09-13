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

def _detect_db_backend(db):
    """
    Возвращает (backend_name, db_path_or_None).
    Для PostgreSQL пути нет, для SQLite может быть db.db_path.
    """
    # Простейшая эвристика — у Postgres-пула обычно есть атрибут pool/execute/fetch
    if hasattr(db, "pool"):
        return "PostgreSQL", None
    # Совместимость с старым SQLite-классом
    if hasattr(db, "db_path"):
        return "SQLite", getattr(db, "db_path", None)
    return "Unknown", None

async def _fetch_reports_for_admin(db, limit: int = 100):
    """
    Универсальная загрузка жалоб из БД без знания точного имени метода.
    Пытается вызвать любой из распространённых названий, чтобы не падать.
    Возвращает list (может быть пустым).
    """
    # кандидаты: добавь сюда свои реальные имена, если они есть
    candidate_methods = [
        ("get_reports", {"limit": limit}),
        ("get_all_reports", {"limit": limit}),
        ("list_reports", {"limit": limit}),
        ("fetch_reports", {"limit": limit}),
        ("admin_get_reports", {"limit": limit}),
        ("get_reports", {}),            # без limit
        ("get_all_reports", {}),
        ("list_reports", {}),
        ("fetch_reports", {}),
        ("admin_get_reports", {}),
    ]

    for name, kwargs in candidate_methods:
        if hasattr(db, name):
            meth = getattr(db, name)
            try:
                res = await meth(**kwargs) if kwargs else await meth()
                if res is None:
                    res = []
                return res
            except TypeError:
                # сигнатура другая — пробуем без аргументов
                try:
                    res = await meth()
                    if res is None:
                        res = []
                    return res
                except Exception as e:
                    logger.warning(f"Метод {name} есть, но не вызвался: {e}")
            except Exception as e:
                logger.warning(f"Не удалось получить жалобы через {name}: {e}")

    logger.warning("В Database нет подходящего метода для получения жалоб "
                   "(например, get_reports/list_reports/get_all_reports). "
                   "Покажем пустой список.")
    return []

def check_ban_and_profile(require_profile=True):
    """Декоратор для проверки бана и наличия профиля"""
    def decorator(func):
        @wraps(func)
        async def wrapper(callback: CallbackQuery, *args, db=None, **kwargs):
            if db is None:
                raise RuntimeError("Database instance not provided. Ensure DatabaseMiddleware injects 'db'.")

            user_id = callback.from_user.id
            user = await db.get_user(user_id)
            if not user or not user.get('current_game'):
                await callback.answer("❌ Ошибка", show_alert=True)
                return

            game = user['current_game']

            # Бан
            if await db.is_user_banned(user_id):
                ban_info = await db.get_user_ban(user_id)
                game_name = settings.GAMES.get(game, game)
                if ban_info:
                    ban_end = ban_info['expires_at'][:16]
                    text = f"🚫 Вы заблокированы в {game_name} до {ban_end}"
                else:
                    text = f"🚫 Вы заблокированы в {game_name}"
                await safe_edit_message(callback, text, kb.back())
                await callback.answer()
                return

            # Профиль (если требуется)
            if require_profile and not await db.has_profile(user_id, game):
                game_name = settings.GAMES.get(game, game)
                await callback.answer(f"❌ Сначала создайте анкету для {game_name}", show_alert=True)
                return

            # ВАЖНО: db передаём как именованный параметр
            return await func(callback, *args, db=db, **kwargs)
        return wrapper
    return decorator

def admin_only(func):
    """Декоратор для проверки прав администратора"""
    @wraps(func)
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        if callback.from_user.id != settings.ADMIN_ID:
            await callback.answer("❌ Нет прав", show_alert=True)
            return
        return await func(callback, *args, **kwargs)
    return wrapper

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Безопасное редактирование сообщения"""
    try:
        message = callback.message
        
        # Определяем тип текущего сообщения
        has_photo = bool(message.photo)
        current_text = message.caption if has_photo else (message.text or "")
        current_markup = message.reply_markup
        
        # Проверяем, нужно ли обновление
        text_changed = current_text != text
        markup_changed = str(current_markup) != str(reply_markup)
        
        if not text_changed and not markup_changed:
            return  # Нет изменений
        
        # Если у нас есть фото, всегда удаляем и создаем новое текстовое сообщение
        # потому что мы не можем превратить фото в текст через редактирование
        if has_photo:
            await message.delete()
            await callback.bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_markup=reply_markup
            )
        else:
            # Обычное текстовое сообщение - редактируем
            await message.edit_text(text, reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        # Fallback - удаляем и создаем новое
        try:
            await callback.message.delete()
        except:
            pass
        try:
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=reply_markup
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
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

def get_main_menu_text(game: str, has_profile: bool) -> str:
    """Генерация текста главного меню"""
    game_name = settings.GAMES.get(game, game)
    text = f"🏠 Главное меню\n\nИгра: {game_name}"
    
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

    user = await db.get_user(user_id)

    if user and user.get('current_game'):
        game = user['current_game']
        has_profile = await db.has_profile(user_id, game)
        text = get_main_menu_text(game, has_profile)
        await message.answer(text, reply_markup=kb.main_menu(has_profile, game))
    else:
        await message.answer(texts.WELCOME, reply_markup=kb.game_selection())

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """🎮 TeammateBot - Помощь

🔍 Функции:
• Создание анкеты для каждой игры
• Поиск сокомандников
• Система лайков и матчей

📝 Как пользоваться:
1. Выберите игру (Dota 2 или CS2)
2. Создайте анкету для выбранной игры
3. Ищите игроков с фильтрами
4. Лайкайте понравившихся
5. При взаимном лайке получите контакты

⚙️ Команды:
/start - Главное меню
/help - Эта справка"""

    await message.answer(help_text)

@router.message(Command("admin"))
@admin_only
async def cmd_admin(message: Message):
    await message.answer("👑 Админ панель", reply_markup=kb.admin_main_menu())

# ==================== ВЫБОР И ПЕРЕКЛЮЧЕНИЕ ИГР ====================

@router.callback_query(F.data.startswith("game_"))
async def select_game(callback: CallbackQuery, db):
    game = callback.data.split("_")[1]
    user_id = callback.from_user.id
    username = callback.from_user.username

    # Проверка подписки
    if not await check_subscription(user_id, game, callback.bot):
        game_name = settings.GAMES.get(game, game)
        channel = settings.DOTA_CHANNEL if game == "dota" else settings.CS_CHANNEL

        text = (f"❌ Чтобы использовать {game_name}, нужно подписаться на канал: {channel}\n\n"
               "1. Нажмите кнопку для перехода в канал\n"
               "2. Подпишитесь на канал\n"
               "3. Вернитесь в бота и нажмите '✅ Я подписался'\n\n"
               "Или нажмите '⬅️ Назад' для выбора другой игры:")

        await safe_edit_message(callback, text, kb.subscribe_channel_keyboard(game))
        await callback.answer()
        return

    logger.info(f"Пользователь {user_id} выбрал игру: {game}")

    await db.create_user(user_id, username, game)
    has_profile = await db.has_profile(user_id, game)
    text = get_main_menu_text(game, has_profile)

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()

@router.callback_query(F.data.startswith("switch_and_matches_"))
async def switch_and_show_matches(callback: CallbackQuery, state: FSMContext, db):
    """Переключение игры и показ матчей из уведомления"""
    parts = callback.data.split("_")
    
    if len(parts) < 4:
        logger.error(f"Неверный формат callback_data: {callback.data}")
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    game = parts[3]
    user_id = callback.from_user.id
    
    if game not in settings.GAMES:
        logger.error(f"Неверная игра в callback: {game}")
        await callback.answer("❌ Неверная игра", show_alert=True)
        return
    
    logger.info(f"Переключение на игру {game} для показа матчей пользователя {user_id}")
    
    # Переключаем игру и очищаем состояние
    if not await db.switch_game(user_id, game):
        await callback.answer("❌ Ошибка переключения игры", show_alert=True)
        return
    
    await state.clear()
    
    # Проверяем бан и показываем матчи
    if await db.is_user_banned(user_id):
        ban_info = await db.get_user_ban(user_id)
        game_name = settings.GAMES.get(game, game)
        text = f"🚫 Вы заблокированы в {game_name}"
        if ban_info:
            text += f" до {ban_info['expires_at'][:16]}"
        text += "\n\nРаздел 'Матчи' недоступен."
        
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    if not await db.has_profile(user_id, game):
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"❌ Сначала создайте анкету для {game_name}", show_alert=True)
        return

    await show_matches(callback, user_id, game)

@router.callback_query(F.data.startswith("switch_"))
async def switch_game(callback: CallbackQuery, db):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
        
    game = parts[1]
    user_id = callback.from_user.id

    # Проверка подписки
    if not await check_subscription(user_id, game, callback.bot):
        game_name = settings.GAMES.get(game, game)
        channel = settings.DOTA_CHANNEL if game == "dota" else settings.CS_CHANNEL

        text = (f"❌ Чтобы использовать {game_name}, нужно подписаться на канал: {channel}\n\n"
               "1. Нажмите кнопку для перехода в канал\n"
               "2. Подпишитесь на канал\n"
               "3. Вернитесь в бота и нажмите '✅ Я подписался'\n\n"
               "Или нажмите '⬅️ Назад' для выбора другой игры:")

        await callback.message.edit_text(text, reply_markup=kb.subscribe_channel_keyboard(game))
        await callback.answer()
        return

    logger.info(f"Переключение на игру: {game}")

    await db.switch_game(user_id, game)
    has_profile = await db.has_profile(user_id, game)
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
    has_profile = await db.has_profile(user_id, game)
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
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']
    profile = await db.get_user_profile(user_id, game)

    profile_text = texts.format_profile(profile, show_contact=True)
    game_name = settings.GAMES.get(game, game)
    text = f"👤 Ваша анкета в {game_name}:\n\n{profile_text}"

    try:
        if profile.get('photo_id'):
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=kb.back()
            )
        else:
            await safe_edit_message(callback, text, kb.back())
    except Exception as e:
        logger.error(f"Ошибка отображения профиля: {e}")
        await safe_edit_message(callback, text, kb.back())

    await callback.answer()

# ==================== ВОЗВРАТ К РЕДАКТИРОВАНИЮ И ПОИСКУ ====================

@router.callback_query(F.data == "back_to_editing")
@check_ban_and_profile()
async def back_to_editing_handler(callback: CallbackQuery, db):
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
    text = f"🔍 Поиск в {game_name}\n\nФильтры:\n\n"
    text += "🏆 Рейтинг: любой\n"
    text += "⚔️ Позиция: любая\n\n"
    text += "Настройте фильтры или начните поиск:"

    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

# ==================== АДМИН ПАНЕЛЬ ====================

@router.callback_query(F.data == "admin_stats")
@admin_only
async def show_admin_stats(callback: CallbackQuery, db):
    lines = ["📊 Статистика бота", "", "🗄 База данных: PostgreSQL"]

    # Redis (если есть в db)
    if hasattr(db, "redis"):
        try:
            pong = await db.redis.ping()
            lines.append(f"⚡ Redis: {'OK' if pong else '—'}")
        except Exception:
            lines.append("⚡ Redis: —")

    # 1) Если у твоего класса есть готовый метод get_stats() — используем его
    stats_dict = None
    if hasattr(db, "get_stats"):
        try:
            value = await db.get_stats()
            if isinstance(value, dict):
                stats_dict = value
        except Exception as e:
            lines.append(f"ℹ️ Не удалось получить расширенную статистику: {e}")

    profiles_by_game = []

    # 2) Фолбэк: собираем агрегаты напрямую через asyncpg pool
    if stats_dict is None:
        stats_dict = {}
        if not hasattr(db, "pool") or db.pool is None:
            lines.append("⚠️ Нет подключения к PostgreSQL (db.pool отсутствует).")
            await safe_edit_message(callback, "\n".join(lines), kb.admin_main_menu())
            await callback.answer()
            return

        try:
            async with db.pool.acquire() as conn:
                async def fetchval(sql: str):
                    try:
                        return await conn.fetchval(sql)
                    except Exception:
                        return None

                # Переименуй таблицы/поля под свою схему при необходимости —
                # если таблицы не найдены, метрика просто будет пропущена.
                totals = [
                    ("Пользователи",      "SELECT COUNT(*) FROM users"),
                    ("Анкеты",            "SELECT COUNT(*) FROM profiles"),
                    ("Матчи",             "SELECT COUNT(*) FROM matches"),
                    ("Лайки",             "SELECT COUNT(*) FROM likes"),
                    ("Жалобы (всего)",    "SELECT COUNT(*) FROM reports"),
                    ("Ожидающих жалоб",   "SELECT COUNT(*) FROM reports WHERE status = 'pending'"),
                    ("Заблокированы",     "SELECT COUNT(*) FROM bans WHERE expires_at > NOW()"),
                ]
                for key, sql in totals:
                    v = await fetchval(sql)
                    if v is not None:
                        stats_dict[key] = v

                # Профили по играм
                try:
                    rows = await conn.fetch("SELECT game, COUNT(*) AS cnt FROM profiles GROUP BY game")
                    profiles_by_game = [(r["game"], r["cnt"]) for r in rows]
                except Exception:
                    profiles_by_game = []

        except Exception as e:
            lines.append(f"ℹ️ Не удалось собрать статистику PostgreSQL: {e}")

    # 3) Форматируем вывод
    order = [
        "Пользователи",
        "Анкеты",
        "Матчи",
        "Лайки",
        "Жалобы (всего)",
        "Ожидающих жалоб",
        "Заблокированы",
    ]
    any_printed = False
    for key in order:
        if key in stats_dict and stats_dict[key] is not None:
            lines.append(f"• {key}: {stats_dict[key]}")
            any_printed = True

    if profiles_by_game:
        lines.append("• Анкеты по играм:")
        for game, cnt in profiles_by_game:
            game_name = settings.GAMES.get(game, game)
            lines.append(f"    - {game_name}: {cnt}")

    if not any_printed and not profiles_by_game:
        lines.append("ℹ️ Нет данных для отображения. "
                     "Добавь метод Database.get_stats() или проверь названия таблиц.")

    text = "\n".join(lines)
    await safe_edit_message(callback, text, kb.admin_main_menu())
    await callback.answer()

@router.callback_query(F.data == "admin_reports")
@admin_only
async def show_admin_reports(callback: CallbackQuery, db):
    reports = await _fetch_reports_for_admin(db, limit=100)
    # если совсем пусто — покажем понятное сообщение, а не молчим
    if not reports:
        await callback.message.edit_text("🚩 Жалоб пока нет или метод получения жалоб не реализован.")
        await callback.answer()
        return
    await show_admin_report(callback, reports, 0, db=db)  # ВАЖНО: db=db

@router.callback_query(F.data == "admin_bans")
@admin_only
async def show_admin_bans(callback: CallbackQuery, db):
    bans = await db.get_all_bans()

    if not bans:
        text = "✅ Нет активных банов"
        await safe_edit_message(callback, text, kb.admin_main_menu())
        await callback.answer()
        return

    await show_admin_ban(callback, bans, 0)

# ==================== ОБРАБОТЧИКИ ЖАЛОБ И БАНОВ ====================

@router.callback_query(F.data.startswith("admin_approve_"))
@admin_only
async def admin_approve_report(callback: CallbackQuery):
    await process_report_action(callback, "approve")

@router.callback_query(F.data.startswith("admin_ban_"))
@admin_only  
async def admin_ban_user(callback: CallbackQuery):
    await process_report_action(callback, "ban")

@router.callback_query(F.data.startswith("admin_dismiss_"))
@admin_only
async def admin_dismiss_report(callback: CallbackQuery):
    await process_report_action(callback, "dismiss")

@router.callback_query(F.data.startswith("admin_unban_"))
@admin_only
async def admin_unban_user(callback: CallbackQuery, db):
    try:
        user_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    success = await db.unban_user(user_id)

    if success:
        await callback.answer("✅ Бан снят")
        logger.info(f"Админ {settings.ADMIN_ID} снял бан с пользователя {user_id}")

        # Уведомляем пользователя
        from .notifications import notify_user_unbanned
        await notify_user_unbanned(callback.bot, user_id)

        # Показываем следующего
        bans = await db.get_all_bans()
        if not bans:
            text = "✅ Бан снят!\n\nБольше активных банов нет."
            await safe_edit_message(callback, text, kb.admin_main_menu())
        else:
            await show_admin_ban(callback, bans, 0)
    else:
        await callback.answer("❌ Ошибка снятия бана", show_alert=True)

# ==================== НАВИГАЦИЯ ПО АДМИН ПАНЕЛИ ====================

@router.callback_query(F.data.startswith("admin_report_"))
@admin_only
async def navigate_reports(callback: CallbackQuery, db):
    parts = callback.data.split("_")
    direction = parts[2]  # next или prev
    current_index = int(parts[3])
    
    reports = await db.get_pending_reports()
    
    if direction == "next" and current_index + 1 < len(reports):
        await show_admin_report(callback, reports, current_index + 1)
    elif direction == "prev" and current_index > 0:
        await show_admin_report(callback, reports, current_index - 1)
    else:
        message = "Это последняя жалоба" if direction == "next" else "Это первая жалоба"
        await callback.answer(message, show_alert=True)

@router.callback_query(F.data.startswith("admin_ban_"))
@admin_only
async def navigate_bans(callback: CallbackQuery, db):
    if not callback.data.startswith("admin_ban_next_") and not callback.data.startswith("admin_ban_prev_"):
        return  # Обработается другим обработчиком
        
    parts = callback.data.split("_")
    direction = parts[2]  # next или prev
    current_index = int(parts[3])
    
    bans = await db.get_all_bans()
    
    if direction == "next" and current_index + 1 < len(bans):
        await show_admin_ban(callback, bans, current_index + 1)
    elif direction == "prev" and current_index > 0:
        await show_admin_ban(callback, bans, current_index - 1)
    else:
        message = "Это последний бан" if direction == "next" else "Это первый бан"
        await callback.answer(message, show_alert=True)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ АДМИНКИ ====================

async def process_report_action(callback: CallbackQuery, action: str, db):
    """Обработка действий с жалобами"""
    try:
        report_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    report_info = await db.get_report_info(report_id)
    if not report_info:
        await callback.answer("❌ Жалоба не найдена", show_alert=True)
        return

    success = await db.process_report(report_id, action, settings.ADMIN_ID)

    if success:
        action_messages = {
            "approve": "✅ Профиль удален",
            "ban": "✅ Пользователь забанен", 
            "dismiss": "❌ Жалоба отклонена"
        }
        
        await callback.answer(action_messages[action])
        logger.info(f"Админ {settings.ADMIN_ID} выполнил действие {action} для жалобы {report_id}")

        # Уведомляем пользователя
        if action in ["approve", "ban"]:
            from .notifications import notify_profile_deleted, notify_user_banned
            await notify_profile_deleted(callback.bot, report_info['reported_user_id'], report_info['game'])
            
            if action == "ban":
                ban_info = await db.get_user_ban(report_info['reported_user_id'])
                if ban_info:
                    await notify_user_banned(callback.bot, report_info['reported_user_id'], ban_info['expires_at'])

        # Показываем следующую жалобу
        reports = await db.get_pending_reports()
        if not reports:
            text = "✅ Жалоба обработана! Больше жалоб нет."
            await safe_edit_message(callback, text, kb.admin_main_menu())
        else:
            await show_admin_report(callback, reports, 0)
    else:
        await callback.answer("❌ Ошибка обработки жалобы", show_alert=True)

async def show_admin_report(callback: CallbackQuery, reports: list, current_index: int, db):
    """Показ жалобы админу"""
    if current_index >= len(reports):
        text = "✅ Все жалобы просмотрены!"
        await safe_edit_message(callback, text, kb.admin_main_menu())
        await callback.answer()
        return

    report = reports[current_index]
    profile = await db.get_user_profile(report['reported_user_id'], report['game'])

    if not profile:
        game_name = settings.GAMES.get(report['game'], report['game'])
        report_text = f"""🚩 Жалоба #{report['id']} ({current_index + 1}/{len(reports)})

⚠️ ПРОФИЛЬ УЖЕ УДАЛЕН

🎮 Игра: {game_name}
👤 Пользователь: {report.get('name', 'N/A')} (@{report.get('username', 'нет username')})
🎯 Никнейм: {report.get('nickname', 'N/A')}
📅 Дата жалобы: {report['created_at'][:16]}

Профиль уже недоступен (возможно, удален пользователем)."""

        await safe_edit_message(callback, report_text, 
                               kb.admin_report_actions_with_nav(report['id'], current_index, len(reports)))
        await callback.answer()
        return

    game_name = settings.GAMES.get(report['game'], report['game'])
    report_text = f"🚩 Жалоба #{report['id']} ({current_index + 1}/{len(reports)})\n\n"
    report_text += f"🎮 Игра: {game_name}\n"
    report_text += f"📅 Дата жалобы: {report['created_at'][:16]}\n\n"
    report_text += "👤 АНКЕТА НАРУШИТЕЛЯ:\n"
    report_text += "━━━━━━━━━━━━━━━━━━\n"
    report_text += texts.format_profile(profile, show_contact=False)
    report_text += "\n━━━━━━━━━━━━━━━━━━\n"
    report_text += "⚖️ Что делать с этой анкетой?"

    try:
        if profile.get('photo_id'):
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer_photo(
                photo=profile['photo_id'],
                caption=report_text,
                reply_markup=kb.admin_report_actions_with_nav(report['id'], current_index, len(reports))
            )
        else:
            await safe_edit_message(callback, report_text, 
                                   kb.admin_report_actions_with_nav(report['id'], current_index, len(reports)))
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа жалобы: {e}")
        await callback.answer("❌ Ошибка загрузки")

async def show_admin_ban(callback: CallbackQuery, bans: list, current_index: int):
    """Показ бана админу"""
    if current_index >= len(bans):
        text = "✅ Все баны просмотрены!"
        await safe_edit_message(callback, text, kb.admin_main_menu())
        await callback.answer()
        return

    ban = bans[current_index]
    ban_text = f"""🚫 Бан #{ban['id']} ({current_index + 1}/{len(bans)})

👤 Пользователь: {ban.get('name', 'N/A')} (@{ban.get('username', 'нет username')})
🎯 Никнейм: {ban.get('nickname', 'N/A')}
📅 Дата бана: {ban['created_at'][:16]}
⏰ Истекает: {ban['expires_at'][:16]}
📝 Причина: {ban['reason']}

Что делать с этим баном?"""

    await safe_edit_message(callback, ban_text, 
                           kb.admin_ban_actions_with_nav(ban['user_id'], current_index, len(bans)))
    await callback.answer()

async def show_matches(callback: CallbackQuery, user_id: int, game: str, db):
    """Показ матчей пользователя"""
    matches = await db.get_matches(user_id, game)
    game_name = settings.GAMES.get(game, game)

    if not matches:
        text = f"💔 У вас пока нет матчей в {game_name}\n\n"
        text += "Чтобы получить матчи:\n"
        text += "• Лайкайте анкеты в поиске\n"
        text += "• Отвечайте на лайки других игроков"
        await safe_edit_message(callback, text, kb.back())
        await callback.answer(f"✅ Переключено на {game_name}")
        return

    text = f"💖 Ваши матчи в {game_name} ({len(matches)}):\n\n"
    for i, match in enumerate(matches, 1):
        name = match['name']
        username = match.get('username', 'нет username')
        text += f"{i}. {name} (@{username})\n"

    text += "\n💬 Вы можете связаться с любым из них!"

    buttons = []
    for i, match in enumerate(matches[:5]):
        name = match['name'][:15] + "..." if len(match['name']) > 15 else match['name']
        buttons.append([kb.InlineKeyboardButton(
            text=f"💬 {name}", 
            callback_data=f"contact_{match['telegram_id']}"
        )])

    buttons.append([kb.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit_message(callback, text, keyboard)
    await callback.answer(f"✅ Переключено на {game_name}")