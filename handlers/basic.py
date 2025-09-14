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

async def _fetch_reports_for_admin(db, limit: int = 100):
    """Получение жалоб из БД"""
    try:
        reports = await db.get_pending_reports()
        return reports or []
    except Exception as e:
        logger.warning(f"Не удалось получить жалобы: {e}")
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

            if require_profile and not await db.has_profile(user_id, game):
                game_name = settings.GAMES.get(game, game)
                await callback.answer(f"❌ Сначала создайте анкету для {game_name}", show_alert=True)
                return

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
                reply_markup=reply_markup
            )
        else:
            await message.edit_text(text, reply_markup=reply_markup)

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

async def _refresh_reports_after_action(callback: CallbackQuery, db, just_id: int | None = None):
    reports = await db.get_pending_reports()
    if not reports:
        await safe_edit_message(callback, "✅ Больше жалоб нет", kb.admin_back_menu())
        await callback.answer()
        return

    # если передан just_id — показать следующую после обработанной
    idx = 0
    if just_id is not None:
        for i, r in enumerate(reports):
            if r["id"] == just_id:
                idx = i + 1
                break
        if idx >= len(reports):
            await safe_edit_message(callback, "✅ Больше жалоб нет", kb.admin_back_menu())
            await callback.answer()
            return

    await show_admin_report(callback, reports, idx, db=db)

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

    if not await db.switch_game(user_id, game):
        await callback.answer("❌ Ошибка переключения игры", show_alert=True)
        return

    await state.clear()

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

@router.callback_query(F.data.startswith("switch_"))
async def switch_game(callback: CallbackQuery, db):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = parts[1]
    user_id = callback.from_user.id

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

    if not has_profile:
        other_game = "dota" if game == "cs" else "cs"
        has_other_profile = await db.has_profile(user_id, other_game)

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

    try:
        if hasattr(db, '_redis'):
            pong = await db._redis.ping()
            lines.append(f"⚡ Redis: {'✅ OK' if pong else '❌ Недоступен'}")
        else:
            lines.append("⚡ Redis: ❌ Не подключен")
    except Exception:
        lines.append("⚡ Redis: ❌ Ошибка")

    if not hasattr(db, '_pg_pool') or db._pg_pool is None:
        lines.append("⚠️ Нет подключения к PostgreSQL.")
        await safe_edit_message(callback, "\n".join(lines), kb.admin_main_menu())
        await callback.answer()
        return

    try:
        async with db._pg_pool.acquire() as conn:
            stats_queries = [
                ("Пользователи", "SELECT COUNT(*) FROM users"),
                ("Анкеты", "SELECT COUNT(*) FROM profiles"), 
                ("Матчи", "SELECT COUNT(*) FROM matches"),
                ("Лайки", "SELECT COUNT(*) FROM likes"),
                ("Жалобы (всего)", "SELECT COUNT(*) FROM reports"),
                ("Ожидающих жалоб", "SELECT COUNT(*) FROM reports WHERE status = 'pending'"),
                ("Заблокированы", "SELECT COUNT(*) FROM bans WHERE expires_at > NOW()"),
            ]

            for name, query in stats_queries:
                try:
                    count = await conn.fetchval(query)
                    lines.append(f"• {name}: {count or 0}")
                except Exception as e:
                    logger.warning(f"Ошибка получения статистики {name}: {e}")
                    lines.append(f"• {name}: ошибка")

            try:
                rows = await conn.fetch("SELECT game, COUNT(*) AS cnt FROM profiles GROUP BY game")
                if rows:
                    lines.append("• Анкеты по играм:")
                    for row in rows:
                        game_name = settings.GAMES.get(row["game"], row["game"])
                        lines.append(f"    - {game_name}: {row['cnt']}")
            except Exception as e:
                logger.warning(f"Ошибка получения статистики по играм: {e}")

    except Exception as e:
        lines.append(f"ℹ️ Не удалось получить статистику: {e}")

    text = "\n".join(lines)
    await safe_edit_message(callback, text, kb.admin_main_menu())
    await callback.answer()

