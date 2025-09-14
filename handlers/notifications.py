import asyncio
import logging
from typing import Optional, List, Tuple, Dict, Any
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from datetime import datetime

import utils.texts as texts
import config.settings as settings
import keyboards.keyboards as kb

logger = logging.getLogger(__name__)

# ==================== АСИНХРОННАЯ ОЧЕРЕДЬ УВЕДОМЛЕНИЙ ====================

class NotificationQueue:
    """Асинхронная очередь для неблокирующей отправки уведомлений"""
    
    def __init__(self):
        self._active_tasks = set()
        self._max_concurrent = 10  # Максимум одновременных уведомлений
        self._retry_count = 2
        
    async def add_notification(self, coro, description: str = "notification"):
        """Добавить уведомление в очередь для асинхронной обработки"""
        if len(self._active_tasks) >= self._max_concurrent:
            # Ждем освобождения слота
            if self._active_tasks:
                done, pending = await asyncio.wait(
                    self._active_tasks, 
                    return_when=asyncio.FIRST_COMPLETED
                )
                self._active_tasks -= done
        
        task = asyncio.create_task(self._safe_execute(coro, description))
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)
    
    async def _safe_execute(self, coro, description: str):
        """Безопасное выполнение корутины с повторными попытками"""
        for attempt in range(self._retry_count + 1):
            try:
                await coro
                return
            except Exception as e:
                logger.warning(f"Ошибка {description} (попытка {attempt + 1}): {e}")
                if attempt < self._retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Экспоненциальная задержка

# Глобальная очередь уведомлений
_notification_queue = NotificationQueue()

# ==================== БАЗОВЫЕ ФУНКЦИИ ====================

async def safe_send_notification(
    bot: Bot,
    user_id: int,
    text: str,
    photo_id: Optional[str] = None,
    keyboard: Optional[InlineKeyboardMarkup] = None
) -> bool:
    """Безопасная отправка уведомления пользователю"""
    try:
        if photo_id:
            await bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=text,
                reply_markup=keyboard, 
                parse_mode= 'HTML'
            )
        else:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard, 
                parse_mode= 'HTML'
            )
        return True
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
        return False

async def _send_notification_internal(
    bot: Bot,
    user_id: int, 
    text: str,
    photo_id: Optional[str] = None,
    keyboard: Optional[InlineKeyboardMarkup] = None
):
    """Внутренняя функция для отправки уведомления"""
    success = await safe_send_notification(bot, user_id, text, photo_id, keyboard)
    if success:
        logger.info(f"📨 Уведомление отправлено {user_id}")
    return success

# ==================== УВЕДОМЛЕНИЯ О МАТЧАХ ====================

async def notify_about_match(bot: Bot, user_id: int, match_user_id: int, game: str, db) -> bool:
    """Уведомление о новом матче (асинхронное)"""
    async def _notify():
        try:
            match_profile = await db.get_user_profile(match_user_id, game)
            game_name = settings.GAMES.get(game, game)

            if not match_profile:
                text = f"У вас новый мэтч в {game_name}!"
                return await _send_notification_internal(bot, user_id, text)

            profile_text = texts.format_profile(match_profile, show_contact=True)
            text = f"У вас новый мэтч в {game_name}!\n\n{profile_text}"

            current_user = await db.get_user(user_id)
            buttons: List[Tuple[str, str]] = []
            if current_user and current_user.get('current_game') != game:
                buttons.append((f"Перейти к мэтчам в {game_name}", f"switch_and_matches_{game}"))
            else:
                buttons.append(("Мои мэтчи", "my_matches"))
            buttons.append(("Главное меню", "main_menu"))

            keyboard = kb.create_navigation_keyboard(buttons)
            return await _send_notification_internal(
                bot, user_id, text, match_profile.get('photo_id'), keyboard
            )

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о матче: {e}")
            return False

    # Добавляем в очередь для асинхронной обработки
    await _notification_queue.add_notification(
        _notify(), 
        f"match notification to {user_id}"
    )
    return True  # Возвращаем True, так как задача поставлена в очередь

# ==================== УВЕДОМЛЕНИЯ О ЛАЙКАХ ====================

