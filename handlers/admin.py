import logging
import contextlib
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings
from handlers.basic import admin_only, safe_edit_message
from handlers.notifications import notify_user_banned, notify_user_unbanned, notify_profile_deleted

# ==================== FSM СОСТОЯНИЯ ====================

class AdminAdForm(StatesGroup):
    waiting_ad_message = State()
    waiting_ad_caption = State()
    waiting_game_choice = State()
    waiting_interval_choice = State()
    editing_interval = State()

class AdminBanForm(StatesGroup):
    waiting_user_input = State()
    waiting_ban_duration = State()
    waiting_ban_reason = State()

logger = logging.getLogger(__name__)
router = Router()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def _parse_rep_data(data: str):
    """Парсинг данных жалобы: rep:<action>:<report_id>[:<user_id>[:<days>]]"""
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else None
    report_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    user_id = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
    days = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 7
    return action, report_id, user_id, days

def _format_datetime(dt):
    """Форматирование даты и времени"""
    if dt is None:
        return "—"
    if isinstance(dt, str):
        return dt[:16]
    try:
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)

def _truncate_text(text: str, limit: int = 1024) -> str:
    """Обрезка текста для Telegram"""
    if not text or len(text) <= limit:
        return text or ""
    return text[:limit-1] + "…"

def _format_user_info(user_id: int, username: str = None) -> str:
    """Форматирование информации о пользователе"""
    if username:
        return f"@{username} (ID: {user_id})"
    else:
        return f"ID: {user_id} (нет @username)"

# ==================== ГЛАВНОЕ МЕНЮ АДМИНКИ ====================

@router.callback_query(F.data == "admin_back")
@admin_only
async def admin_main_menu(callback: CallbackQuery):
    """Главное меню админ панели"""
    await safe_edit_message(callback, "Админ панель", kb.admin_main_menu())
    await callback.answer()

# ==================== СТАТИСТИКА ====================

@router.callback_query(F.data == "admin_stats")
@admin_only
async def show_admin_stats(callback: CallbackQuery, db):
    """Показ статистики бота"""
    lines = ["Статистика бота", "", "База данных: PostgreSQL"]

    # Redis
    try:
        if hasattr(db, '_redis'):
            pong = await db._redis.ping()
            lines.append(f"Redis: {'✅ OK' if pong else '❌ Недоступен'}")
        else:
            lines.append("Redis: ❌ Не подключен")
    except Exception:
        lines.append("Redis: ❌ Ошибка")

    # PostgreSQL
    if not hasattr(db, '_pg_pool') or db._pg_pool is None:
        lines.append("⚠️ Нет подключения к PostgreSQL.")
        await safe_edit_message(callback, "\n".join(lines), kb.admin_back_menu())
        await callback.answer()
        return

    try:
        async with db._pg_pool.acquire() as conn:
            stats = await db.get_database_stats()

            main_stats = [
                ("👥 Всего пользователей", "users_total"),
                ("👤 Пользователи с анкетами", "users_with_profiles"), 
                ("📝 Всего анкет", "profiles_total"),
                ("💖 Мэтчи", "matches_total"),
                ("❤️ Лайки", "likes_total"),
                ("🚩 Жалобы (всего)", "reports_total"),
                ("⏳ Ожидающие жалобы", "reports_pending"),
                ("🚫 Заблокированы", "active_bans"),
            ]

            for name, key in main_stats:
                value = stats.get(key, "ошибка")
                lines.append(f"{name}: {value}")

            games_data = stats.get("games_breakdown", {})
            if games_data:
                lines.append("\n📊 Статистика по играм:")
                for game, data in games_data.items():
                    game_name = settings.GAMES.get(game, game)
                    lines.append(f"  • {game_name}:")
                    lines.append(f"    👤 Пользователей: {data['users']}")
                    lines.append(f"    📝 Анкет: {data['profiles']}")

            try:
                rows = await conn.fetch("SELECT game, COUNT(*) AS cnt FROM profiles GROUP BY game")
                if rows:
                    lines.append("\n📊 Анкеты по играм:")
                    for row in rows:
                        game_name = settings.GAMES.get(row["game"], row["game"])
                        lines.append(f"  • {game_name}: {row['cnt']}")
            except Exception as e:
                logger.warning(f"Ошибка получения статистики по играм: {e}")

    except Exception as e:
        lines.append(f"❌ Не удалось получить статистику: {e}")

    text = "\n".join(lines)
    await safe_edit_message(callback, text, kb.admin_back_menu())
    await callback.answer()

