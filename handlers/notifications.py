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
        self._max_concurrent = 10
        self._retry_count = 2
        
    async def add_notification(self, coro, description: str = "notification"):
        """Добавить уведомление в очередь для асинхронной обработки"""
        if len(self._active_tasks) >= self._max_concurrent:
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
                    await asyncio.sleep(0.5 * (attempt + 1)) 

_notification_queue = NotificationQueue()

# ==================== БАЗОВЫЕ ФУНКЦИИ ====================

async def get_user_interaction_state(user_id: int, db) -> str:
    """Определяем состояние взаимодействия пользователя"""
    try:
        cache_key = f"user_state:{user_id}"
        last_state = await db._redis.get(cache_key)
        
        busy_states = [
            'search_browsing',
            'profile_editing',
            'profile_creation',
            'search_setup'
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
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Понятно", callback_data="dismiss_notification")]
            ])
            notification_text = f"🔔 {text}"
            return await safe_send_notification(bot, user_id, notification_text, photo_id=None, keyboard=keyboard)
        else:
            if quick_actions:
                keyboard = kb.create_navigation_keyboard(quick_actions)
            else:
                keyboard = kb.create_navigation_keyboard([("Главное меню", "main_menu")])
            return await safe_send_notification(bot, user_id, text, photo_id=photo_id, keyboard=keyboard)

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

        # Обновляем Redis кэш (быстро)
        activity_key = f"last_activity:{user_id}"
        await db._redis.setex(activity_key, 300, str(current_time))  # 5 минут

        if state:
            state_key = f"user_state:{user_id}"
            await db._redis.setex(state_key, 300, state)  # 5 минут

        # Обновляем поле last_activity в PostgreSQL (для алгоритма подбора)
        await db.update_user_activity(user_id)

        # Реактивируем анкету если пользователь вернулся после деактивации
        await db.reactivate_profile(user_id)

    except Exception as e:
        logger.warning(f"Ошибка обновления активности пользователя {user_id}: {e}")

async def safe_send_notification(
    bot: Bot,
    user_id: int,
    text: str,
    photo_id: Optional[str] = None,
    keyboard: Optional[InlineKeyboardMarkup] = None,
    add_ok_button: bool = True
) -> bool:
    """Безопасная отправка уведомления пользователю"""
    try:
        # Если передана кастомная клавиатура, используем её
        # Иначе создаём стандартную кнопку "Понятно" если add_ok_button=True
        if keyboard is None:
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
    success = await safe_send_notification(bot, user_id, text, photo_id=photo_id, keyboard=keyboard)
    if success:
        logger.info(f"📨 Уведомление отправлено {user_id}")
    return success

# ==================== УВЕДОМЛЕНИЯ О МЭТЧАХ ====================

async def notify_about_match(bot: Bot, user_id: int, match_user_id: int, game: str, db) -> bool:
    """Уведомление о новом мэтче (упрощенное, как лайки)"""
    async def _notify():
        try:
            game_name = settings.GAMES.get(game, game)
            text = f"У вас новый мэтч в {game_name}! Зайдите в «Мэтчи», чтобы посмотреть контакты"

            current_user = await db.get_user(user_id)
            quick_actions = []

            if current_user and current_user.get('current_game') != game:
                quick_actions.append((f"Мэтчи в {game_name}", f"switch_and_matches_{game}"))
            else:
                quick_actions.append(("Мои мэтчи", "my_matches"))

            return await smart_notification(bot, user_id, text, quick_actions, None, db)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о мэтче: {e}")
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
            text = f"Кто-то лайкнул вашу анкету в {game_name}! Зайдите в «Лайки», чтобы посмотреть"

            current_user = await db.get_user(user_id)
            quick_actions = []

            if current_user and current_user.get('current_game') != actual_game:
                quick_actions.append((f"Лайки в {game_name}", f"switch_and_likes_{actual_game}"))
            else:
                quick_actions.append(("Посмотреть лайки", "my_likes"))

            quick_actions.append(("Понятно", "dismiss_notification"))

            return await smart_notification(bot, user_id, text, quick_actions, None, db)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о лайке: {e}")
            return False

    await _notification_queue.add_notification(_notify(), f"like notification to {user_id}")
    return True

