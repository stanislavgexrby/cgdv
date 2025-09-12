import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from handlers.notifications import notify_about_match, notify_about_like, notify_user_banned, notify_profile_deleted
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.database import Database
import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()
db = Database(settings.DATABASE_PATH)

class SearchForm(StatesGroup):
    filters = State()
    browsing = State()

__all__ = ['safe_edit_message', 'router', 'SearchForm']


# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    logger.info(f"Пользователь {user_id} запустил бота")

    user = db.get_user(user_id)

    if user and user.get('current_game'):
        game = user['current_game']
        game_name = settings.GAMES.get(game, game)
        has_profile = db.has_profile(user_id, game)

        text = f"🏠 Главное меню\n\nТекущая игра: {game_name}"
        if has_profile:
            text += "\n\nВыберите действие:"
        else:
            text += "\n\nСоздайте анкету для начала:"

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
async def cmd_admin(message: Message):
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ Нет прав")
        return

    await message.answer("👑 Админ панель", reply_markup=kb.admin_main_menu())


# ==================== ВЫБОР И ПЕРЕКЛЮЧЕНИЕ ИГР ====================

@router.callback_query(F.data.startswith("game_"))
async def select_game(callback: CallbackQuery):
    game = callback.data.split("_")[1]
    user_id = callback.from_user.id
    username = callback.from_user.username

    if settings.CHECK_SUBSCRIPTION and not await check_subscription(user_id, game, callback.bot):
        game_name = settings.GAMES.get(game, game)
        channel = settings.DOTA_CHANNEL if game == "dota" else settings.CS_CHANNEL

        await safe_edit_message(callback, 
            f"❌ Чтобы использовать {game_name}, нужно подписаться на канал: {channel}\n\n"
            "1. Нажмите кнопку для перехода в канал\n"
            "2. Подпишитесь на канал\n"
            "3. Вернитесь в бота и нажмите '✅ Я подписался'\n\n"
            "Или нажмите '⬅️ Назад' для выбора другой игры:",
            kb.subscribe_channel_keyboard(game)
        )
        await callback.answer()
        return

    logger.info(f"Пользователь {user_id} выбрал игру: {game}")

    db.create_user(user_id, username, game)

    has_profile = db.has_profile(user_id, game)
    game_name = settings.GAMES.get(game, game)

    text = f"🏠 Главное меню\n\nИгра: {game_name}"

    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += "\n\nСоздайте анкету для начала:"

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()