# ==================== ЖАЛОБЫ ====================

@router.callback_query(F.data == "admin_reports")
@admin_only
async def show_admin_reports(callback: CallbackQuery, db):
    """Показ жалоб"""
    reports = await db.get_pending_reports()
    
    if not reports:
        text = "🚩 Нет ожидающих жалоб"
        await safe_edit_message(callback, text, kb.admin_back_menu())
        await callback.answer()
        return

    await _show_report(callback, reports[0], 0, len(reports), db)

async def _show_report(callback: CallbackQuery, report: dict, current_index: int, total_reports: int, db):
    """Показ отдельной жалобы с индексом и статистикой нарушений"""
    report_id = report['id']
    reported_user_id = report['reported_user_id']
    reporter_id = report['reporter_id']
    game = report.get('game', 'dota')
    
    profile = await db.get_user_profile(reported_user_id, game)
    game_name = settings.GAMES.get(game, game)
    
    reporter_info = _format_user_info(reporter_id, report.get('reporter_username'))
    reported_info = _format_user_info(reported_user_id, report.get('reported_username'))
    
    mod_stats = await db.get_user_moderation_stats(reported_user_id)
    
    header = (
        f"🚩 Жалоба #{report_id} ({current_index + 1}/{total_reports}) | {game_name}\n"
        f"📅 Дата: {_format_datetime(report.get('created_at'))}\n"
        f"👤 Жалоба от: {reporter_info}\n"
        f"🎯 На пользователя: {reported_info}\n"
        f"📋 Причина: {report.get('report_reason', 'inappropriate_content')}\n\n"
    )
    
    stats_text = "📊 <b>История нарушений:</b>\n"
    stats_text += f"• Жалоб всего: {mod_stats['reports_total']}\n"
    stats_text += f"• Подтвержденных жалоб: {mod_stats['reports_resolved']}\n"
    stats_text += f"• Банов всего: {mod_stats['bans_total']}\n"
    
    if mod_stats['last_ban']:
        last_ban = mod_stats['last_ban']
        ban_date = _format_datetime(last_ban['created_at'])
        stats_text += f"• Последний бан: {ban_date}\n"
        stats_text += f"• Причина: {last_ban['reason']}\n"
    else:
        stats_text += "• Последний бан: не было\n"
    
    if profile:
        body = "\n👤 <b>Анкета нарушителя:</b>\n\n" + texts.format_profile(profile, show_contact=True)
    else:
        body = f"\n❌ Анкета пользователя не найдена"
    
    text = _truncate_text(header + stats_text + body)
    keyboard = kb.admin_report_actions(reported_user_id, report_id, current_index, total_reports)
    
    photo_id = profile.get('photo_id') if profile else None
    
    try:
        if photo_id:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=photo_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            await safe_edit_message(callback, text, keyboard)
    except Exception as e:
        logger.error(f"Ошибка показа жалобы: {e}")
        await safe_edit_message(callback, text, keyboard)
    
    await callback.answer()

@router.callback_query(F.data.startswith("rep:nav:"))
@admin_only
async def navigate_reports(callback: CallbackQuery, db):
    """Навигация по жалобам"""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return
        
    direction = parts[2]
    current_index = int(parts[3]) if len(parts) > 3 else 0
    
    reports = await db.get_pending_reports()
    
    if direction == "next" and current_index + 1 < len(reports):
        await _show_report(callback, reports[current_index + 1], current_index + 1, len(reports), db)
    elif direction == "prev" and current_index > 0:
        await _show_report(callback, reports[current_index - 1], current_index - 1, len(reports), db)
    else:
        message = "Это последняя жалоба" if direction == "next" else "Это первая жалоба"
        await callback.answer(message, show_alert=True)

