import logging
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

from handlers.basic import check_ban_and_profile, safe_edit_message, _format_expire_date
from handlers.notifications import notify_about_match, notify_admin_new_report

logger = logging.getLogger(__name__)
router = Router()

# ==================== FSM СОСТОЯНИЯ ====================

class LikesForm(StatesGroup):
    waiting_report_message = State()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def show_profile_with_photo(callback: CallbackQuery, profile: dict, text: str, keyboard):
    """Универсальная функция показа профиля с фото или без"""
    try:
        if profile.get('photo_id'):
            try:
                await callback.message.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение: {e}")

            try:
                await callback.message.answer_photo(
                    photo=profile['photo_id'],
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            except Exception as photo_error:
                if "wrong file identifier" in str(photo_error) or "file not found" in str(photo_error):
                    logger.warning(f"Невалидный photo_id для пользователя {profile.get('telegram_id')}: {photo_error}")
                    await callback.message.answer(
                        text=text,
                        reply_markup=keyboard,
                        parse_mode='HTML',
                        disable_web_page_preview=True
                    )
                else:
                    raise photo_error
        else:
            await safe_edit_message(callback, text, keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа профиля с фото: {e}")
        try:
            await safe_edit_message(callback, text, keyboard)
            await callback.answer()
        except Exception as e2:
            logger.error(f"Критическая ошибка показа профиля: {e2}")
            await callback.answer("Ошибка загрузки")

async def show_empty_state(callback: CallbackQuery, message: str):
    """Показ пустого состояния (нет лайков/матчей)"""
    await safe_edit_message(callback, message, kb.back())
    await callback.answer()

async def process_like_action(callback: CallbackQuery, target_user_id: int, action: str, current_index: int = 0, db=None):
    if db is None:
        raise RuntimeError("db is required")

    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    if action == "like":
        is_match = await db.add_like(user_id, target_user_id, game, message=None)

        if is_match:
            await handle_match_created(callback, target_user_id, game, db)
        else:
            await show_next_like_or_finish(callback, user_id, game, db)

    elif action == "skip":
        await db.skip_like(user_id, target_user_id, game)
        await show_next_like_or_finish(callback, user_id, game, db)

async def handle_match_created(callback: CallbackQuery, target_user_id: int, game: str, db):
    """Обработка создания матча"""
    user_id = callback.from_user.id
    await notify_about_match(callback.bot, target_user_id, user_id, game, db)

    target_profile = await db.get_user_profile(target_user_id, game)

    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text="Другие лайки", callback_data="my_likes")],
        [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

    if target_profile:
        match_text = texts.format_profile(target_profile, show_contact=True)
        text = f"{texts.MATCH_CREATED}\n\n{match_text}"

        await show_profile_with_photo(callback, target_profile, text, keyboard)
    else:
        text = f"{texts.MATCH_CREATED}\n\nПользователь не найден"
        await safe_edit_message(callback, text, keyboard)
        await callback.answer()

    logger.info(f"Взаимный лайк: {callback.from_user.id} <-> {target_user_id}")

async def show_next_like_or_finish(callback: CallbackQuery, user_id: int, game: str, db):
    """Показ следующего лайка или завершение просмотра"""
    likes = await db.get_likes_for_user(user_id, game)

    if likes:
        await show_like_profile(callback, likes, 0)
    else:
        text = "Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые"
        await safe_edit_message(callback, text, kb.back())

async def _send_new_like_profile(message, likes: list, index: int):
    """Отправка нового сообщения с профилем лайка (для уведомлений)"""
    if index >= len(likes):
        text = "Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые"
        sent_msg = await message.answer(text, reply_markup=kb.back(), parse_mode='HTML')
        return sent_msg.message_id

    profile = likes[index]
    profile_text = texts.format_profile(profile)
    text = f"Этот игрок лайкнул вас:\n\n{profile_text}"

    like_message = profile.get('message')
    if like_message:
        # Экранируем сообщение пользователя
        escaped_message = html.escape(like_message)
        text += f"\n\n💬 <i>Сообщение: «{escaped_message}»</i>"

    total = len(likes)
    counter_text = f"Лайк {index + 1} из {total}"
    text = f"{counter_text}\n\n{text}"

    keyboard = kb.like_actions(profile['telegram_id'], index, total)

    sent_msg = None
    if profile.get('photo_id'):
        try:
            sent_msg = await message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото: {e}")
            sent_msg = await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        sent_msg = await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

    return sent_msg.message_id if sent_msg else None

async def show_like_profile(callback: CallbackQuery, likes: list, index: int):
    """Показ профиля в лайках"""
    if index >= len(likes):
        text = "Все лайки просмотрены!\n\nЗайдите позже, возможно появятся новые"
        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    profile = likes[index]
    profile_text = texts.format_profile(profile)
    text = f"Этот игрок лайкнул вас:\n\n{profile_text}"

    if profile.get('message'):
        # Экранируем сообщение пользователя
        escaped_message = html.escape(profile['message'])
        text += f"\n💌 Сообщение:\n\"{escaped_message}\""

    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [
            kb.InlineKeyboardButton(text="❤️", callback_data=f"loves_back_{profile['telegram_id']}_{index}"),
            kb.InlineKeyboardButton(text="👎", callback_data=f"loves_skip_{profile['telegram_id']}_{index}")
        ],
        [kb.InlineKeyboardButton(text="Пожаловаться", callback_data=f"loves_report_{profile['telegram_id']}_{index}")],
        [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

    await show_profile_with_photo(callback, profile, text, keyboard)

async def _save_last_menu_message(user_id: int, message_id: int, db):
    """Сохранение ID последнего сообщения меню в Redis"""
    try:
        key = f"last_menu_msg:{user_id}"
        await db._redis.setex(key, 3600, str(message_id))
    except Exception as e:
        logger.warning(f"Не удалось сохранить last_menu_message: {e}")

async def _get_last_menu_message(user_id: int, db) -> int:
    """Получение ID последнего сообщения меню из Redis"""
    try:
        key = f"last_menu_msg:{user_id}"
        value = await db._redis.get(key)
        if value:
            return int(value)
    except Exception as e:
        logger.warning(f"Не удалось получить last_menu_message: {e}")
    return None

async def _delete_last_menu_message(user_id: int, bot, db):
    """Удаление последнего сообщения меню"""
    try:
        message_id = await _get_last_menu_message(user_id, db)
        if message_id:
            try:
                await bot.delete_message(chat_id=user_id, message_id=message_id)
                logger.info(f"Удалено предыдущее меню: {message_id}")
            except Exception as e:
                logger.warning(f"Не удалось удалить предыдущее меню {message_id}: {e}")
    except Exception as e:
        logger.warning(f"Ошибка удаления последнего меню: {e}")

async def _is_notification_message(callback: CallbackQuery) -> bool:
    """Проверка, является ли сообщение уведомлением"""
    try:
        message_text = callback.message.text or callback.message.caption or ""
        notification_keywords = ["лайкнул вашу анкету", "🔔"]
        return any(keyword in message_text for keyword in notification_keywords)
    except:
        return False

async def _show_likes_internal(callback: CallbackQuery, user_id: int, game: str, state: FSMContext, db, delete_current: bool = False):
    """Внутренняя функция показа лайков"""
    await state.clear()

    likes = await db.get_likes_for_user(user_id, game)

    if delete_current:
        await _delete_last_menu_message(user_id, callback.bot, db)

        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить уведомление: {e}")

    if not likes:
        game_name = settings.GAMES.get(game, game)
        text = f"Пока никто не лайкнул вашу анкету в {game_name}\n\n"
        text += "Попробуйте:\n"
        text += "• Улучшить анкету\n"
        text += "• Добавить фото\n"
        text += "• Быть активнее в поиске"

        if delete_current:
            sent_msg = await callback.message.answer(text, reply_markup=kb.back(), parse_mode='HTML')
            await _save_last_menu_message(user_id, sent_msg.message_id, db)
        else:
            await show_empty_state(callback, text)
        return

    if delete_current:
        new_message_id = await _send_new_like_profile(callback.message, likes, 0)
        if new_message_id:
            await _save_last_menu_message(user_id, new_message_id, db)
    else:
        await show_like_profile(callback, likes, 0)

MATCHES_PAGE_SIZE = 8

async def _show_matches_internal(callback: CallbackQuery, user_id: int, game: str, state: FSMContext, db, page: int = 0):
    """Внутренняя функция показа матчей с пагинацией"""
    await state.clear()

    matches = await db.get_matches(user_id, game)
    game_name = settings.GAMES.get(game, game)

    if not matches:
        text = f"У вас пока нет мэтчей в {game_name}\n\n"
        text += "Чтобы получить мэтчи:\n"
        text += "• Лайкайте анкеты в поиске\n"
        text += "• Отвечайте на лайки других игроков"

        await show_empty_state(callback, text)
        return

    total = len(matches)
    total_pages = (total + MATCHES_PAGE_SIZE - 1) // MATCHES_PAGE_SIZE
    page = max(0, min(page, total_pages - 1))

    page_matches = matches[page * MATCHES_PAGE_SIZE:(page + 1) * MATCHES_PAGE_SIZE]
    start_num = page * MATCHES_PAGE_SIZE + 1

    text = f"Ваши мэтчи в {game_name} ({total}):\n\n"
    for i, match in enumerate(page_matches, start_num):
        name = match['name']
        username = match.get('username')
        username_text = f"@{username}" if username else "нет username"
        text += f"{i}. {name} ({username_text})\n"

    if total_pages > 1:
        text += f"\nСтраница {page + 1} из {total_pages}"

    buttons = []
    for match in page_matches:
        name = match['name'][:20] + "..." if len(match['name']) > 20 else match['name']
        buttons.append([kb.InlineKeyboardButton(
            text=name,
            callback_data=f"contact_{match['telegram_id']}_{page}"
        )])

    nav_row = []
    if page > 0:
        nav_row.append(kb.InlineKeyboardButton(text="←", callback_data=f"my_matches_page_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(kb.InlineKeyboardButton(text="→", callback_data=f"my_matches_page_{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")])
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=buttons)

    await safe_edit_message(callback, text, keyboard)

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "my_likes")
@check_ban_and_profile()
async def show_my_likes(callback: CallbackQuery, state: FSMContext, db):
    """Показ входящих лайков"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    is_notification = await _is_notification_message(callback)

    await _show_likes_internal(callback, user_id, game, state, db, delete_current=is_notification)

    if not is_notification:
        await callback.answer()

@router.callback_query(F.data == "my_matches")
@check_ban_and_profile()
async def show_my_matches(callback: CallbackQuery, state: FSMContext, db):
    """Показ матчей пользователя"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    await _show_matches_internal(callback, user_id, game, state, db, page=0)
    await callback.answer()

@router.callback_query(F.data.startswith("my_matches_page_"))
@check_ban_and_profile()
async def show_matches_page(callback: CallbackQuery, state: FSMContext, db):
    """Пагинация мэтчей"""
    try:
        page = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 0

    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    await _show_matches_internal(callback, user_id, game, state, db, page=page)
    await callback.answer()

@router.callback_query(F.data.startswith("switch_and_likes_"))
async def switch_and_show_likes(callback: CallbackQuery, state: FSMContext, db):
    try:
        parts = callback.data.split("_")
        if len(parts) < 4 or not parts[3]:
            raise ValueError("Неполные данные")

        game = parts[3]
        if game not in settings.GAMES:
            raise ValueError(f"Неверная игра: {game}")
        user_id = callback.from_user.id

        if game not in settings.GAMES:
            logger.error(f"Неверная игра в callback: {game}")
            await callback.answer("Неверная игра", show_alert=True)
            return

        logger.info(f"Переключение на игру {game} для показа лайков пользователя {user_id}")

        if not await db.switch_game(user_id, game):
            await callback.answer("Ошибка переключения игры", show_alert=True)
            return

        if await db.is_user_banned(user_id):
            ban_info = await db.get_user_ban(user_id)
            game_name = settings.GAMES.get(game, game)
            text = f"Вы заблокированы в {game_name}"
            if ban_info:
                expires_at = ban_info['expires_at']
                ban_end = _format_expire_date(expires_at)
                text += f" до {ban_end}"

            is_notification = await _is_notification_message(callback)
            if is_notification:
                await _delete_last_menu_message(user_id, callback.bot, db)
                try:
                    await callback.message.delete()
                except:
                    pass
                sent_msg = await callback.message.answer(text, reply_markup=kb.back(), parse_mode='HTML')
                await _save_last_menu_message(user_id, sent_msg.message_id, db)
            else:
                await safe_edit_message(callback, text, kb.back())
                await callback.answer()
            return

        profile = await db.get_user_profile(user_id, game)
        if not profile:
            game_name = settings.GAMES.get(game, game)
            await callback.answer(f"Сначала создайте анкету для {game_name}", show_alert=True)
            return

        is_notification = await _is_notification_message(callback)

        from handlers.likes import _show_likes_internal
        await _show_likes_internal(callback, user_id, game, state, db, delete_current=is_notification)

        if not is_notification:
            await callback.answer(f"Переключено на {settings.GAMES.get(game, game)}")

    except (ValueError, IndexError) as e:
        logger.error(f"Некорректный callback: {callback.data}, ошибка: {e}")
        await callback.answer("Ошибка обработки данных", show_alert=True)
        return

@router.callback_query(F.data.startswith("switch_and_matches_"))
async def switch_and_show_matches(callback: CallbackQuery, state: FSMContext, db):
    """Переключение игры и показ матчей из уведомления"""
    parts = callback.data.split("_")

    if len(parts) < 4:
        logger.error(f"Неверный формат callback_data: {callback.data}")
        await callback.answer("Ошибка данных", show_alert=True)
        return

    game = parts[3]
    user_id = callback.from_user.id

    if game not in settings.GAMES:
        logger.error(f"Неверная игра в callback: {game}")
        await callback.answer("Неверная игра", show_alert=True)
        return

    logger.info(f"Переключение на игру {game} для показа мэтчей пользователя {user_id}")

    if not await db.switch_game(user_id, game):
        await callback.answer("Ошибка переключения игры", show_alert=True)
        return

    if await db.is_user_banned(user_id):
        ban_info = await db.get_user_ban(user_id)
        game_name = settings.GAMES.get(game, game)
        text = f"Вы заблокированы в {game_name}"
        if ban_info:
            expires_at = ban_info['expires_at']
            ban_end = _format_expire_date(expires_at)
            text += f" до {ban_end}"

        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    profile = await db.get_user_profile(user_id, game)
    if not profile:
        game_name = settings.GAMES.get(game, game)
        await callback.answer(f"Сначала создайте анкету для {game_name}", show_alert=True)
        return

    from handlers.likes import _show_matches_internal
    await _show_matches_internal(callback, user_id, game, state, db)
    await callback.answer(f"Переключено на {settings.GAMES.get(game, game)}")

# ==================== ОБРАБОТЧИКИ ДЕЙСТВИЙ С ЛАЙКАМИ ====================

@router.callback_query(F.data.startswith("loves_back"))
async def like_back(callback: CallbackQuery, state: FSMContext, db):
    """Возврат к предыдущей анкете и повторная попытка лайк"""
    parts = callback.data.split("_")
    try:
        target_user_id = int(parts[2])
    except Exception:
        await callback.answer("Ошибка данных", show_alert=True)
        return

    current_index = 0
    if len(parts) > 3:
        try:
            current_index = int(parts[3])
        except Exception:
            current_index = 0

    await process_like_action(callback, target_user_id, "like", current_index, db=db)
    await callback.answer()

@router.callback_query(F.data.startswith("loves_skip_"))
async def skip_like(callback: CallbackQuery, db):
    """Пропуск лайка"""
    try:
        parts = callback.data.split("_")
        target_user_id = int(parts[2])
        current_index = int(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        await callback.answer("Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await safe_edit_message(callback, "Ошибка", kb.back())
        await callback.answer()
        return

    if await db.is_user_banned(user_id):
        game_name = settings.GAMES.get(user['current_game'], user['current_game'])
        ban_info = await db.get_user_ban(user_id)

        if ban_info:
            ban_end = ban_info['expires_at'][:16]
            text = f"Вы заблокированы в {game_name} до {ban_end}"
        else:
            text = f"Вы заблокированы в {game_name}"

        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    await process_like_action(callback, target_user_id, "skip", current_index, db=db)
    await callback.answer()

@router.callback_query(F.data.startswith("loves_report_"))
async def report_like(callback: CallbackQuery, state: FSMContext, db):
    """Инициация жалобы на лайк"""
    try:
        parts = callback.data.split("_")
        target_user_id = int(parts[2])
        current_index = int(parts[3]) if len(parts) > 3 else 0
    except (ValueError, IndexError):
        await callback.answer("Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await safe_edit_message(callback, "Ошибка", kb.back())
        await callback.answer()
        return

    game = user['current_game']

    if await db.is_user_banned(user_id):
        game_name = settings.GAMES.get(game, game)
        ban_info = await db.get_user_ban(user_id)

        if ban_info:
            expires_at = ban_info['expires_at']
            ban_end = _format_expire_date(expires_at)
            text = f"Вы заблокированы в {game_name} до {ban_end}"
        else:
            text = f"Вы заблокированы в {game_name}"

        await safe_edit_message(callback, text, kb.back())
        await callback.answer()
        return

    # Сохраняем данные для последующей отправки жалобы
    await state.update_data(
        report_target_user_id=target_user_id,
        report_from_likes=True,
        last_bot_message_id=callback.message.message_id,
        current_index=current_index
    )
    await state.set_state(LikesForm.waiting_report_message)

    text = (
        "<b>Подача жалобы</b>\n\n"
        "Напишите причину жалобы (ваше сообщение увидит только администратор):\n\n"
        "Например:\n"
        "• Неприемлемое фото\n"
        "• Оскорбительное описание\n"
        "• Спам или реклама\n"
        "• Фейковая анкета"
    )

    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text="Отмена", callback_data="cancel_report_likes")]
    ])

    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.callback_query(F.data == "cancel_report_likes")
async def cancel_report_likes(callback: CallbackQuery, state: FSMContext, db):
    """Отмена жалобы из раздела лайков"""
    data = await state.get_data()
    current_index = data.get('current_index', 0)

    await state.clear()
    await callback.answer("Жалоба отменена")

    # Возвращаемся к просмотру текущего лайка
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    if user and user.get('current_game'):
        game = user['current_game']
        likes = await db.get_likes_for_user(user_id, game)

        if likes and current_index < len(likes):
            # Показываем тот же лайк, на который хотели пожаловаться
            await show_like_profile(callback, likes, current_index)
        else:
            # Если лайков нет или индекс некорректный, показываем первый или сообщение
            await show_next_like_or_finish(callback, user_id, game, db)
    else:
        await safe_edit_message(callback, "Возвращение в главное меню", kb.back())

@router.message(LikesForm.waiting_report_message)
async def receive_like_report_message(message: Message, state: FSMContext, db):
    """Получение сообщения жалобы из раздела лайков"""
    data = await state.get_data()
    report_message = message.text
    bot = message.bot
    chat_id = message.chat.id
    last_bot_message_id = data.get('last_bot_message_id')

    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

    # Проверяем длину сообщения
    if not report_message or len(report_message.strip()) < 5:
        text = "Сообщение слишком короткое\n\nОпишите причину жалобы подробнее (минимум 5 символов):"
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Отмена", callback_data="cancel_report_likes")]
        ])

        if last_bot_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=last_bot_message_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
                sent = await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='HTML')
                await state.update_data(last_bot_message_id=sent.message_id)
        else:
            sent = await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='HTML')
            await state.update_data(last_bot_message_id=sent.message_id)
        return

    report_message = report_message[:500]
    target_user_id = data.get('report_target_user_id')
    user_id = message.from_user.id

    user = await db.get_user(user_id)
    if not user or not user.get('current_game'):
        await message.answer("Ошибка: не удалось определить игру")
        await state.clear()
        return

    game = user['current_game']

    # Удаляем лайк
    like_removed = await db.remove_like(target_user_id, user_id, game)
    if not like_removed:
        logger.info(f"Не удалось удалить лайк: {user_id} пожаловался на {target_user_id}")

    # Добавляем жалобу с сообщением
    report_added = await db.add_report(user_id, target_user_id, game, report_message)

    # Очищаем данные жалобы из state
    await state.update_data(report_target_user_id=None)

    if report_added:
        await notify_admin_new_report(bot, user_id, target_user_id, game)
        logger.info(f"Жалоба на лайк: {user_id} пожаловался на {target_user_id}, причина: {report_message[:50]}")

        notification_text = "Жалоба отправлена модератору!"
    else:
        notification_text = "Вы уже жаловались на этого пользователя"

    # Удаляем предыдущее сообщение и отправляем уведомление
    if last_bot_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=last_bot_message_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить предыдущее сообщение: {e}")

    sent = await bot.send_message(chat_id, notification_text, parse_mode='HTML')
    last_bot_message_id = sent.message_id

    # Создаем фейковый callback для show_next_like_or_finish
    import asyncio
    await asyncio.sleep(0.5)

    class FakeMessage:
        def __init__(self, msg_id, chat, bot_instance):
            self.message_id = msg_id
            self.chat = chat
            self.bot = bot_instance
            self._bot = bot_instance
            self._chat_id = chat.id

        async def delete(self):
            try:
                await self._bot.delete_message(chat_id=self._chat_id, message_id=self.message_id)
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение {self.message_id}: {e}")

        async def edit_text(self, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
            try:
                await self._bot.edit_message_text(
                    chat_id=self._chat_id,
                    message_id=self.message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
            except Exception as e:
                logger.warning(f"Не удалось отредактировать сообщение {self.message_id}: {e}")

        async def answer_photo(self, photo, caption=None, reply_markup=None, parse_mode=None, **kwargs):
            return await self._bot.send_photo(
                chat_id=self._chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

        async def answer(self, text, reply_markup=None, parse_mode=None, **kwargs):
            return await self._bot.send_message(
                chat_id=self._chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

    class FakeCallback:
        def __init__(self, msg, user, bot_instance):
            self.message = msg
            self.from_user = user
            self.bot = bot_instance

        async def answer(self, text="", show_alert=False):
            pass

    fake_msg = FakeMessage(last_bot_message_id, message.chat, bot)
    fake_callback = FakeCallback(fake_msg, message.from_user, bot)

    await show_next_like_or_finish(fake_callback, user_id, game, db)

    # Очищаем state после показа следующего лайка
    await state.clear()

# ==================== ПОКАЗ КОНТАКТОВ ====================

@router.callback_query(F.data.startswith("contact_"))
async def show_contact(callback: CallbackQuery, db):
    """Показ контактной информации матча"""
    try:
        parts = callback.data.split("_")
        target_user_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        await callback.answer("Ошибка", show_alert=True)
        return

    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if not user or not user.get('current_game'):
        await callback.answer("Ошибка", show_alert=True)
        return

    game = user['current_game']

    if await db.is_user_banned(user_id):
        game_name = settings.GAMES.get(game, game)
        ban_info = await db.get_user_ban(user_id)

        if ban_info:
            ban_end = ban_info['expires_at'][:16]
            await callback.answer(f"Вы заблокированы в {game_name} до {ban_end}", show_alert=True)
        else:
            await callback.answer(f"Вы заблокированы в {game_name}", show_alert=True)
        return

    target_profile = await db.get_user_profile(target_user_id, game)

    if not target_profile:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    profile_text = texts.format_profile(target_profile)
    text = f"Ваш мэтч:\n\n{profile_text}"

    keyboard = kb.contact(target_profile.get('username'), page=page)

    await show_profile_with_photo(callback, target_profile, text, keyboard)