# ==================== УВЕДОМЛЕНИЯ МОДЕРАЦИИ ====================

async def notify_profile_deleted(bot: Bot, user_id: int, game: str) -> bool:
    """Уведомление об удалении профиля модератором (умное)"""
    async def _notify():
        try:
            game_name = settings.GAMES.get(game, game)
            text = (f"Ваша анкета в {game_name} была удалена модератором за нарушение правил сообщества\n\n"
                    f"Вы можете создать новую анкету, соблюдая правила")

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
            text = (f"Вы заблокированы до {formatted_date} за нарушение правил сообщества\n\n"
                    f"Во время блокировки вы не можете использовать бота\n\n"
                    f"Если Вы не согласны с решением, обратитесь в поддержку")

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
            text = "Блокировка снята! Теперь вы можете снова пользоваться ботом"
            quick_actions = [("Главное меню", "main_menu")]
            return await smart_notification(bot, user_id, text, quick_actions, None, None)

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о снятии бана: {e}")
            return False

    await _notification_queue.add_notification(_notify(), f"unban notification to {user_id}")
    return True

# ==================== УВЕДОМЛЕНИЯ АДМИНА ====================

async def notify_admin_new_report(bot: Bot, reporter_id: int, reported_user_id: int, game: str) -> bool:
    """Уведомление всех админов о новой жалобе"""
    if not settings.ADMIN_IDS:
        return False

    try:
        game_name = settings.GAMES.get(game, game)
        text = (f"🚩 Новая жалоба!\n\n"
                f"Пользователь {reporter_id} пожаловался на анкету {reported_user_id} "
                f"в игре {game_name}")

        success_count = 0
        for admin_id in settings.ADMIN_IDS:
            success = await safe_send_notification(bot, admin_id, text, photo_id=None, add_ok_button=True)
            if success:
                success_count += 1

        if success_count > 0:
            logger.info(f"📨 Уведомление о жалобе отправлено {success_count} админам")
            return True
        else:
            logger.warning("Не удалось отправить уведомление ни одному админу")
            return False
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админам: {e}")
        return False
# ==================== СЛУЖЕБНЫЕ ФУНКЦИИ ====================

async def wait_all_notifications():
    """Дождаться завершения всех уведомлений (для graceful shutdown)"""
    if _notification_queue._active_tasks:
        logger.info(f"Ожидаем завершения {len(_notification_queue._active_tasks)} уведомлений...")
        await asyncio.gather(*_notification_queue._active_tasks, return_exceptions=True)
        logger.info("Все уведомления завершены")

async def notify_monthly_profile_reminder(bot: Bot, user_id: int, game: str, db) -> bool:
    """Ежемесячное напоминание об обновлении анкеты"""
    async def _notify():
        try:
            game_name = settings.GAMES.get(game, game)
            text = (f"🔄 Время обновить анкету!\n\n"
                    f"Ваша анкета в {game_name} не обновлялась больше месяца. "
                    f"Рекомендуем проверить актуальность информации:\n\n"
                    f"• Рейтинг\n• Позиции\n• Описание\n\n"
                    f"Актуальные анкеты показываются в поиске чаще!")

            quick_actions = [
                ("Редактировать анкету", "edit_profile"),
                ("Посмотреть анкету", "view_profile")
            ]

            return await smart_notification(bot, user_id, text, quick_actions, None, db)

        except Exception as e:
            logger.error(f"Ошибка отправки напоминания об обновлении: {e}")
            return False

    await _notification_queue.add_notification(_notify(), f"monthly reminder to {user_id}")
    return True