@router.callback_query(F.data.startswith("rep:"))
@admin_only
async def handle_report_action(callback: CallbackQuery, db):
    """Обработка действий с жалобами"""
    action, report_id, user_id, days = _parse_rep_data(callback.data)
    
    if not action:
        await callback.answer("❌ Неизвестное действие", show_alert=True)
        return
    
    if action == "del":
        await _delete_profile_action(callback, report_id, user_id, db)
    elif action == "ban":
        await _ban_user_action(callback, report_id, user_id, days, db)
    elif action == "ignore":
        await _dismiss_report_action(callback, report_id, db)
    elif action == "next":
        await _show_next_report(callback, db)
    else:
        await callback.answer("❌ Неподдерживаемое действие", show_alert=True)

async def _delete_profile_action(callback: CallbackQuery, report_id: int, user_id: int, db):
    """Удаление профиля по жалобе"""
    user = await db.get_user(user_id)
    game = (user.get("current_game") if user else "dota") or "dota"
    
    success_delete = await db.delete_profile(user_id, game)
    success_report = await db.update_report_status(report_id, status="resolved", admin_id=callback.from_user.id)
    
    if success_delete:
        await notify_profile_deleted(callback.bot, user_id, game)
        logger.info(f"Админ удалил профиль {user_id} по жалобе {report_id}")
    
    message = "🗑️ Профиль удален, пользователь уведомлен" if (success_delete and success_report) else "❌ Ошибка выполнения"
    await callback.answer(message, show_alert=not (success_delete and success_report))
    
    await _show_next_report(callback, db)

async def _ban_user_action(callback: CallbackQuery, report_id: int, user_id: int, days: int, db):
    """Бан пользователя по жалобе"""
    expires_at = datetime.utcnow() + timedelta(days=days)
    reason = f"Нарушение правил (жалоба #{report_id})"
    
    success_ban = await db.ban_user(user_id, reason, expires_at)
    success_report = await db.update_report_status(report_id, status="resolved", admin_id=callback.from_user.id)
    
    if success_ban:
        await notify_user_banned(callback.bot, user_id, expires_at)
        logger.info(f"Админ забанил пользователя {user_id} на {days} дней по жалобе {report_id}")
    
    message = f"Бан на {days} дней применен, пользователь уведомлен" if (success_ban and success_report) else "❌ Ошибка выполнения"
    await callback.answer(message, show_alert=not (success_ban and success_report))
    
    user = await db.get_user(user_id)
    if user and user.get('current_game'):
        await db._clear_pattern_cache(f"search:*:{user['current_game']}:*")
    
    await _show_next_report(callback, db)

async def _dismiss_report_action(callback: CallbackQuery, report_id: int, db):
    """Отклонение жалобы"""
    success = await db.update_report_status(report_id, status="ignored", admin_id=callback.from_user.id)
    
    message = "❌ Жалоба отклонена" if success else "❌ Ошибка обновления"
    await callback.answer(message, show_alert=not success)
    
    await _show_next_report(callback, db)

async def _show_next_report(callback: CallbackQuery, db):
    """Показ следующей жалобы"""
    reports = await db.get_pending_reports()
    
    if not reports:
        text = "✅ Больше жалоб нет"
        await safe_edit_message(callback, text, kb.admin_back_menu())
        return
    
    await _show_report(callback, reports[0], 0, len(reports), db)

# ==================== БАНЫ ====================

@router.callback_query(F.data.startswith("admin_unban_"))
@admin_only
async def admin_unban_user(callback: CallbackQuery, db):
    """Снятие бана пользователя"""
    try:
        user_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    success = await db.unban_user(user_id)
    
    if success:
        await notify_user_unbanned(callback.bot, user_id)
        logger.info(f"Админ снял бан с пользователя {user_id}")
        
        bans = await db.get_all_bans()
        if not bans:
            text = "✅ Бан снят!\n\nБольше активных банов нет."
            await safe_edit_message(callback, text, kb.admin_back_menu())
        else:
            await _show_ban(callback, bans[0], 0, len(bans))
        
        await callback.answer("✅ Бан снят и пользователь уведомлен")
    else:
        await callback.answer("❌ Ошибка снятия бана", show_alert=True)

@router.callback_query(F.data == "admin_bans")
@admin_only
async def show_admin_bans(callback: CallbackQuery, db):
    """Показ активных банов"""
    bans = await db.get_all_bans()
    
    if not bans:
        text = "✅ Нет активных банов"
        await safe_edit_message(callback, text, kb.admin_back_menu())
        await callback.answer()
        return
    
    await _show_ban(callback, bans[0], 0, len(bans))

