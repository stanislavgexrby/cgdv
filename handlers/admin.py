import logging
import contextlib
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings
from handlers.basic import admin_only, safe_edit_message
from handlers.notifications import notify_user_banned, notify_user_unbanned, notify_profile_deleted

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

# ==================== ГЛАВНОЕ МЕНЮ АДМИНКИ ====================

@router.callback_query(F.data == "admin_back")
@admin_only
async def admin_main_menu(callback: CallbackQuery):
    """Главное меню админ панели"""
    await safe_edit_message(callback, "👑 Админ панель", kb.admin_main_menu())
    await callback.answer()

# ==================== СТАТИСТИКА ====================

@router.callback_query(F.data == "admin_stats")
@admin_only
async def show_admin_stats(callback: CallbackQuery, db):
    """Показ статистики бота"""
    lines = ["📊 Статистика бота", "", "🗄 База данных: PostgreSQL"]

    # Redis статус
    try:
        if hasattr(db, '_redis'):
            pong = await db._redis.ping()
            lines.append(f"⚡ Redis: {'✅ OK' if pong else '❌ Недоступен'}")
        else:
            lines.append("⚡ Redis: ❌ Не подключен")
    except Exception:
        lines.append("⚡ Redis: ❌ Ошибка")

    # Проверка подключения к PostgreSQL
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

    await _show_report(callback, reports[0], db)

async def _show_report(callback: CallbackQuery, report: dict, db):
    """Показ отдельной жалобы"""
    report_id = report['id']
    reported_user_id = report['reported_user_id']
    game = report.get('game', 'dota')
    
    # Получаем профиль нарушителя
    profile = await db.get_user_profile(reported_user_id, game)
    game_name = settings.GAMES.get(game, game)
    
    # Формируем текст
    header = (
        f"🚩 Жалоба #{report_id} | {game_name}\n"
        f"📅 Дата: {_format_datetime(report.get('created_at'))}\n"
        f"👤 Жалобщик: {report['reporter_id']}\n"
        f"🎯 На пользователя: {reported_user_id}\n"
        f"📋 Причина: {report.get('report_reason', 'inappropriate_content')}\n"
    )
    
    if profile:
        body = "\n👤 Анкета нарушителя:\n\n" + texts.format_profile(profile, show_contact=True)
    else:
        body = f"\n❌ Анкета пользователя {reported_user_id} не найдена"
    
    text = _truncate_text(header + body)
    keyboard = kb.admin_report_actions(reported_user_id, report_id)
    
    # Отправляем с фото если есть
    photo_id = profile.get('photo_id') if profile else None
    
    try:
        if photo_id:
            media = InputMediaPhoto(media=photo_id, caption=text)
            await callback.message.edit_media(media=media, reply_markup=keyboard)
        else:
            await safe_edit_message(callback, text, keyboard)
    except Exception:
        # Fallback для случаев несовместимости типов сообщений
        try:
            if photo_id:
                await callback.message.delete()
                await callback.message.answer_photo(photo_id, caption=text, reply_markup=keyboard)
            else:
                await safe_edit_message(callback, text, keyboard)
        except Exception as e:
            logger.error(f"Ошибка показа жалобы: {e}")
            await safe_edit_message(callback, text, keyboard)
    
    await callback.answer()

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
        # Отправляем уведомление пользователю
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

async def unban_user(callback: CallbackQuery, db):
    """Снятие бана"""
    try:
        user_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    success = await db.unban_user(user_id)
    
    if success:
        notify_user_unbanned(callback.bot, user_id)
        logger.info(f"Админ снял бан с пользователя {user_id}")
        await callback.answer("Бан снят")
        
        bans = await db.get_all_bans()
        if not bans:
            text = "Бан снят!\n\nБольше активных банов нет."
            await safe_edit_message(callback, text, kb.admin_back_menu())
        else:
            await _show_ban(callback, bans[0], 0, len(bans))
    else:
        await callback.answer("❌ Ошибка снятия бана", show_alert=True)

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
    
    await _show_report(callback, reports[0], db)

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
        # Отправляем уведомление пользователю
        await notify_user_unbanned(callback.bot, user_id)
        logger.info(f"Админ снял бан с пользователя {user_id}")
        
        # Проверяем есть ли еще баны для показа
        bans = await db.get_all_bans()
        if not bans:
            text = "✅ Бан снят!\n\nБольше активных банов нет."
            await safe_edit_message(callback, text, kb.admin_back_menu())
        else:
            # Показываем первый бан из оставшихся
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