@router.callback_query(F.data == "admin_reports")
@admin_only
async def show_admin_reports(callback: CallbackQuery, db):
    reports = await db.get_pending_reports()

    if not reports:
        text = "🚩 Нет ожидающих жалоб"
        await safe_edit_message(callback, text, kb.admin_main_menu())
        await callback.answer()
        return

    await show_admin_report(callback, reports, 0, db=db)

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
async def admin_approve_report(callback: CallbackQuery, db):
    # admin_approve_report_{report_id}_{user_id}
    parts = callback.data.split("_")
    report_id = int(parts[-2])
    user_id   = int(parts[-1])   # не используем, но полезно для логов
    ok = await db.update_report_status(report_id, status="resolved", admin_id=callback.from_user.id)
    await callback.answer("✅ Жалоба одобрена" if ok else "❌ Не удалось обновить", show_alert=not ok)

def _fmt_until(dt: datetime | None) -> str:
    if not dt:
        return "перманентно"
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)

@router.callback_query(F.data.startswith("admin_ban_user_"))
@admin_only
async def admin_ban_user(callback: CallbackQuery, db):
    # формат: admin_ban_user_{report_id}_{user_id}_{days}
    try:
        parts = callback.data.split("_")
        report_id = int(parts[-3])
        user_id   = int(parts[-2])
        days      = int(parts[-1])
    except Exception as e:
        logger.error(f"admin_ban_user: bad callback_data {callback.data} → {e}")
        await callback.answer("❌ Неверные данные кнопки", show_alert=True)
        return

    until = datetime.utcnow() + timedelta(days=days)

    ok_ban = await db.ban_user(user_id, f"нарушение правил (жалоба), {days}d", until)
    ok_rep = await db.update_report_status(report_id, status="resolved", admin_id=callback.from_user.id)

    # 🔔 уведомление пользователю
    if ok_ban:
        try:
            await callback.bot.send_message(
                chat_id=user_id,
                text=texts.USER_BANNED.format(until_date=_fmt_until(until))
            )
        except Exception as e:
            logger.warning(f"notify banned user {user_id} failed: {e}")

    await callback.answer("🚫 Бан применён, жалоба закрыта" if (ok_ban and ok_rep) else "❌ Ошибка при бане/закрытии",
                          show_alert=not (ok_ban and ok_rep))

    # 🔄 обновляем панель на следующую жалобу
    await _refresh_reports_after_action(callback, db, just_id=report_id)

@router.callback_query(F.data.startswith("admin_dismiss_report_"))
@admin_only
async def admin_dismiss_report(callback: CallbackQuery, db):
    # admin_dismiss_report_{report_id}
    report_id = int(callback.data.rsplit("_", 1)[-1])

    ok = await db.update_report_status(report_id, status="ignored", admin_id=callback.from_user.id)
    await callback.answer("🙈 Жалоба отклонена" if ok else "❌ Не удалось обновить", show_alert=not ok)

    # 🔄 обновить панель жалоб
    await _refresh_reports_after_action(callback, db, just_id=report_id)


@router.callback_query(F.data.startswith("admin_delete_profile_"))
@admin_only
async def admin_delete_profile(callback: CallbackQuery, db):
    # admin_delete_profile_{report_id}_{user_id}
    parts = callback.data.split("_")
    report_id = int(parts[-2])
    user_id   = int(parts[-1])

    user = await db.get_user(user_id)
    game = (user.get("current_game") if user else "dota") or "dota"

    ok_del = await db.delete_profile(user_id, game)
    ok_rep = await db.update_report_status(report_id, status="resolved", admin_id=callback.from_user.id)

    # 🔔 уведомление пользователю об удалении анкеты
    if ok_del:
        try:
            await callback.bot.send_message(user_id, texts.PROFILE_DELETED_BY_ADMIN)
        except Exception:
            pass

    await callback.answer("🗑️ Анкета удалена, жалоба закрыта" if (ok_del and ok_rep) else "❌ Ошибка",
                          show_alert=not (ok_del and ok_rep))

    # 🔄 обновить панель жалоб
    await _refresh_reports_after_action(callback, db, just_id=report_id)

@router.callback_query(F.data.startswith("admin_next_report"))
@admin_only
async def admin_next_report(callback: CallbackQuery, db):
    parts = callback.data.split("_")
    current_id = int(parts[-1]) if len(parts) > 3 and parts[-1].isdigit() else None

    reports = await db.get_pending_reports()
    if not reports:
        await safe_edit_message(callback, "✅ Больше жалоб нет", kb.admin_back_menu())
        return

    idx = 0
    if current_id is not None:
        for i, r in enumerate(reports):
            if r["id"] == current_id:
                idx = i + 1
                break
        if idx >= len(reports):
            await safe_edit_message(callback, "✅ Больше жалоб нет", kb.admin_back_menu())
            await callback.answer()
            return

    await show_admin_report(callback, reports, idx, db=db)