async def _show_ban(callback: CallbackQuery, ban: dict, current_index: int, total_bans: int):
    """Показ отдельного бана"""
    ban_text = f"""🚫 Бан #{ban['id']} ({current_index + 1}/{total_bans})

👤 Пользователь: {ban.get('name', 'N/A')} (@{ban.get('username', 'нет username')})
🎯 Никнейм: {ban.get('nickname', 'N/A')}
📅 Дата бана: {_format_datetime(ban.get('created_at'))}
⏰ Истекает: {_format_datetime(ban.get('expires_at'))}
📝 Причина: {ban['reason']}

Что делать с этим баном?"""

    keyboard = kb.admin_ban_actions_with_nav(ban['user_id'], current_index, total_bans)
    await safe_edit_message(callback, ban_text, keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_ban_"))
@admin_only
async def navigate_bans(callback: CallbackQuery, db):
    """Навигация по банам"""
    parts = callback.data.split("_")
    if len(parts) < 4:
        return
    
    direction = parts[2]  # prev или next
    current_index = int(parts[3])
    
    bans = await db.get_all_bans()
    
    if direction == "next" and current_index + 1 < len(bans):
        await _show_ban(callback, bans[current_index + 1], current_index + 1, len(bans))
    elif direction == "prev" and current_index > 0:
        await _show_ban(callback, bans[current_index - 1], current_index - 1, len(bans))
    else:
        message = "Это последний бан" if direction == "next" else "Это первый бан"
        await callback.answer(message, show_alert=True)

# ==================== УПРАВЛЕНИЕ РЕКЛАМОЙ ====================

@router.callback_query(F.data == "admin_ads")
@admin_only
async def admin_ads_menu(callback: CallbackQuery, db):
    """Меню управления рекламой - список всех постов"""
    ads = await db.get_all_ads()
    
    if not ads:
        text = "📢 Рекламные посты\n\nНет рекламных постов.\n\nДобавьте первый пост, переслав боту сообщение с рекламой."
        await safe_edit_message(callback, text, kb.admin_ads_menu_empty())
    else:
        text = "📢 Управление рекламными постами:\n\n"
        for ad in ads:
            status = "✅" if ad['is_active'] else "❌"
            text += f"{status} <b>#{ad['id']}</b> - {ad['caption']}\n"
            text += f"   📊 Показ: каждые <b>{ad['show_interval']}</b> анкет\n\n"
        
        text += "\n💡 Нажмите на пост для управления"
        
        await safe_edit_message(callback, text, kb.admin_ads_menu_list(ads))
    
    await callback.answer()

@router.callback_query(F.data.startswith("ad_view_"))
@admin_only
async def view_ad_details(callback: CallbackQuery, db):
    try:
        ad_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return
    
    ads = await db.get_all_ads()
    ad = next((a for a in ads if a['id'] == ad_id), None)
    
    if not ad:
        await callback.answer("Реклама не найдена", show_alert=True)
        await admin_ads_menu(callback, db)
        return
    
    status = "✅ Активна" if ad['is_active'] else "❌ Выключена"
    created = ad['created_at'].strftime("%d.%m.%Y %H:%M") if hasattr(ad['created_at'], 'strftime') else str(ad['created_at'])[:16]
    
    games = ad.get('games', ['dota', 'cs'])
    if len(games) == 2:
        games_text = "Обе игры"
    elif 'dota' in games:
        games_text = "Dota 2"
    else:
        games_text = "CS2"
    
    text = (f"📢 Рекламный пост <b>#{ad['id']}</b>\n\n"
            f"<b>Название:</b> {ad['caption']}\n"
            f"<b>Игры:</b> {games_text}\n"
            f"<b>Статус:</b> {status}\n"
            f"<b>Интервал показа:</b> каждые {ad['show_interval']} анкет\n"
            f"<b>Создан:</b> {created}\n\n"
            f"<b>Управление:</b>")
    
    await safe_edit_message(callback, text, kb.admin_ad_actions(ad))
    await callback.answer()

@router.callback_query(F.data == "admin_add_ad")
@admin_only
async def start_add_ad(callback: CallbackQuery, state: FSMContext):
    """Начало добавления рекламы"""
    await state.set_state(AdminAdForm.waiting_ad_message)
    text = ("📢 Добавление рекламного поста\n\n"
            "<b>Шаг 1/3: Перешлите боту сообщение с рекламой</b>\n\n"
            "Сообщение может содержать:\n"
            "• Текст с форматированием\n"
            "• Фото или видео\n"
            "• Ссылки и кнопки\n\n"
            "Оно будет показываться пользователям во время поиска анкет.")
    
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_ads")]
    ])
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.message(AdminAdForm.waiting_ad_message)
async def receive_ad_message(message: Message, state: FSMContext, db):
    """Получение рекламного сообщения"""
    await state.update_data(
        message_id=message.message_id,
        chat_id=message.chat.id
    )
    
    await state.set_state(AdminAdForm.waiting_ad_caption)
    await message.answer(
        "✅ Сообщение получено!\n\n<b>Шаг 2/3: Отправьте краткое название</b>\n\nЭто название будет видно только в админ панели для удобства управления.",
        reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_ads")]
        ]),
        parse_mode='HTML'
    )

