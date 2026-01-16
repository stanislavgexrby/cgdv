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
    waiting_ad_type = State()  # Новое состояние для выбора типа рекламы
    waiting_ad_caption = State()
    waiting_game_choice = State()
    waiting_region_choice = State()  # Новое состояние для выбора регионов
    waiting_expires_choice = State()  # Новое состояние для выбора срока действия
    waiting_custom_expires = State()  # Новое состояние для ввода даты вручную
    waiting_interval_choice = State()
    editing_interval = State()
    waiting_custom_interval = State()  # Новое состояние для ввода кастомного интервала

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
async def show_admin_stats_menu(callback: CallbackQuery):
    """Меню выбора типа статистики"""
    await safe_edit_message(callback, "Выберите тип статистики:", kb.admin_stats_menu())
    await callback.answer()

@router.callback_query(F.data == "admin_stats_general")
@admin_only
async def show_admin_stats(callback: CallbackQuery, db):
    """Показ общей статистики бота"""
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
    await safe_edit_message(callback, text, kb.admin_stats_menu())
    await callback.answer()

@router.callback_query(F.data == "admin_analytics")
@admin_only
async def show_admin_analytics(callback: CallbackQuery, db):
    """Расширенная аналитика"""

    await callback.answer("Собираю аналитику...", show_alert=False)

    try:
        async with db._pg_pool.acquire() as conn:
            # === КОНВЕРСИИ ===
            total_likes = await conn.fetchval("SELECT COUNT(*) FROM likes")
            total_matches = await conn.fetchval("SELECT COUNT(*) FROM matches")
            overall_conversion = (total_matches / total_likes * 100) if total_likes > 0 else 0

            # Конверсия по играм
            conversions_by_game = await conn.fetch("""
                SELECT
                    l.game,
                    COUNT(DISTINCT l.id) as likes_count,
                    COUNT(DISTINCT m.id) as matches_count,
                    CASE
                        WHEN COUNT(DISTINCT l.id) > 0
                        THEN ROUND((COUNT(DISTINCT m.id)::numeric / COUNT(DISTINCT l.id) * 100), 1)
                        ELSE 0
                    END as conversion_rate
                FROM likes l
                LEFT JOIN matches m ON l.from_user = m.user1 AND l.to_user = m.user2 AND l.game = m.game
                GROUP BY l.game
            """)

            # === АКТИВНОСТЬ ПО ДНЯМ НЕДЕЛИ ===
            activity_by_day = await conn.fetch("""
                SELECT
                    TO_CHAR(created_at, 'Day') as day_name,
                    EXTRACT(DOW FROM created_at) as day_num,
                    COUNT(*) as count
                FROM likes
                WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY day_num, day_name
                ORDER BY day_num
            """)

            # === RETENTION (возвращаемость) ===
            retention_7d = await conn.fetchval("""
                WITH first_activity AS (
                    SELECT telegram_id, MIN(created_at) as first_seen
                    FROM users
                    WHERE created_at > NOW() - INTERVAL '14 days'
                    GROUP BY telegram_id
                ),
                returned AS (
                    SELECT COUNT(DISTINCT u.telegram_id) as count
                    FROM users u
                    JOIN first_activity fa ON u.telegram_id = fa.telegram_id
                    WHERE u.last_activity > fa.first_seen + INTERVAL '7 days'
                )
                SELECT count FROM returned
            """) or 0

            total_new_users_14d = await conn.fetchval("""
                SELECT COUNT(*) FROM users
                WHERE created_at > NOW() - INTERVAL '14 days'
                AND created_at < NOW() - INTERVAL '7 days'
            """) or 0

            retention_rate = (retention_7d / total_new_users_14d * 100) if total_new_users_14d > 0 else 0

            # === ТОП РЕГИОНЫ ===
            top_regions = await conn.fetch("""
                SELECT region, COUNT(*) as count
                FROM profiles
                WHERE region IS NOT NULL AND region != 'any'
                GROUP BY region
                ORDER BY count DESC
                LIMIT 10
            """)

            # === КАЧЕСТВО ПРОФИЛЕЙ ===
            profile_quality = await conn.fetch("""
                SELECT quality, COUNT(*) as count
                FROM (
                    SELECT
                        CASE
                            WHEN (
                                CASE WHEN rating IS NOT NULL AND rating != 'any' THEN 1 ELSE 0 END +
                                CASE WHEN positions IS NOT NULL AND jsonb_array_length(positions) > 0 AND positions != '["any"]'::jsonb THEN 1 ELSE 0 END +
                                CASE WHEN region IS NOT NULL AND region != 'any' THEN 1 ELSE 0 END +
                                CASE WHEN goals IS NOT NULL AND jsonb_array_length(goals) > 0 AND goals != '["any"]'::jsonb THEN 1 ELSE 0 END +
                                CASE WHEN additional_info IS NOT NULL AND LENGTH(TRIM(additional_info)) > 0 THEN 1 ELSE 0 END +
                                CASE WHEN profile_url IS NOT NULL AND LENGTH(TRIM(profile_url)) > 0 THEN 1 ELSE 0 END +
                                CASE WHEN photo_id IS NOT NULL THEN 1 ELSE 0 END
                            ) >= 5 THEN 'Отличные (5+ полей)'
                            WHEN (
                                CASE WHEN rating IS NOT NULL AND rating != 'any' THEN 1 ELSE 0 END +
                                CASE WHEN positions IS NOT NULL AND jsonb_array_length(positions) > 0 AND positions != '["any"]'::jsonb THEN 1 ELSE 0 END +
                                CASE WHEN region IS NOT NULL AND region != 'any' THEN 1 ELSE 0 END +
                                CASE WHEN goals IS NOT NULL AND jsonb_array_length(goals) > 0 AND goals != '["any"]'::jsonb THEN 1 ELSE 0 END +
                                CASE WHEN additional_info IS NOT NULL AND LENGTH(TRIM(additional_info)) > 0 THEN 1 ELSE 0 END +
                                CASE WHEN profile_url IS NOT NULL AND LENGTH(TRIM(profile_url)) > 0 THEN 1 ELSE 0 END +
                                CASE WHEN photo_id IS NOT NULL THEN 1 ELSE 0 END
                            ) >= 3 THEN 'Средние (3-4 поля)'
                            ELSE 'Базовые (≤2 полей)'
                        END as quality
                    FROM profiles
                ) subquery
                GROUP BY quality
                ORDER BY
                    CASE quality
                        WHEN 'Отличные (5+ полей)' THEN 1
                        WHEN 'Средние (3-4 поля)' THEN 2
                        ELSE 3
                    END
            """)

            # === АКТИВНОСТЬ ПОЛЬЗОВАТЕЛЕЙ ===
            activity_stats = await conn.fetch("""
                SELECT activity_level, COUNT(*) as count
                FROM (
                    SELECT
                        CASE
                            WHEN last_activity > NOW() - INTERVAL '3 days' THEN 'Активные (3 дня)'
                            WHEN last_activity > NOW() - INTERVAL '7 days' THEN 'Средние (7 дней)'
                            WHEN last_activity > NOW() - INTERVAL '30 days' THEN 'Редкие (30 дней)'
                            ELSE 'Неактивные (>30 дней)'
                        END as activity_level
                    FROM users
                    WHERE last_activity IS NOT NULL
                ) subquery
                GROUP BY activity_level
                ORDER BY
                    CASE activity_level
                        WHEN 'Активные (3 дня)' THEN 1
                        WHEN 'Средние (7 дней)' THEN 2
                        WHEN 'Редкие (30 дней)' THEN 3
                        ELSE 4
                    END
            """)

            # === ФОРМИРУЕМ ТЕКСТ ===
            lines = [
                "📊 <b>РАСШИРЕННАЯ АНАЛИТИКА</b>",
                "",
                "<b>💹 КОНВЕРСИИ:</b>",
                f"  Общая конверсия: {overall_conversion:.1f}%",
                f"  (Мэтчи / Лайки: {total_matches} / {total_likes})",
            ]

            if conversions_by_game:
                lines.append("\n  По играм:")
                for row in conversions_by_game:
                    game_name = "Dota 2" if row['game'] == 'dota' else "CS2"
                    lines.append(f"    • {game_name}: {row['conversion_rate']}% ({row['matches_count']}/{row['likes_count']})")

            # Активность по дням
            lines.extend([
                "",
                "<b>📅 АКТИВНОСТЬ ПО ДНЯМ НЕДЕЛИ:</b>",
                "  (лайки за последние 30 дней)"
            ])

            if activity_by_day:
                for row in activity_by_day:
                    day_name = row['day_name'].strip()
                    bars = '█' * (row['count'] // 10 + 1)
                    lines.append(f"  {day_name}: {bars} {row['count']}")

            # Retention
            lines.extend([
                "",
                "<b>🔄 RETENTION (возвращаемость):</b>",
                f"  7-дневный retention: {retention_rate:.1f}%",
                f"  ({retention_7d} из {total_new_users_14d} вернулись)"
            ])

            # Топ регионы
            if top_regions:
                lines.extend([
                    "",
                    "<b>🌍 ТОП-10 РЕГИОНОВ:</b>"
                ])
                for i, row in enumerate(top_regions, 1):
                    lines.append(f"  {i}. {row['region']}: {row['count']}")

            # Качество профилей
            if profile_quality:
                lines.extend([
                    "",
                    "<b>⭐ КАЧЕСТВО ПРОФИЛЕЙ:</b>"
                ])
                for row in profile_quality:
                    lines.append(f"  • {row['quality']}: {row['count']}")

            # Активность пользователей
            if activity_stats:
                lines.extend([
                    "",
                    "<b>📈 АКТИВНОСТЬ ПОЛЬЗОВАТЕЛЕЙ:</b>"
                ])
                for row in activity_stats:
                    lines.append(f"  • {row['activity_level']}: {row['count']}")

            text = "\n".join(lines)

    except Exception as e:
        logger.error(f"Ошибка получения аналитики: {e}")
        text = f"❌ Ошибка получения аналитики:\n\n{str(e)}"

    await safe_edit_message(callback, text, kb.admin_stats_menu())
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
    
    # Получаем сообщение от жалобщика
    report_message = report.get('report_message')
    reason_text = f"«{report_message}»" if report_message else "не указана"

    header = (
        f"🚩 Жалоба #{report_id} ({current_index + 1}/{total_reports}) | {game_name}\n"
        f"📅 Дата: {_format_datetime(report.get('created_at'))}\n"
        f"👤 Жалоба от: {reporter_info}\n"
        f"🎯 На пользователя: {reported_info}\n"
        f"📋 Причина жалобы: {reason_text}\n\n"
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

    # Формируем текст с регионами
    regions = ad.get('regions', ['all'])
    if 'all' in regions:
        regions_text = "Все регионы"
    else:
        from config import settings
        region_names = []
        for region in regions[:3]:
            region_names.append(settings.COUNTRIES_DICT.get(region, region))
        regions_text = ", ".join(region_names)
        if len(regions) > 3:
            regions_text += f" +{len(regions) - 3}"

    text = (f"📢 Рекламный пост <b>#{ad['id']}</b>\n\n"
            f"<b>Название:</b> {ad['caption']}\n"
            f"<b>Игры:</b> {games_text}\n"
            f"<b>Регионы:</b> {regions_text}\n"
            f"<b>Статус:</b> {status}\n"
            f"<b>Интервал показа:</b> каждые {ad['show_interval']} анкет\n"
            f"<b>Создан:</b> {created}\n\n"
            f"<b>Управление:</b>")
    
    await safe_edit_message(callback, text, kb.admin_ad_actions(ad))
    await callback.answer()

@router.callback_query(F.data.startswith("ad_preview_"))
@admin_only
async def preview_ad_post(callback: CallbackQuery, db):
    """Предпросмотр рекламного поста"""
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

    # Отправляем предпросмотр
    try:
        # Копируем рекламное сообщение админу
        await callback.bot.copy_message(
            chat_id=callback.message.chat.id,
            from_chat_id=ad['chat_id'],
            message_id=ad['message_id']
        )

        # Отправляем пояснительное сообщение с кнопкой возврата
        preview_text = f"👆 Так выглядит рекламный пост <b>#{ad_id}</b> для пользователей\n\n"
        preview_text += f"<b>Название:</b> {ad['caption']}"

        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="◀️ Назад к посту", callback_data=f"ad_view_{ad_id}")]
        ])

        await callback.message.answer(
            preview_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

        await callback.answer("Предпросмотр отправлен")

    except Exception as e:
        logger.error(f"Ошибка предпросмотра рекламы: {e}")
        await callback.answer(
            "Ошибка загрузки рекламного поста. Возможно, оригинальное сообщение было удалено.",
            show_alert=True
        )

@router.callback_query(F.data == "admin_add_ad")
@admin_only
async def start_add_ad(callback: CallbackQuery, state: FSMContext):
    """Начало добавления рекламы"""
    # Очищаем state перед созданием новой рекламы (удаляет editing_ad_id и другие старые данные)
    await state.clear()
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

    await state.set_state(AdminAdForm.waiting_ad_type)
    await message.answer(
        "✅ Сообщение получено!\n\n"
        "<b>Шаг 2/6: Выберите тип рекламы</b>\n\n"
        "📋 <b>Копировать</b> - текст копируется, кнопка 'Продолжить' снизу поста\n"
        "  (для красивого отображения текстовых реклам без эмодзи Telegram)\n\n"
        "↗️ <b>Переслать</b> - сообщение пересылается из источника\n"
        "  (кнопка отдельно, сохраняется автор сообщения)",
        reply_markup=kb.ad_type_choice_keyboard(),
        parse_mode='HTML'
    )

@router.callback_query(F.data.startswith("adtype_"), AdminAdForm.waiting_ad_type)
async def select_ad_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа рекламы"""
    ad_type = callback.data.split("_")[1]  # 'copy' или 'forward'

    if ad_type not in ['copy', 'forward']:
        await callback.answer("❌ Неизвестный тип рекламы", show_alert=True)
        return

    await state.update_data(ad_type=ad_type)
    await state.set_state(AdminAdForm.waiting_ad_caption)

    type_name = "Копирование" if ad_type == 'copy' else "Пересылка"
    text = (
        f"✅ Выбран тип: <b>{type_name}</b>\n\n"
        f"<b>Шаг 3/6: Отправьте краткое название</b>\n\n"
        f"Это название будет видно только в админ панели для удобства управления."
    )

    await callback.message.edit_text(
        text,
        reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="❌ Отмена", callback_data="admin_ads")]
        ]),
        parse_mode='HTML'
    )
    await callback.answer()

@router.message(AdminAdForm.waiting_ad_caption)
async def receive_ad_caption(message: Message, state: FSMContext, db):
    """Получение названия рекламы и переход к выбору игр"""
    caption = message.text[:100] if message.text else "Без названия"

    await state.update_data(caption=caption)
    await state.set_state(AdminAdForm.waiting_game_choice)

    text = (f"✅ Название сохранено: <b>{caption}</b>\n\n"
            f"<b>Шаг 4/6: В каких играх показывать рекламу?</b>")

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

    # Логируем данные до сохранения
    data_before = await state.get_data()
    logger.info(f"select_games_for_ad: данные ДО обновления = {list(data_before.keys())}")

    # ВАЖНО: Проверяем, нет ли editing_ad_id от предыдущего редактирования
    if 'editing_ad_id' in data_before:
        logger.warning(f"⚠️ Обнаружен editing_ad_id={data_before['editing_ad_id']} при создании новой рекламы! Это ошибка!")

    await state.update_data(games=games, selected_regions=['all'])
    await state.set_state(AdminAdForm.waiting_region_choice)

    # Проверяем данные после сохранения
    data_after = await state.get_data()
    logger.info(f"select_games_for_ad: данные ПОСЛЕ обновления = {list(data_after.keys())}")

    games_text = "обеих играх" if len(games) == 2 else ("Dota 2" if games[0] == "dota" else "CS2")

    text = (f"✅ Реклама будет показываться в <b>{games_text}</b>\n\n"
            f"<b>Шаг 4/5: Выберите регионы для показа</b>\n\n"
            f"В каких регионах показывать рекламу?\n"
            f"Можно выбрать несколько или показывать во всех регионах.")

    await callback.message.edit_text(
        text,
        reply_markup=kb.ad_regions(selected_regions=['all']),
        parse_mode='HTML'
    )
    await callback.answer()

# === ОБРАБОТЧИКИ ВЫБОРА РЕГИОНОВ ДЛЯ РЕКЛАМЫ ===

@router.callback_query(F.data.startswith("ad_region_add_"), AdminAdForm.waiting_region_choice)
async def add_region_to_ad(callback: CallbackQuery, state: FSMContext):
    """Добавление региона в список для рекламы (универсальный для создания и редактирования)"""
    region = callback.data.split("_")[3]
    data = await state.get_data()
    selected_regions = data.get('selected_regions', [])
    editing_ad_id = data.get('editing_ad_id')  # Определяем режим

    # Если выбран "Все регионы", очищаем список и добавляем "all"
    if region == "all":
        selected_regions = ['all']
    else:
        # Убираем "all" если выбран конкретный регион
        if 'all' in selected_regions:
            selected_regions.remove('all')
        # Добавляем новый регион
        if region not in selected_regions:
            selected_regions.append(region)

    await state.update_data(selected_regions=selected_regions)

    # Обновляем клавиатуру в зависимости от режима
    await callback.message.edit_reply_markup(
        reply_markup=kb.ad_regions(
            selected_regions=selected_regions,
            editing=bool(editing_ad_id),
            ad_id=editing_ad_id
        )
    )
    await callback.answer()

@router.callback_query(F.data.startswith("ad_region_remove_"), AdminAdForm.waiting_region_choice)
async def remove_region_from_ad(callback: CallbackQuery, state: FSMContext):
    """Удаление региона из списка для рекламы (универсальный для создания и редактирования)"""
    region = callback.data.split("_")[3]
    data = await state.get_data()
    selected_regions = data.get('selected_regions', [])
    editing_ad_id = data.get('editing_ad_id')  # Определяем режим

    if region in selected_regions:
        selected_regions.remove(region)

    await state.update_data(selected_regions=selected_regions)

    # Обновляем клавиатуру в зависимости от режима
    await callback.message.edit_reply_markup(
        reply_markup=kb.ad_regions(
            selected_regions=selected_regions,
            editing=bool(editing_ad_id),
            ad_id=editing_ad_id
        )
    )
    await callback.answer()

@router.callback_query(F.data == "ad_region_other", AdminAdForm.waiting_region_choice)
async def show_all_regions_for_ad(callback: CallbackQuery, state: FSMContext):
    """Показать полный список всех регионов (универсальный для создания и редактирования)"""
    data = await state.get_data()
    selected_regions = data.get('selected_regions', [])
    editing_ad_id = data.get('editing_ad_id')  # Определяем режим

    await callback.message.edit_reply_markup(
        reply_markup=kb.ad_all_regions(
            selected_regions=selected_regions,
            editing=bool(editing_ad_id),
            ad_id=editing_ad_id
        )
    )
    await callback.answer()

@router.callback_query(F.data == "ad_region_back_main", AdminAdForm.waiting_region_choice)
async def back_to_main_regions_for_ad(callback: CallbackQuery, state: FSMContext):
    """Вернуться к основным регионам (универсальный для создания и редактирования)"""
    data = await state.get_data()
    selected_regions = data.get('selected_regions', [])
    editing_ad_id = data.get('editing_ad_id')  # Определяем режим

    await callback.message.edit_reply_markup(
        reply_markup=kb.ad_regions(
            selected_regions=selected_regions,
            editing=bool(editing_ad_id),
            ad_id=editing_ad_id
        )
    )
    await callback.answer()

@router.callback_query(F.data == "ad_region_need", AdminAdForm.waiting_region_choice)
async def region_need_reminder(callback: CallbackQuery):
    """Напоминание о необходимости выбрать регион"""
    await callback.answer("Выберите хотя бы один регион или 'Все регионы'", show_alert=True)

@router.callback_query(F.data == "ad_region_done", AdminAdForm.waiting_region_choice)
async def regions_selected_for_ad(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора регионов и переход к сроку действия (только для создания новой рекламы)"""
    data = await state.get_data()
    selected_regions = data.get('selected_regions', [])

    # Логируем состояние для диагностики
    logger.info(f"ad_region_done: keys in state = {list(data.keys())}")

    if not selected_regions:
        await callback.answer("Выберите хотя бы один регион!", show_alert=True)
        return

    # Этот обработчик только для создания новой рекламы (не для редактирования)
    # При редактировании используется ad_region_save_{id}
    if 'editing_ad_id' in data:
        logger.warning("ad_region_done вызван при редактировании, но это обработчик для создания!")
        await callback.answer("Используйте кнопку 'Сохранить'", show_alert=True)
        return

    await state.set_state(AdminAdForm.waiting_expires_choice)

    # Формируем текст с выбранными регионами
    if 'all' in selected_regions:
        regions_text = "Все регионы"
    else:
        from config import settings
        region_names = []
        for region in selected_regions[:5]:  # Показываем первые 5
            region_names.append(settings.COUNTRIES_DICT.get(region, region))
        regions_text = ", ".join(region_names)
        if len(selected_regions) > 5:
            regions_text += f" и ещё {len(selected_regions) - 5}"

    text = (f"✅ Регионы выбраны: <b>{regions_text}</b>\n\n"
            f"<b>Шаг 6/7: Выберите срок действия</b>\n\n"
            f"Через сколько времени реклама автоматически удалится?")

    await callback.message.edit_text(
        text,
        reply_markup=kb.ad_expires_choice_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer()

# === КОНЕЦ ОБРАБОТЧИКОВ РЕГИОНОВ ===

# === ОБРАБОТЧИКИ ВЫБОРА СРОКА ДЕЙСТВИЯ ===

@router.callback_query(F.data.startswith("ad_expires_"), AdminAdForm.waiting_expires_choice)
async def select_ad_expires(callback: CallbackQuery, state: FSMContext):
    """Выбор срока действия рекламы"""
    expires_choice = callback.data.split("_")[2]  # '1', '3', '7', '14', '30', 'never', 'custom'

    # Если выбрано "Указать дату"
    if expires_choice == 'custom':
        await state.set_state(AdminAdForm.waiting_custom_expires)

        text = (
            "📅 <b>Указание даты окончания рекламы</b>\n\n"
            "Введите дату, когда реклама должна автоматически удалиться.\n\n"
            "<b>Формат:</b> <code>ДД.ММ.ГГГГ</code> или <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>21.12.2025</code> - удалится 21 декабря 2025 в 00:00\n"
            "• <code>31.12.2025 23:59</code> - удалится 31 декабря 2025 в 23:59\n\n"
            "⚠️ Дата должна быть в будущем"
        )

        await callback.message.edit_text(
            text,
            reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
                [kb.InlineKeyboardButton(text="◀️ Назад", callback_data="ad_expires_back")]
            ]),
            parse_mode='HTML'
        )
        await callback.answer()
        return

    # Вычисляем expires_at для быстрых кнопок
    if expires_choice == 'never':
        expires_at = None
        expires_text = "Бессрочно"
    else:
        from datetime import datetime, timedelta
        days = int(expires_choice)
        expires_at = datetime.utcnow() + timedelta(days=days)
        expires_text = f"{days} {'день' if days == 1 else 'дня' if days < 5 else 'дней'}"

    await state.update_data(expires_at=expires_at)
    await state.set_state(AdminAdForm.waiting_interval_choice)

    text = (f"✅ Срок действия: <b>{expires_text}</b>\n\n"
            f"<b>Шаг 7/7: Выберите интервал показа</b>\n\n"
            f"Через сколько анкет показывать эту рекламу?")

    await callback.message.edit_text(
        text,
        reply_markup=kb.interval_choice_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer()

@router.callback_query(F.data == "ad_expires_back", AdminAdForm.waiting_custom_expires)
async def back_to_expires_choice(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору срока действия"""
    await state.set_state(AdminAdForm.waiting_expires_choice)

    data = await state.get_data()
    selected_regions = data.get('selected_regions', [])

    if 'all' in selected_regions:
        regions_text = "Все регионы"
    else:
        from config import settings
        region_names = []
        for region in selected_regions[:5]:
            region_names.append(settings.COUNTRIES_DICT.get(region, region))
        regions_text = ", ".join(region_names)
        if len(selected_regions) > 5:
            regions_text += f" и ещё {len(selected_regions) - 5}"

    text = (f"✅ Регионы выбраны: <b>{regions_text}</b>\n\n"
            f"<b>Шаг 6/7: Выберите срок действия</b>\n\n"
            f"Через сколько времени реклама автоматически удалится?")

    await callback.message.edit_text(
        text,
        reply_markup=kb.ad_expires_choice_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer()

@router.message(AdminAdForm.waiting_custom_expires, F.text)
async def process_custom_expires(message: Message, state: FSMContext):
    """Обработка ввода даты вручную"""
    from datetime import datetime

    date_text = message.text.strip()

    # Пробуем распарсить дату
    expires_at = None
    formats = [
        "%d.%m.%Y",           # 21.12.2025
        "%d.%m.%Y %H:%M",     # 21.12.2025 23:59
        "%d/%m/%Y",           # 21/12/2025
        "%d/%m/%Y %H:%M",     # 21/12/2025 23:59
    ]

    for date_format in formats:
        try:
            expires_at = datetime.strptime(date_text, date_format)
            break
        except ValueError:
            continue

    if not expires_at:
        await message.answer(
            "❌ <b>Неверный формат даты!</b>\n\n"
            "Используйте формат: <code>ДД.ММ.ГГГГ</code> или <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>21.12.2025</code>\n"
            "• <code>31.12.2025 23:59</code>\n\n"
            "Попробуйте ещё раз или нажмите 'Назад'",
            parse_mode='HTML'
        )
        return

    # Проверяем, что дата в будущем
    now = datetime.now()
    if expires_at <= now:
        await message.answer(
            "❌ <b>Дата должна быть в будущем!</b>\n\n"
            f"Вы указали: <code>{expires_at.strftime('%d.%m.%Y %H:%M')}</code>\n"
            f"Сейчас: <code>{now.strftime('%d.%m.%Y %H:%M')}</code>\n\n"
            "Попробуйте ещё раз или нажмите 'Назад'",
            parse_mode='HTML'
        )
        return

    # Проверяем, что дата не слишком далеко в будущем (например, не более 10 лет)
    from datetime import timedelta
    max_future = now + timedelta(days=3650)  # 10 лет
    if expires_at > max_future:
        await message.answer(
            "❌ <b>Дата слишком далеко в будущем!</b>\n\n"
            f"Максимум: <code>{max_future.strftime('%d.%m.%Y')}</code>\n\n"
            "Попробуйте ещё раз или нажмите 'Назад'",
            parse_mode='HTML'
        )
        return

    # Все проверки пройдены, сохраняем дату
    await state.update_data(expires_at=expires_at)
    await state.set_state(AdminAdForm.waiting_interval_choice)

    expires_text = expires_at.strftime('%d.%m.%Y %H:%M')
    days_until = (expires_at - now).days + 1

    text = (
        f"✅ Срок действия: <b>до {expires_text}</b>\n"
        f"   (через {days_until} {'день' if days_until == 1 else 'дня' if days_until < 5 else 'дней'})\n\n"
        f"<b>Шаг 7/7: Выберите интервал показа</b>\n\n"
        f"Через сколько анкет показывать эту рекламу?"
    )

    await message.answer(
        text,
        reply_markup=kb.interval_choice_keyboard(),
        parse_mode='HTML'
    )

# === КОНЕЦ ОБРАБОТЧИКОВ СРОКА ДЕЙСТВИЯ ===

@router.callback_query(F.data == "custom_interval", AdminAdForm.waiting_interval_choice)
async def request_custom_interval_new(callback: CallbackQuery, state: FSMContext):
    """Запрос ввода кастомного интервала при создании новой рекламы"""
    await state.set_state(AdminAdForm.waiting_custom_interval)

    text = (f"<b>Шаг 4/4: Интервал показа</b>\n\n"
            f"<b>Введите свой интервал показа:</b>\n"
            f"(число от 1 до 1000)")

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_custom_interval_new")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "cancel_custom_interval_new", AdminAdForm.waiting_custom_interval)
async def cancel_custom_interval_new(callback: CallbackQuery, state: FSMContext):
    """Отмена ввода кастомного интервала при создании"""
    await state.set_state(AdminAdForm.waiting_interval_choice)

    text = (f"<b>Шаг 4/4: Выберите интервал показа</b>\n\n"
            f"Через сколько анкет показывать этот пост?\n"
            f"(чем больше - тем реже показывается реклама)")

    await callback.message.edit_text(
        text,
        reply_markup=kb.interval_choice_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer("Отменено")

@router.message(AdminAdForm.waiting_custom_interval, F.text)
async def process_custom_interval(message: Message, state: FSMContext, db):
    """Обработка кастомного интервала (для создания новой или редактирования существующей рекламы)"""
    # Валидация ввода
    try:
        interval = int(message.text.strip())
        if interval < 1 or interval > 1000:
            await message.answer(
                "❌ Неверное значение!\n\n"
                "Интервал должен быть от 1 до 1000.\n"
                "Попробуйте ещё раз или нажмите 'Отмена'."
            )
            return
    except ValueError:
        await message.answer(
            "❌ Ошибка!\n\n"
            "Введите число от 1 до 1000.\n"
            "Попробуйте ещё раз или нажмите 'Отмена'."
        )
        return

    data = await state.get_data()
    editing_ad_id = data.get('editing_ad_id')

    # Если редактируем существующую рекламу
    if editing_ad_id:
        success = await db.update_ad_interval(editing_ad_id, interval)
        await state.clear()

        if success:
            ads = await db.get_all_ads()
            ad = next((a for a in ads if a['id'] == editing_ad_id), None)

            if not ad:
                await message.answer("❌ Ошибка: реклама не найдена")
                return

            status = "✅ Активна" if ad['is_active'] else "❌ Выключена"
            created = ad['created_at'].strftime("%d.%m.%Y %H:%M") if hasattr(ad['created_at'], 'strftime') else str(ad['created_at'])[:16]

            text = (f"📢 Рекламный пост <b>#{ad['id']}</b>\n\n"
                    f"<b>Название:</b> {ad['caption']}\n"
                    f"<b>Статус:</b> {status}\n"
                    f"<b>Интервал показа:</b> каждые {ad['show_interval']} анкет\n"
                    f"<b>Создан:</b> {created}\n\n"
                    f"<b>Управление:</b>")

            await message.answer(
                text,
                reply_markup=kb.admin_ad_actions(ad),
                parse_mode='HTML'
            )
            await message.answer(f"✅ Интервал изменён на {interval}")
        else:
            await message.answer("❌ Ошибка обновления интервала")
    else:
        # Создаём новую рекламу
        # Проверяем наличие необходимых данных
        if 'message_id' not in data or 'chat_id' not in data or 'caption' not in data:
            logger.error(f"Недостаточно данных в state для создания рекламы: {data.keys()}")
            await message.answer("❌ Ошибка: данные рекламы потеряны. Попробуйте создать рекламу заново.")
            await state.clear()
            return

        ad_id = await db.add_ad_post(
            message_id=data['message_id'],
            chat_id=data['chat_id'],
            caption=data['caption'],
            admin_id=message.from_user.id,
            show_interval=interval,
            games=data.get('games', ['dota', 'cs']),
            regions=data.get('selected_regions', ['all']),
            ad_type=data.get('ad_type', 'forward'),
            expires_at=data.get('expires_at')
        )

        await state.clear()

        games = data.get('games', ['dota', 'cs'])
        games_text = "обеих играх" if len(games) == 2 else ("Dota 2" if games[0] == "dota" else "CS2")

        # Формируем текст с регионами
        selected_regions = data.get('selected_regions', ['all'])
        if 'all' in selected_regions:
            regions_text = "Все регионы"
        else:
            from config import settings
            region_names = []
            for region in selected_regions[:3]:
                region_names.append(settings.COUNTRIES_DICT.get(region, region))
            regions_text = ", ".join(region_names)
            if len(selected_regions) > 3:
                regions_text += f" +{len(selected_regions) - 3}"

        text = (f"✅ Рекламный пост <b>#{ad_id}</b> создан!\n\n"
                f"<b>Название:</b> {data['caption']}\n"
                f"<b>Игры:</b> {games_text}\n"
                f"<b>Регионы:</b> {regions_text}\n"
                f"<b>Интервал:</b> каждые {interval} анкет\n\n"
                f"Пост автоматически активен и будет показываться пользователям.")

        await message.answer(
            text,
            reply_markup=kb.admin_back_menu(),
            parse_mode='HTML'
        )

@router.callback_query(F.data.startswith("interval_"), AdminAdForm.waiting_interval_choice)
async def select_interval_for_new_ad(callback: CallbackQuery, state: FSMContext, db):
    try:
        interval = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        await callback.answer("Ошибка", show_alert=True)
        return

    data = await state.get_data()

    # Проверяем наличие необходимых данных
    if 'message_id' not in data or 'chat_id' not in data or 'caption' not in data:
        logger.error(f"Недостаточно данных в state для создания рекламы: {data.keys()}")
        await callback.answer("❌ Ошибка: данные рекламы потеряны. Попробуйте создать рекламу заново.", show_alert=True)
        await state.clear()
        return

    ad_id = await db.add_ad_post(
        message_id=data['message_id'],
        chat_id=data['chat_id'],
        caption=data['caption'],
        admin_id=callback.from_user.id,
        show_interval=interval,
        games=data.get('games', ['dota', 'cs']),
        regions=data.get('selected_regions', ['all']),
        ad_type=data.get('ad_type', 'forward'),
        expires_at=data.get('expires_at')
    )

    await state.clear()

    games = data.get('games', ['dota', 'cs'])
    games_text = "обеих играх" if len(games) == 2 else ("Dota 2" if games[0] == "dota" else "CS2")

    # Формируем текст с регионами
    selected_regions = data.get('selected_regions', ['all'])
    if 'all' in selected_regions:
        regions_text = "Все регионы"
    else:
        from config import settings
        region_names = []
        for region in selected_regions[:3]:
            region_names.append(settings.COUNTRIES_DICT.get(region, region))
        regions_text = ", ".join(region_names)
        if len(selected_regions) > 3:
            regions_text += f" +{len(selected_regions) - 3}"

    text = (f"✅ Рекламный пост <b>#{ad_id}</b> создан!\n\n"
            f"<b>Название:</b> {data['caption']}\n"
            f"<b>Игры:</b> {games_text}\n"
            f"<b>Регионы:</b> {regions_text}\n"
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

# === ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ РЕГИОНОВ РЕКЛАМЫ ===

@router.callback_query(F.data.startswith("ad_regions_"))
@admin_only
async def start_edit_regions(callback: CallbackQuery, state: FSMContext, db):
    """Начало редактирования регионов для рекламы"""
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

    current_regions = ad.get('regions', ['all'])
    if not current_regions:
        current_regions = ['all']

    await state.update_data(editing_ad_id=ad_id, selected_regions=current_regions)
    await state.set_state(AdminAdForm.waiting_region_choice)

    # Формируем текст с текущими регионами
    if 'all' in current_regions:
        regions_text = "Все регионы"
    else:
        from config import settings
        region_names = []
        for region in current_regions[:5]:
            region_names.append(settings.COUNTRIES_DICT.get(region, region))
        regions_text = ", ".join(region_names)
        if len(current_regions) > 5:
            regions_text += f" и ещё {len(current_regions) - 5}"

    text = (f"📢 Пост <b>#{ad_id}</b>: {ad['caption']}\n\n"
            f"<b>Текущие регионы:</b> {regions_text}\n\n"
            f"<b>Выберите новые регионы для показа:</b>\n"
            f"Можно выбрать несколько или 'Все регионы'")

    await callback.message.edit_text(
        text,
        reply_markup=kb.ad_regions(selected_regions=current_regions, editing=True, ad_id=ad_id),
        parse_mode='HTML'
    )
    await callback.answer()

@router.callback_query(F.data.startswith("ad_region_save_"))
async def save_ad_regions(callback: CallbackQuery, state: FSMContext, db):
    """Сохранение выбранных регионов"""
    try:
        ad_id = int(callback.data.split("_")[3])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return

    data = await state.get_data()
    selected_regions = data.get('selected_regions', [])

    if not selected_regions:
        await callback.answer("Выберите хотя бы один регион!", show_alert=True)
        return

    success = await db.update_ad_regions(ad_id, selected_regions)
    await state.clear()

    if success:
        # Формируем текст с регионами для уведомления
        if 'all' in selected_regions:
            regions_text = "Все регионы"
        else:
            from config import settings
            region_names = []
            for region in selected_regions[:3]:
                region_names.append(settings.COUNTRIES_DICT.get(region, region))
            regions_text = ", ".join(region_names)
            if len(selected_regions) > 3:
                regions_text += f" +{len(selected_regions) - 3}"

        # Получаем обновленную рекламу из БД
        ads = await db.get_all_ads()
        ad = next((a for a in ads if a['id'] == ad_id), None)

        if not ad:
            await callback.answer("❌ Реклама не найдена", show_alert=True)
            return

        # Формируем информацию о рекламе
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
                f"<b>Регионы:</b> {regions_text}\n"
                f"<b>Статус:</b> {status}\n"
                f"<b>Интервал показа:</b> каждые {ad['show_interval']} анкет\n"
                f"<b>Создан:</b> {created}\n\n"
                f"<b>Управление:</b>")

        await callback.message.edit_text(
            text,
            reply_markup=kb.admin_ad_actions(ad),
            parse_mode='HTML'
        )
        await callback.answer(f"✅ Регионы обновлены")
    else:
        await callback.answer("❌ Ошибка обновления", show_alert=True)

# === КОНЕЦ ОБРАБОТЧИКОВ РЕДАКТИРОВАНИЯ РЕГИОНОВ ===

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

@router.callback_query(F.data.startswith("custom_interval_"), AdminAdForm.editing_interval)
async def request_custom_interval_edit(callback: CallbackQuery, state: FSMContext, db):
    """Запрос ввода кастомного интервала при редактировании"""
    try:
        ad_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return

    data = await state.get_data()
    if data.get('editing_ad_id') != ad_id:
        await callback.answer("Ошибка: несовпадение ID", show_alert=True)
        return

    ads = await db.get_all_ads()
    ad = next((a for a in ads if a['id'] == ad_id), None)

    if not ad:
        await callback.answer("Реклама не найдена", show_alert=True)
        return

    await state.set_state(AdminAdForm.waiting_custom_interval)

    text = (f"📢 Пост <b>#{ad_id}</b>: {ad['caption']}\n\n"
            f"<b>Текущий интервал:</b> каждые {ad['show_interval']} анкет\n\n"
            f"<b>Введите свой интервал показа:</b>\n"
            f"(число от 1 до 1000)")

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_custom_interval_{ad_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_custom_interval_"), AdminAdForm.waiting_custom_interval)
async def cancel_custom_interval_edit(callback: CallbackQuery, state: FSMContext, db):
    """Отмена ввода кастомного интервала"""
    try:
        ad_id = int(callback.data.split("_")[3])
    except (IndexError, ValueError):
        await callback.answer("Ошибка ID", show_alert=True)
        return

    await state.set_state(AdminAdForm.editing_interval)

    ads = await db.get_all_ads()
    ad = next((a for a in ads if a['id'] == ad_id), None)

    if not ad:
        await callback.answer("Реклама не найдена", show_alert=True)
        await state.clear()
        return

    text = (f"📢 Пост <b>#{ad_id}</b>: {ad['caption']}\n\n"
            f"<b>Текущий интервал:</b> каждые {ad['show_interval']} анкет\n\n"
            f"<b>Выберите новый интервал показа:</b>")

    await callback.message.edit_text(
        text,
        reply_markup=kb.interval_choice_keyboard(ad_id, current_interval=ad['show_interval']),
        parse_mode='HTML'
    )
    await callback.answer("Отменено")

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