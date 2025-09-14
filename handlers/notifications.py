import asyncio
import logging
from typing import Optional, List, Tuple, Dict, Any
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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

async def get_user_interaction_state(user_id: int, db) -> str:
    """Определяем состояние взаимодействия пользователя"""
    try:
        cache_key = f"user_state:{user_id}"
        last_state = await db._redis.get(cache_key)
        
        busy_states = [
            'search_browsing',     # Просматривает анкеты
            'profile_editing',     # Редактирует профиль
            'profile_creation',    # Создает профиль
            'search_setup'         # Настраивает фильтры поиска
        ]
        
        if last_state in busy_states:
            return 'busy'
        
        return 'available'
        
    except Exception as e:
        logger.warning(f"Ошибка определения состояния пользователя {user_id}: {e}")
        return 'available'

async def smart_notification(bot: Bot, user_id: int, text: str, 
                           quick_actions: List[Tuple[str, str]] = None, 
                           photo_id: Optional[str] = None, db=None):
    """Умное уведомление в зависимости от состояния пользователя"""
    try:
        user_state = await get_user_interaction_state(user_id, db) if db else 'available'
        
        if user_state == 'busy':
            # Простое текстовое уведомление без кнопок действий
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Понятно", callback_data="dismiss_notification")]
            ])
            notification_text = f"🔔 {text}"
            return await safe_send_notification(bot, user_id, notification_text, None, keyboard)
        else:
            # Полное уведомление с быстрыми действиями
            if quick_actions:
                keyboard = kb.create_navigation_keyboard(quick_actions)
            else:
                keyboard = kb.create_navigation_keyboard([("Главное меню", "main_menu")])
            return await safe_send_notification(bot, user_id, text, photo_id, keyboard)
            
    except Exception as e:
        logger.error(f"Ошибка отправки умного уведомления: {e}")
        return False

async def update_user_activity(user_id: int, state: str = None, db=None):
    """Обновляем активность и состояние пользователя"""
    if not db:
        return
        
    try:
        import time
        current_time = time.time()
        
        # Обновляем время последней активности
        activity_key = f"last_activity:{user_id}"
        await db._redis.setex(activity_key, 300, str(current_time))  # 5 минут
        
        # Обновляем состояние если передано
        if state:
            state_key = f"user_state:{user_id}"
            await db._redis.setex(state_key, 300, state)  # 5 минут
            
    except Exception as e:
        logger.warning(f"Ошибка обновления активности пользователя {user_id}: {e}")

async def safe_send_notification(
    bot: Bot,
    user_id: int,
    text: str,
    photo_id: Optional[str] = None,
    add_ok_button: bool = True
) -> bool:
    """Безопасная отправка уведомления пользователю"""
    try:
        keyboard = kb.notification_ok() if add_ok_button else None

        if photo_id:
            await bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=text,
                reply_markup=keyboard, 
                parse_mode='HTML'
            )
        else:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboard, 
                parse_mode='HTML'
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
    """Уведомление о новом матче (упрощенное, как лайки)"""
    async def _notify():
        try:
            game_name = settings.GAMES.get(game, game)
            text = f"У вас новый мэтч в {game_name}! Зайдите в «Мэтчи», чтобы посмотреть контакты."

            current_user = await db.get_user(user_id)
            quick_actions = []

            if current_user and current_user.get('current_game') != game:
                quick_actions.append((f"Мэтчи в {game_name}", f"switch_and_matches_{game}"))
            else:
                quick_actions.append(("Мои мэтчи", "my_matches"))

            return await smart_notification(bot, user_id, text, quick_actions, None, db)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о матче: {e}")
            return False

    await _notification_queue.add_notification(_notify(), f"match notification to {user_id}")
    return True

# ==================== УВЕДОМЛЕНИЯ О ЛАЙКАХ ====================

async def notify_about_like(bot: Bot, user_id: int, game: str, db=None) -> bool:
    """Уведомление о новом лайке (умное)"""
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

            current_user = await db.get_user(user_id)
            quick_actions = []

            if current_user and current_user.get('current_game') != actual_game:
                quick_actions.append((f"Лайки в {game_name}", f"switch_and_likes_{actual_game}"))
            else:
                quick_actions.append(("Посмотреть лайки", "my_likes"))

            return await smart_notification(bot, user_id, text, quick_actions, None, db)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о лайке: {e}")
            return False

    await _notification_queue.add_notification(_notify(), f"like notification to {user_id}")
    return True

# ==================== УВЕДОМЛЕНИЯ МОДЕРАЦИИ ====================

# Обновляем notify_profile_deleted, notify_user_banned, notify_user_unbanned
# Заменяем их на использование smart_notification:

async def notify_profile_deleted(bot: Bot, user_id: int, game: str) -> bool:
    """Уведомление об удалении профиля модератором (умное)"""
    async def _notify():
        try:
            game_name = settings.GAMES.get(game, game)
            text = (f"Ваша анкета в {game_name} была удалена модератором за нарушение правил сообщества.\n\n"
                    f"Вы можете создать новую анкету, соблюдая правила.")

            quick_actions = [
                ("Создать новую анкету", "create_profile"),
                ("Главное меню", "main_menu"),
            ]

            return await smart_notification(bot, user_id, text, quick_actions, None, None)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об удалении профиля: {e}")
            return False

    await _notification_queue.add_notification(_notify(), f"profile deleted notification to {user_id}")
    return True

async def notify_user_banned(bot: Bot, user_id: int, expires_at: datetime) -> bool:
    """Уведомление о бане пользователя (умное)"""
    async def _notify():
        try:
            formatted_date = expires_at.strftime("%d.%m.%Y %H:%M (UTC)")
            text = (f"Вы заблокированы до {formatted_date} за нарушение правил сообщества.\n\n"
                    f"Во время блокировки вы не можете использовать бота.")
            
            # Для банов не даем быстрых действий
            return await smart_notification(bot, user_id, text, None, None, None)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о бане: {e}")
            return False

    await _notification_queue.add_notification(_notify(), f"ban notification to {user_id}")
    return True

async def notify_user_unbanned(bot: Bot, user_id: int) -> bool:
    """Уведомление о снятии бана (умное)"""
    async def _notify():
        try:
            text = "Блокировка снята! Теперь вы можете снова пользоваться ботом."
            quick_actions = [("Главное меню", "main_menu")]
            return await smart_notification(bot, user_id, text, quick_actions, None, None)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о снятии бана: {e}")
            return False

    await _notification_queue.add_notification(_notify(), f"unban notification to {user_id}")
    return True

# ==================== УВЕДОМЛЕНИЯ АДМИНА ====================

async def notify_admin_new_report(bot: Bot, reporter_id: int, reported_user_id: int, game: str) -> bool:
    """Уведомление админа о новой жалобе"""
    if not settings.ADMIN_ID or settings.ADMIN_ID == 0:
        return False

    try:
        game_name = settings.GAMES.get(game, game)
        text = (f"🚩 Новая жалоба!\n\n"
                f"Пользователь {reporter_id} пожаловался на анкету {reported_user_id} "
                f"в игре {game_name}")
        # Админские уведомления без кнопки OK
        success = await safe_send_notification(bot, settings.ADMIN_ID, text, add_ok_button=False)
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