@router.message(AdminAdForm.waiting_ad_caption)
async def receive_ad_caption(message: Message, state: FSMContext, db):
    """Получение названия рекламы и переход к выбору игр"""
    caption = message.text[:100] if message.text else "Без названия"

    await state.update_data(caption=caption)
    await state.set_state(AdminAdForm.waiting_game_choice)
    
    text = (f"✅ Название сохранено: <b>{caption}</b>\n\n"
            f"<b>Шаг 3/4: В каких играх показывать рекламу?</b>")
    
    await message.answer(
        text,
        reply_markup=kb.game_choice_for_ad_keyboard(),
        parse_mode='HTML'
    )

@router.callback_query(F.data.startswith("adgame_"), AdminAdForm.waiting_game_choice)
async def select_games_for_ad(callback: CallbackQuery, state: FSMContext):
    """Выбор игр для показа рекламы"""
    choice = callback.data.split("_")[1]
    
    if choice == "dota":
        games = ['dota']
    elif choice == "cs":
        games = ['cs']
    else:  # both
        games = ['dota', 'cs']
    
    await state.update_data(games=games)
    await state.set_state(AdminAdForm.waiting_interval_choice)
    
    games_text = "обеих играх" if len(games) == 2 else ("Dota 2" if games[0] == "dota" else "CS2")
    
    text = (f"✅ Реклама будет показываться в <b>{games_text}</b>\n\n"
            f"<b>Шаг 4/4: Выберите интервал показа</b>\n\n"
            f"Через сколько анкет показывать эту рекламу?")
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.interval_choice_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("interval_"), AdminAdForm.waiting_interval_choice)
async def select_interval_for_new_ad(callback: CallbackQuery, state: FSMContext, db):
    try:
        interval = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка", show_alert=True)
        return
    
    data = await state.get_data()
    
    ad_id = await db.add_ad_post(
        message_id=data['message_id'],
        chat_id=data['chat_id'],
        caption=data['caption'],
        admin_id=callback.from_user.id,
        show_interval=interval,
        games=data.get('games', ['dota', 'cs'])
    )
    
    await state.clear()
    
    games = data.get('games', ['dota', 'cs'])
    games_text = "обеих играх" if len(games) == 2 else ("Dota 2" if games[0] == "dota" else "CS2")
    
    text = (f"✅ Рекламный пост <b>#{ad_id}</b> создан!\n\n"
            f"<b>Название:</b> {data['caption']}\n"
            f"<b>Игры:</b> {games_text}\n"
            f"<b>Интервал:</b> каждые {interval} анкет\n\n"
            f"Пост автоматически активен и будет показываться пользователям.")
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.admin_back_menu(),
        parse_mode='HTML'
    )
    await callback.answer("✅ Реклама добавлена!")

@router.callback_query(F.data.startswith("ad_toggle_"))
@admin_only
async def toggle_ad_status(callback: CallbackQuery, db):
    """Включение/выключение рекламы"""
    try:
        ad_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return
    
    await db.toggle_ad_status(ad_id)
    await callback.answer("✅ Статус изменён")
    await view_ad_details(callback, db)