@router.callback_query(F.data.startswith("switch_and_matches_"))
async def switch_and_show_matches(callback: CallbackQuery, state: FSMContext):
    """Переключение игры и показ матчей из уведомления"""
    # callback_data имеет формат: "switch_and_matches_cs" или "switch_and_matches_dota"
    # После split("_") получаем: ["switch", "and", "matches", "cs"]
    parts = callback.data.split("_")
    
    if len(parts) < 4:
        logger.error(f"Неверный формат callback_data: {callback.data}")
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    game = parts[3]  # Берем последний элемент - это название игры
    user_id = callback.from_user.id
    
    # Проверяем валидность игры
    if game not in settings.GAMES:
        logger.error(f"Неверная игра в callback: {game}, parts: {parts}")
        await callback.answer("❌ Неверная игра", show_alert=True)
        return
    
    logger.info(f"Переключение на игру {game} для показа матчей пользователя {user_id}")
    
    # Переключаем игру
    success = db.switch_game(user_id, game)
    if not success:
        await callback.answer("❌ Ошибка переключения игры", show_alert=True)
        return
    
    # Очищаем состояние FSM
    await state.clear()
    
    # Проверяем бан
    if db.is_user_banned(user_id):
        ban_info = db.get_user_ban(user_id)
        game_name = settings.GAMES.get(game, game)
        if ban_info:
            ban_end = ban_info['expires_at']
            text = f"🚫 Вы заблокированы в {game_name} до {ban_end[:16]}\n\nРаздел 'Матчи' недоступен."
        else:
            text = f"🚫 Вы заблокированы в {game_name}\n\nРаздел 'Матчи' недоступен."
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    # Проверяем наличие профиля
    if not db.has_profile(user_id, game):
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"❌ Сначала создайте анкету для {game_name}", show_alert=True)
        return

    # Получаем и показываем матчи
    matches = db.get_matches(user_id, game)
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
async def switch_game(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
        
    game = parts[1]
    user_id = callback.from_user.id

    if settings.CHECK_SUBSCRIPTION and not await check_subscription(user_id, game, callback.bot):
        game_name = settings.GAMES.get(game, game)
        channel = settings.DOTA_CHANNEL if game == "dota" else settings.CS_CHANNEL

        await callback.message.edit_text(
            f"❌ Чтобы использовать {game_name}, нужно подписаться на канал: {channel}\n\n"
            "1. Нажмите кнопку для перехода в канал\n"
            "2. Подпишитесь на канал\n"
            "3. Вернитесь в бота и нажмите '✅ Я подписался'\n\n"
            "Или нажмите '⬅️ Назад' для выбора другой игры:",
            reply_markup=kb.subscribe_channel_keyboard(game)
        )
        await callback.answer()
        return

    logger.info(f"Переключение на игру: {game}")

    db.switch_game(user_id, game)

    has_profile = db.has_profile(user_id, game)
    game_name = settings.GAMES.get(game, game)

    text = f"🏠 Главное меню\n\nИгра: {game_name}"

    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += f"\n\nУ вас пока нет анкеты для {game_name}.\nСоздайте анкету для начала:"

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()

# ==================== НАВИГАЦИЯ ПО МЕНЮ ====================

@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await safe_edit_message(callback, texts.WELCOME, kb.game_selection())
        await callback.answer()
        return

    game = user['current_game']
    has_profile = db.has_profile(user_id, game)
    game_name = settings.GAMES.get(game, game)

    text = f"🏠 Главное меню\n\nИгра: {game_name}"

    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += "\n\nСоздайте анкету для начала:"

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await safe_edit_message(callback, texts.WELCOME, kb.game_selection())
        await callback.answer()
        return

    game = user['current_game']
    has_profile = db.has_profile(user_id, game)
    game_name = settings.GAMES.get(game, game)

    text = f"🏠 Главное меню\n\nИгра: {game_name}"

    if has_profile:
        text += "\n\nВыберите действие:"
    else:
        text += "\n\nСоздайте анкету для начала:"

    await safe_edit_message(callback, text, kb.main_menu(has_profile, game))
    await callback.answer()


@router.callback_query(F.data == "back_to_games")
async def back_to_games(callback: CallbackQuery):
    await safe_edit_message(callback,
        texts.WELCOME,
        reply_markup=kb.game_selection()
    )
    await callback.answer()


# ==================== ПРОСМОТР ПРОФИЛЯ ====================

@router.callback_query(F.data == "view_profile")
async def view_profile(callback: CallbackQuery):
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
async def back_to_editing_handler(callback: CallbackQuery):
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
async def back_to_search_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    game = user['current_game']

    if not db.has_profile(user_id, game):
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"❌ Сначала создайте анкету для {game_name}", show_alert=True)
        return

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
async def show_admin_stats(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    try:
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM profiles")
            total_profiles = cursor.fetchone()[0]

            cursor = conn.execute("SELECT game, COUNT(*) FROM profiles GROUP BY game")
            profiles_by_game = cursor.fetchall()

            cursor = conn.execute("SELECT COUNT(*) FROM matches")
            total_matches = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM reports WHERE status = 'pending'")
            pending_reports = cursor.fetchone()[0]

        text = f"""📊 Статистика бота

👥 Всего пользователей: {total_users}
📄 Всего анкет: {total_profiles}"""

        for game, count in profiles_by_game:
            game_name = settings.GAMES.get(game, game)
            text += f"\n  - {game_name}: {count}"

        text += f"\n💖 Матчей: {total_matches}"
        text += f"\n🚩 Ожидающих жалоб: {pending_reports}"

        await safe_edit_message(callback, text, kb.admin_main_menu())
        await callback.answer()

    except Exception as e:
        await callback.message.answer(f"Ошибка получения статистики: {e}")
        await callback.answer()


@router.callback_query(F.data == "admin_reports")
async def show_admin_reports(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    reports = db.get_pending_reports()

    if not reports:
        text = "🚩 Нет ожидающих жалоб"
        await safe_edit_message(callback, text, kb.admin_main_menu())
        await callback.answer()
        return

    await show_admin_report(callback, reports, 0)


@router.callback_query(F.data == "admin_bans")
async def show_admin_bans(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    bans = db.get_all_bans()

    if not bans:
        text = "✅ Нет активных банов"
        await safe_edit_message(callback, text, kb.admin_main_menu())
        await callback.answer()
        return

    await show_admin_ban(callback, bans, 0)


# ==================== ОБРАБОТЧИКИ ЖАЛОБ И БАНОВ ====================

@router.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_report(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    try:
        report_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    report_info = db.get_report_info(report_id)
    if not report_info:
        await callback.answer("❌ Жалоба не найдена", show_alert=True)
        return

    success = db.process_report(report_id, 'approve', settings.ADMIN_ID)

    if success:
        await callback.answer("✅ Профиль удален")
        logger.info(f"Админ {settings.ADMIN_ID} удалил профиль по жалобе {report_id}")

        await notify_profile_deleted(
            callback.bot, 
            report_info['reported_user_id'], 
            report_info['game']
        )

        reports = db.get_pending_reports()
        if not reports:
            text = "✅ Жалоба обработана! Больше жалоб нет."
            await safe_edit_message(callback, text, kb.admin_main_menu())
        else:
            await show_admin_report(callback, reports, 0)
    else:
        await callback.answer("❌ Ошибка обработки жалобы", show_alert=True)


@router.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban_user(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    try:
        report_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    report_info = db.get_report_info(report_id)
    if not report_info:
        await callback.answer("❌ Жалоба не найдена", show_alert=True)
        return

    success = db.process_report(report_id, 'ban', settings.ADMIN_ID)

    if success:
        await callback.answer("✅ Пользователь забанен")
        logger.info(f"Админ {settings.ADMIN_ID} забанил пользователя по жалобе {report_id}")

        ban_info = db.get_user_ban(report_info['reported_user_id'])
        if ban_info:
            await notify_user_banned(callback.bot, report_info['reported_user_id'], ban_info['expires_at'])
        await notify_profile_deleted(
            callback.bot, 
            report_info['reported_user_id'], 
            report_info['game']
        )

        reports = db.get_pending_reports()
        if not reports:
            text = "✅ Жалоба обработана! Больше жалоб нет."
            await safe_edit_message(callback, text, kb.admin_main_menu())
        else:
            await show_admin_report(callback, reports, 0)
    else:
        await callback.answer("❌ Ошибка бана пользователя", show_alert=True)


@router.callback_query(F.data.startswith("admin_dismiss_"))
async def admin_dismiss_report(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    try:
        report_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    success = db.process_report(report_id, 'dismiss', settings.ADMIN_ID)
    
    if success:
        await callback.answer("❌ Жалоба отклонена")
        logger.info(f"Админ {settings.ADMIN_ID} отклонил жалобу {report_id}")
        
        reports = db.get_pending_reports()
        if not reports:
            text = "✅ Жалоба обработана! Больше жалоб нет."
            await safe_edit_message(callback, text, kb.admin_main_menu())
        else:
            await show_admin_report(callback, reports, 0)
    else:
        await callback.answer("❌ Ошибка обработки жалобы", show_alert=True)


@router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban_user(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    try:
        user_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    success = db.unban_user(user_id)

    if success:
        await callback.answer("✅ Бан снят")
        logger.info(f"Админ {settings.ADMIN_ID} снял бан с пользователя {user_id}")

        from .notifications import notify_user_unbanned
        await notify_user_unbanned(callback.bot, user_id)

        bans = db.get_all_bans()

        if not bans:
            text = "✅ Бан снят!\n\nБольше активных банов нет."
            await safe_edit_message(callback, text, kb.admin_main_menu())
        else:
            await show_admin_ban(callback, bans, 0)

    else:
        await callback.answer("❌ Ошибка снятия бана", show_alert=True)


# ==================== НАВИГАЦИЯ ПО ЖАЛОБАМ И БАНАМ ====================

@router.callback_query(F.data.startswith("admin_report_next_"))
async def admin_report_next(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        current_index = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка навигации", show_alert=True)
        return

    reports = db.get_pending_reports()
    next_index = current_index + 1

    if next_index < len(reports):
        await show_admin_report(callback, reports, next_index)
    else:
        await callback.answer("Это последняя жалоба", show_alert=True)


@router.callback_query(F.data.startswith("admin_report_prev_"))
async def admin_report_prev(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        current_index = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка навигации", show_alert=True)
        return

    reports = db.get_pending_reports()
    prev_index = current_index - 1

    if prev_index >= 0:
        await show_admin_report(callback, reports, prev_index)
    else:
        await callback.answer("Это первая жалоба", show_alert=True)


@router.callback_query(F.data.startswith("admin_ban_next_"))
async def admin_ban_next(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        current_index = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка навигации", show_alert=True)
        return

    bans = db.get_all_bans()
    next_index = current_index + 1

    if next_index < len(bans):
        await show_admin_ban(callback, bans, next_index)
    else:
        await callback.answer("Это последний бан", show_alert=True)


@router.callback_query(F.data.startswith("admin_ban_prev_"))
async def admin_ban_prev(callback: CallbackQuery):
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("❌ Нет прав", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        current_index = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка навигации", show_alert=True)
        return

    bans = db.get_all_bans()
    prev_index = current_index - 1

    if prev_index >= 0:
        await show_admin_ban(callback, bans, prev_index)
    else:
        await callback.answer("Это первый бан", show_alert=True)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def check_subscription(user_id: int, game: str, bot: Bot) -> bool:
    channel = None
    if game == "dota":
        channel = settings.DOTA_CHANNEL
    elif game == "cs":
        channel = settings.CS_CHANNEL

    if not channel or not settings.CHECK_SUBSCRIPTION:
        return True

    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False


async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    try:
        current_text = callback.message.text or callback.message.caption or ""
        current_markup = callback.message.reply_markup

        text_changed = current_text != text
        markup_changed = str(current_markup) != str(reply_markup)

        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=reply_markup)
        else:
            if text_changed or markup_changed:
                await callback.message.edit_text(
                    text=text,
                    reply_markup=reply_markup
                )

    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        try:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=reply_markup)
        except:
            pass


async def show_admin_report(callback: CallbackQuery, reports: list, current_index: int):
    if current_index >= len(reports):
        text = "✅ Все жалобы просмотрены!"
        await safe_edit_message(callback, text, kb.admin_main_menu())
        await callback.answer()
        return

    report = reports[current_index]

    profile = db.get_user_profile(report['reported_user_id'], report['game'])

    if not profile:
        game_name = settings.GAMES.get(report['game'], report['game'])
        report_text = f"""🚩 Жалоба #{report['id']} ({current_index + 1}/{len(reports)})

⚠️ ПРОФИЛЬ УЖЕ УДАЛЕН

🎮 Игра: {game_name}
👤 Пользователь: {report.get('name', 'N/A')} (@{report.get('username', 'нет username')})
🎯 Никнейм: {report.get('nickname', 'N/A')}
📅 Дата жалобы: {report['created_at'][:16]}

Профиль уже недоступен (возможно, удален пользователем)."""

        await safe_edit_message(callback, report_text, kb.admin_report_actions_with_nav(report['id'], current_index, len(reports)))
        await callback.answer()
        return

    game_name = settings.GAMES.get(report['game'], report['game'])

    report_text = f"🚩 Жалоба #{report['id']} ({current_index + 1}/{len(reports)})\n\n"
    report_text += f"🎮 Игра: {game_name}\n"
    report_text += f"📅 Дата жалобы: {report['created_at'][:16]}\n\n"

    report_text += "👤 АНКЕТА НАРУШИТЕЛЯ:\n"
    report_text += "━━━━━━━━━━━━━━━━━━\n"

    profile_text = texts.format_profile(profile, show_contact=False)
    report_text += profile_text

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
            await safe_edit_message(callback, report_text, kb.admin_report_actions_with_nav(report['id'], current_index, len(reports)))

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка показа жалобы: {e}")
        await callback.answer("❌ Ошибка загрузки")


async def show_admin_ban(callback: CallbackQuery, bans: list, current_index: int):
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

    await safe_edit_message(callback, ban_text, kb.admin_ban_actions_with_nav(ban['user_id'], current_index, len(bans)))
    await callback.answer()