async def notify_about_like(bot: Bot, user_id: int, game: str, db=None) -> bool:
    """Уведомление о новом лайке (асинхронное)"""
    async def _notify():
        try:
            if db is None:
                logger.error("db parameter is required for notify_about_like")
                return False

            if not game:
                user = await db.get_user(user_id)
                actual_game = user.get('current_game', 'dota') if user else 'dota'
            else:
                actual_game = game

            game_name = settings.GAMES.get(actual_game, actual_game)
            text = f"Кто-то лайкнул вашу анкету в {game_name}! Зайдите в «Лайки», чтобы посмотреть."

            keyboard = kb.create_navigation_keyboard([
                ("Посмотреть лайки", "my_likes"),
                ("Главное меню", "main_menu"),
            ])

            return await _send_notification_internal(bot, user_id, text, None, keyboard)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о лайке: {e}")
            return False

    # Добавляем в очередь для асинхронной обработки
    await _notification_queue.add_notification(
        _notify(), 
        f"like notification to {user_id}"
    )
    return True

# ==================== УВЕДОМЛЕНИЯ МОДЕРАЦИИ ====================

async def notify_profile_deleted(bot: Bot, user_id: int, game: str) -> bool:
    """Уведомление об удалении профиля модератором (асинхронное)"""
    async def _notify():
        try:
            game_name = settings.GAMES.get(game, game)
            text = (f"Ваша анкета в {game_name} была удалена модератором\n\n"
                    f"Причина: нарушение правил сообщества\n\n"
                    f"Что можно сделать:\n"
                    f"• Создать новую анкету\n"
                    f"• Соблюдать правила сообщества\n"
                    f"• Быть вежливыми с другими игроками")

            keyboard = kb.create_navigation_keyboard([
                ("Создать новую анкету", "create_profile"),
                ("Главное меню", "main_menu"),
            ])

            return await _send_notification_internal(bot, user_id, text, None, keyboard)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об удалении профиля: {e}")
            return False

    # Добавляем в очередь для асинхронной обработки
    await _notification_queue.add_notification(
        _notify(), 
        f"profile deleted notification to {user_id}"
    )
    return True

async def notify_user_banned(bot: Bot, user_id: int, expires_at: datetime) -> bool:
    """Уведомление о бане пользователя (асинхронное)"""
    async def _notify():
        try:
            formatted_date = expires_at.strftime("%d.%m.%Y %H:%M (UTC)")

            text = (f"Вы заблокированы до {formatted_date} за нарушение правил сообщества.\n\n"
                    f"Во время блокировки вы не можете:\n"
                    f"• Создавать анкеты\n"
                    f"• Искать игроков\n"
                    f"• Ставить лайки\n"
                    f"• Просматривать лайки и мэтчи")
            return await _send_notification_internal(bot, user_id, text)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о бане: {e}")
            return False

    await _notification_queue.add_notification(
        _notify(),
        f"ban notification to {user_id}"
    )
    return True

async def notify_user_unbanned(bot: Bot, user_id: int) -> bool:
    """Уведомление о снятии бана (асинхронное)"""
    async def _notify():
        try:
            text = "Блокировка снята! Теперь вы можете снова пользоваться ботом."
            keyboard = kb.create_navigation_keyboard([("Главное меню", "main_menu")])
            return await _send_notification_internal(bot, user_id, text, None, keyboard)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о снятии бана: {e}")
            return False

    await _notification_queue.add_notification(
        _notify(),
        f"unban notification to {user_id}"
    )
    return True

# ==================== УВЕДОМЛЕНИЯ АДМИНА ====================

async def notify_admin_new_report(bot: Bot, reporter_id: int, reported_user_id: int, game: str) -> bool:
    """Уведомление админа о новой жалобе (синхронное - важно для админа)"""
    if not settings.ADMIN_ID or settings.ADMIN_ID == 0:
        return False
    
    try:
        game_name = settings.GAMES.get(game, game)
        text = (f"🚩 Новая жалоба!\n\n"
                f"Пользователь {reporter_id} пожаловался на анкету {reported_user_id} "
                f"в игре {game_name}")
        success = await safe_send_notification(bot, settings.ADMIN_ID, text)
        if success:
            logger.info("📨 Уведомление админу о жалобе отправлено")
        return success
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")
        return False

# ==================== СЛУЖЕБНЫЕ ФУНКЦИИ ====================

async def get_notification_stats() -> Dict[str, Any]:
    """Получить статистику очереди уведомлений"""
    return {
        "active_notifications": len(_notification_queue._active_tasks),
        "max_concurrent": _notification_queue._max_concurrent
    }

async def wait_all_notifications():
    """Дождаться завершения всех уведомлений (для graceful shutdown)"""
    if _notification_queue._active_tasks:
        logger.info(f"Ожидаем завершения {len(_notification_queue._active_tasks)} уведомлений...")
        await asyncio.gather(*_notification_queue._active_tasks, return_exceptions=True)
        logger.info("Все уведомления завершены")