@router.callback_query(F.data.startswith("ad_interval_"))
@admin_only
async def start_edit_interval(callback: CallbackQuery, state: FSMContext, db):
    """Начало редактирования интервала"""
    try:
        ad_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return
    
    ads = await db.get_all_ads()
    ad = next((a for a in ads if a['id'] == ad_id), None)
    
    if not ad:
        await callback.answer("Реклама не найдена", show_alert=True)
        return
    
    await state.update_data(editing_ad_id=ad_id)
    await state.set_state(AdminAdForm.editing_interval)
    
    text = (f"📢 Пост <b>#{ad_id}</b>: {ad['caption']}\n\n"
            f"<b>Текущий интервал:</b> каждые {ad['show_interval']} анкет\n\n"
            f"<b>Выберите новый интервал показа:</b>")
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.interval_choice_keyboard(ad_id, current_interval=ad['show_interval']),
        parse_mode='HTML'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("ad_games_"))
@admin_only
async def start_edit_games(callback: CallbackQuery, state: FSMContext, db):
    """Начало редактирования игр для рекламы"""
    try:
        ad_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return
    
    ads = await db.get_all_ads()
    ad = next((a for a in ads if a['id'] == ad_id), None)
    
    if not ad:
        await callback.answer("Реклама не найдена", show_alert=True)
        return
    
    current_games = ad.get('games', ['dota', 'cs'])
    
    text = (f"📢 Пост <b>#{ad_id}</b>: {ad['caption']}\n\n"
            f"<b>В каких играх показывать рекламу?</b>")
    
    await callback.message.edit_text(
        text,
        reply_markup=kb.game_choice_for_ad_edit_keyboard(ad_id, current_games),
        parse_mode='HTML'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("setgames_"))
async def apply_new_games(callback: CallbackQuery, db):
    """Применение нового списка игр"""
    try:
        parts = callback.data.split("_")
        ad_id = int(parts[1])
        choice = parts[2]
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных", show_alert=True)
        return
    
    if choice == "dota":
        games = ['dota']
    elif choice == "cs":
        games = ['cs']
    else:  # both
        games = ['dota', 'cs']
    
    success = await db.update_ad_games(ad_id, games)
    
    if success:
        games_text = "обеих играх" if len(games) == 2 else ("Dota 2" if games[0] == "dota" else "CS2")
        await callback.answer(f"✅ Теперь показывается в {games_text}")
        await view_ad_details(callback, db)
    else:
        await callback.answer("❌ Ошибка обновления", show_alert=True)