@router.callback_query(F.data == "admin_back")
@admin_only
async def admin_back(callback: CallbackQuery):
    await safe_edit_message(callback, "👑 Админ панель", kb.admin_main_menu())
    await callback.answer()

@router.callback_query(F.data.startswith("admin_prev_report"))
@admin_only
async def admin_prev_report(callback: CallbackQuery, db):
    parts = callback.data.split("_")
    current_id = int(parts[-1]) if parts[-1].isdigit() else None

    reports = await db.get_pending_reports()
    if not reports:
        await safe_edit_message(callback, "🚩 Жалоб нет", kb.admin_back_menu())
        return

    idx = 0
    if current_id is not None:
        for i, r in enumerate(reports):
            if r["id"] == current_id:
                idx = max(0, i - 1)
                break

    await show_admin_report(callback, reports, idx, db=db)

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

        from .notifications import notify_user_unbanned
        await notify_user_unbanned(callback.bot, user_id)

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
    direction = parts[2]
    current_index = int(parts[3])

    reports = await db.get_pending_reports()

    if direction == "next" and current_index + 1 < len(reports):
        await show_admin_report(callback, reports, current_index + 1, db=db)
    elif direction == "prev" and current_index > 0:
        await show_admin_report(callback, reports, current_index - 1, db=db)
    else:
        message = "Это последняя жалоба" if direction == "next" else "Это первая жалоба"
        await callback.answer(message, show_alert=True)

@router.callback_query(F.data.startswith("admin_ban_"))
@admin_only
async def navigate_bans(callback: CallbackQuery, db):
    if not callback.data.startswith("admin_ban_next_") and not callback.data.startswith("admin_ban_prev_"):
        return

    parts = callback.data.split("_")
    direction = parts[2]
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

from aiogram.types import InputMediaPhoto

def _truncate_caption(s: str, limit: int = 1024) -> str:
    s = s or ""
    return s if len(s) <= limit else s[:limit-1] + "…"

def _fmt_dt(dt):
    if dt is None:
        return "—"
    if isinstance(dt, str):
        return dt[:16]
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)

async def show_admin_report(callback: CallbackQuery, reports: list[dict], idx: int, *, db):
    rep = reports[idx]
    game = rep.get("game", "dota")
    profile = await db.get_user_profile(rep["reported_user_id"], game)
    game_name = settings.GAMES.get(game, game)

    header = (
        f"🚩 Жалоба #{rep['id']} | {game_name}\n"
        f"Статус: {rep.get('status','pending')}\n"
        f"Причина: {rep.get('report_reason','inappropriate_content')}\n"
    )
    if profile:
        body = "👤 Объект жалобы:\n\n" + texts.format_profile(profile, show_contact=True)
    else:
        body = f"❌ Анкета {rep['reported_user_id']} не найдена"

    markup = kb.admin_report_actions(reported_user_id=rep["reported_user_id"], report_id=rep["id"])
    caption = _truncate_caption(header + "\n\n" + body)

    # если есть фото у анкеты — редактируем медиа
    photo_id = None
    if profile:
        photo_id = profile.get("photo_file_id") or profile.get("photo") or profile.get("photo_id")

    try:
        if photo_id:
            media = InputMediaPhoto(media=photo_id, caption=caption)
            await callback.message.edit_media(media=media, reply_markup=markup)
        else:
            # фоллбек: просто текст
            await safe_edit_message(callback, caption, markup)
    except Exception:
        # если media нельзя отредактировать (например, предыдущее сообщение было текстом/другим типом) — пошлём новое фото
        if photo_id:
            await callback.message.answer_photo(photo_id, caption=caption, reply_markup=markup)
            # опционально: старое сообщение убрать
            with contextlib.suppress(Exception):
                await callback.message.delete()
        else:
            await safe_edit_message(callback, caption, markup)

    await callback.answer()

    
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
📅 Дата бана: {_fmt_dt(ban.get('created_at'))}
⏰ Истекает: {_fmt_dt(ban.get('expires_at'))}
📝 Причина: {ban['reason']}

Что делать с этим баном?"""

    await safe_edit_message(callback, ban_text, 
                           kb.admin_ban_actions_with_nav(ban['user_id'], current_index, len(bans)))
    await callback.answer()