@router.callback_query(F.data.startswith("setint_"), AdminAdForm.editing_interval)
async def apply_new_interval(callback: CallbackQuery, state: FSMContext, db):
    """Применение нового интервала"""
    try:
        parts = callback.data.split("_")
        ad_id = int(parts[1])
        interval = int(parts[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных", show_alert=True)
        return
    
    data = await state.get_data()
    if data.get('editing_ad_id') != ad_id:
        await callback.answer("Ошибка: несовпадение ID", show_alert=True)
        return
    
    success = await db.update_ad_interval(ad_id, interval)
    await state.clear()
    
    if success:
        ads = await db.get_all_ads()
        ad = next((a for a in ads if a['id'] == ad_id), None)
        
        if not ad:
            await callback.answer("Ошибка: реклама не найдена", show_alert=True)
            return
        
        status = "✅ Активна" if ad['is_active'] else "❌ Выключена"
        created = ad['created_at'].strftime("%d.%m.%Y %H:%M") if hasattr(ad['created_at'], 'strftime') else str(ad['created_at'])[:16]
        
        text = (f"📢 Рекламный пост <b>#{ad['id']}</b>\n\n"
                f"<b>Название:</b> {ad['caption']}\n"
                f"<b>Статус:</b> {status}\n"
                f"<b>Интервал показа:</b> каждые {ad['show_interval']} анкет\n"
                f"<b>Создан:</b> {created}\n\n"
                f"<b>Управление:</b>")
        
        await callback.message.edit_text(
            text,
            reply_markup=kb.admin_ad_actions(ad),
            parse_mode='HTML'
        )
        await callback.answer(f"✅ Интервал изменён на {interval}")
    else:
        await callback.answer("❌ Ошибка обновления", show_alert=True)

@router.callback_query(F.data.startswith("ad_delete_"))
@admin_only
async def confirm_delete_ad(callback: CallbackQuery):
    """Подтверждение удаления рекламы"""
    try:
        ad_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return
    
    text = "⚠️ Вы уверены?\n\nЭто действие нельзя отменить."
    
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [
            kb.InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"ad_del_confirm_{ad_id}"),
            kb.InlineKeyboardButton(text="❌ Отмена", callback_data=f"ad_view_{ad_id}")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("ad_del_confirm_"))
@admin_only
async def delete_ad_confirmed(callback: CallbackQuery, db):
    """Подтверждённое удаление рекламы"""
    try:
        ad_id = int(callback.data.split("_")[3])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return
    
    success = await db.delete_ad_post(ad_id)
    
    if success:
        await callback.answer("✅ Реклама удалена", show_alert=True)
        await admin_ads_menu(callback, db)
    else:
        await callback.answer("❌ Ошибка удаления", show_alert=True)

@router.callback_query(F.data == "ad_back_to_list")
async def back_to_ads_list(callback: CallbackQuery, state: FSMContext, db):
    """Возврат к списку реклам"""
    await state.clear()
    await admin_ads_menu(callback, db)

# ==================== БАН ПОЛЬЗОВАТЕЛЯ ПО ID/USERNAME ====================

@router.callback_query(F.data == "admin_ban_user")
@admin_only
async def start_ban_user_process(callback: CallbackQuery, state: FSMContext):
    """Начало процесса бана пользователя"""
    await state.set_state(AdminBanForm.waiting_user_input)

    text = (
        "🚫 <b>Бан пользователя</b>\n\n"
        "<b>Шаг 1/3: Укажите пользователя</b>\n\n"
        "Введите Telegram ID или username пользователя:\n"
        "• <code>123456789</code> (Telegram ID)\n"
        "• <code>@username</code> (username)\n"
        "• <code>username</code> (без @)"
    )

    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])

    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.message(AdminBanForm.waiting_user_input)
async def receive_user_input(message: Message, state: FSMContext, db):
    """Получение ID или username пользователя"""
    user_input = message.text.strip()

    # Пытаемся найти пользователя
    user = None

    # Проверяем, это ID или username
    if user_input.isdigit():
        # Это Telegram ID
        user_id = int(user_input)
        user = await db.get_user(user_id)
        if not user:
            await message.answer(
                "❌ Пользователь с таким ID не найден в базе.\n\n"
                "Попробуйте другой ID или username:",
                reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
                    [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
                ]),
                parse_mode='HTML'
            )
            return
    else:
        # Это username
        username = user_input.lstrip('@')
        user = await db.get_user_by_username(username)
        if not user:
            await message.answer(
                f"❌ Пользователь с username @{username} не найден в базе.\n\n"
                "Попробуйте другой ID или username:",
                reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
                    [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
                ]),
                parse_mode='HTML'
            )
            return

    # Проверяем, не забанен ли уже
    is_banned = await db.is_user_banned(user['telegram_id'])
    if is_banned:
        ban_info = await db.get_user_ban(user['telegram_id'])
        expires_text = _format_datetime(ban_info.get('expires_at')) if ban_info else 'навсегда'

        await message.answer(
            f"⚠️ Пользователь уже забанен!\n\n"
            f"👤 ID: {user['telegram_id']}\n"
            f"📛 Username: @{user.get('username', 'нет')}\n"
            f"⏰ Истекает: {expires_text}\n"
            f"📝 Причина: {ban_info.get('reason', 'не указана')}\n\n"
            "Введите другого пользователя или отмените:",
            reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
                [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
            ]),
            parse_mode='HTML'
        )
        return

    # Получаем профиль для отображения
    current_game = user.get('current_game', 'dota')
    profile = await db.get_user_profile(user['telegram_id'], current_game) if current_game else None

    # Сохраняем данные пользователя
    await state.update_data(
        user_id=user['telegram_id'],
        username=user.get('username'),
        current_game=current_game,
        profile=profile
    )

    await state.set_state(AdminBanForm.waiting_ban_duration)

    # Формируем информацию о пользователе
    user_info = f"👤 ID: <code>{user['telegram_id']}</code>\n"
    if user.get('username'):
        user_info += f"📛 Username: @{user['username']}\n"
    if profile:
        user_info += f"🎮 Игра: {settings.GAMES.get(current_game, current_game)}\n"
        user_info += f"📝 Имя: {profile.get('name', 'нет')}\n"
        user_info += f"🎯 Никнейм: {profile.get('nickname', 'нет')}\n"

    text = (
        f"✅ Пользователь найден!\n\n"
        f"{user_info}\n"
        f"<b>Шаг 2/3: Выберите длительность бана:</b>"
    )

    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [
            kb.InlineKeyboardButton(text="7 дней", callback_data="banuser_days_7"),
            kb.InlineKeyboardButton(text="30 дней", callback_data="banuser_days_30")
        ],
        [
            kb.InlineKeyboardButton(text="90 дней", callback_data="banuser_days_90"),
            kb.InlineKeyboardButton(text="365 дней", callback_data="banuser_days_365")
        ],
        [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])

    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data.startswith("banuser_days_"), AdminBanForm.waiting_ban_duration)
async def select_ban_duration(callback: CallbackQuery, state: FSMContext):
    """Выбор длительности бана"""
    try:
        days = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка", show_alert=True)
        return

    await state.update_data(ban_days=days)
    await state.set_state(AdminBanForm.waiting_ban_reason)

    data = await state.get_data()
    user_id = data['user_id']
    username = data.get('username')

    user_info = f"👤 ID: <code>{user_id}</code>"
    if username:
        user_info += f" (@{username})"

    text = (
        f"✅ Выбрано: бан на <b>{days} дней</b>\n\n"
        f"{user_info}\n\n"
        f"<b>Шаг 3/3: Введите причину бана:</b>\n\n"
        f"Причина будет показана пользователю."
    )

    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text="Использовать стандартную", callback_data="banuser_default_reason")],
        [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "banuser_default_reason", AdminBanForm.waiting_ban_reason)
async def use_default_ban_reason(callback: CallbackQuery, state: FSMContext, db):
    """Использование стандартной причины бана"""
    await _apply_ban(callback, state, db, reason="Нарушение правил сообщества")

@router.message(AdminBanForm.waiting_ban_reason)
async def receive_ban_reason(message: Message, state: FSMContext, db):
    """Получение причины бана"""
    reason = message.text.strip()[:200]  # Ограничиваем длину

    if not reason:
        await message.answer(
            "❌ Причина не может быть пустой. Введите причину бана:",
            reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
                [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
            ])
        )
        return

    await _apply_ban(message, state, db, reason=reason)

async def _apply_ban(source, state: FSMContext, db, reason: str):
    """Применение бана"""
    data = await state.get_data()
    user_id = data['user_id']
    username = data.get('username')
    ban_days = data['ban_days']
    current_game = data.get('current_game')

    # Вычисляем дату окончания бана
    expires_at = datetime.utcnow() + timedelta(days=ban_days)

    # Применяем бан
    success = await db.ban_user(user_id, reason, expires_at)

    if success:
        # Отправляем уведомление пользователю
        bot = source.bot if hasattr(source, 'bot') else source.message.bot
        await notify_user_banned(bot, user_id, expires_at)

        # Очищаем кэш поиска
        if current_game:
            await db._clear_pattern_cache(f"search:*:{current_game}:*")

        logger.info(f"Админ забанил пользователя {user_id} на {ban_days} дней. Причина: {reason}")

        user_info = f"👤 ID: {user_id}"
        if username:
            user_info += f" (@{username})"

        text = (
            f"✅ <b>Пользователь успешно забанен!</b>\n\n"
            f"{user_info}\n"
            f"⏰ Длительность: {ban_days} дней\n"
            f"📝 Причина: {reason}\n"
            f"📅 До: {_format_datetime(expires_at)}\n\n"
            f"Пользователь получил уведомление о бане."
        )

        keyboard = kb.admin_back_menu()

        if isinstance(source, CallbackQuery):
            await source.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
            await source.answer("✅ Бан применён!")
        else:
            await source.answer(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        error_text = "❌ Ошибка применения бана. Попробуйте снова."

        if isinstance(source, CallbackQuery):
            await source.answer(error_text, show_alert=True)
        else:
            await source.answer(error_text)

    await state.clear()