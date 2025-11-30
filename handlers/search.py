import logging
import random
import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from handlers.likes import show_profile_with_photo

from handlers.basic import check_ban_and_profile, safe_edit_message, SearchForm
from handlers.notifications import notify_about_match, notify_about_like, update_user_activity, notify_admin_new_report
from handlers.likes import show_profile_with_photo

import keyboards.keyboards as kb
import utils.texts as texts
import config.settings as settings

logger = logging.getLogger(__name__)
router = Router()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def update_filters_display(callback: CallbackQuery, state: FSMContext, message: str = None):
    """Отображение текущих фильтров с учётом роли"""
    data = await state.get_data()
    game = data.get('game', 'dota')
    game_name = settings.GAMES.get(game, game)
    role_filter = data.get('role_filter', 'player')

    filters_text = []

    role_name = settings.ROLES.get(role_filter, 'Игрок')
    filters_text.append(f"<b>Роль:</b> {role_name}")

    if role_filter == 'player':
        rating_filter = data.get('rating_filter')
        if rating_filter:
            rating_name = settings.RATINGS[game].get(rating_filter, rating_filter)
            filters_text.append(f"<b>Рейтинг:</b> {rating_name}")
        else:
            filters_text.append("<b>Рейтинг:</b> не указан")

        position_filter = data.get('position_filter')
        if position_filter:
            position_name = settings.POSITIONS[game].get(position_filter, position_filter)
            filters_text.append(f"<b>Позиция:</b> {position_name}")
        else:
            filters_text.append("<b>Позиция:</b> не указана")

        goals_filter = data.get('goals_filter')
        if goals_filter:
            goals_name = settings.GOALS.get(goals_filter, goals_filter)
            filters_text.append(f"<b>Цель:</b> {goals_name}")
        else:
            filters_text.append("<b>Цель:</b> не указана")

    country_filter = data.get('country_filter')
    if country_filter:
        country_name = settings.MAIN_COUNTRIES.get(country_filter) or settings.COUNTRIES_DICT.get(country_filter, country_filter)
        filters_text.append(f"<b>Страна:</b> {country_name}")
    else:
        filters_text.append("<b>Страна:</b> не указана")

    text = f"Настройка фильтров для {game_name}\n\n"
    text += "\n".join(filters_text)
    text += "\n\nВыберите что настроить:"

    await safe_edit_message(callback, text, kb.filters_setup_menu(role_filter))

    if message:
        await callback.answer(message)

async def get_full_filters_display(data: dict) -> str:
    """Полное отображение всех фильтров с учётом роли"""
    game = data.get('game', 'dota')
    game_name = settings.GAMES.get(game, game)
    role_filter = data.get('role_filter', 'player')

    filters_text = []

    role_name = settings.ROLES.get(role_filter, 'Игрок')
    filters_text.append(f"<b>Роль:</b> {role_name}")

    if role_filter == 'player':
        rating_filter = data.get('rating_filter')
        if rating_filter:
            rating_name = settings.RATINGS[game].get(rating_filter, rating_filter)
            filters_text.append(f"<b>Рейтинг:</b> {rating_name}")
        else:
            filters_text.append("<b>Рейтинг:</b> не указан")

        position_filter = data.get('position_filter')
        if position_filter:
            position_name = settings.POSITIONS[game].get(position_filter, position_filter)
            filters_text.append(f"<b>Позиция:</b> {position_name}")
        else:
            filters_text.append("<b>Позиция:</b> не указана")

        goals_filter = data.get('goals_filter')
        if goals_filter:
            goals_name = settings.GOALS.get(goals_filter, goals_filter)
            filters_text.append(f"<b>Цель:</b> {goals_name}")
        else:
            filters_text.append("<b>Цель:</b> не указана")

    country_filter = data.get('country_filter')
    if country_filter:
        country_name = settings.MAIN_COUNTRIES.get(country_filter) or settings.COUNTRIES_DICT.get(country_filter, country_filter)
        filters_text.append(f"<b>Страна:</b> {country_name}")
    else:
        filters_text.append("<b>Страна:</b> не указана")

    text = f"Поиск в {game_name}\n\n"
    text += "\n".join(filters_text)
    text += "\n\nВыберите действие:"

    return text

async def handle_search_action(callback: CallbackQuery, action: str, target_user_id: int, state: FSMContext, db):
    """Универсальная обработка действий в поиске"""
    user_id = callback.from_user.id
    data = await state.get_data()
    
    current_index = data.get('current_index', 0)
    profiles_shown = data.get('profiles_shown', 0)
    profiles = data.get('profiles', [])
    
    logger.info(f"🔶 handle_search_action: action={action}, current_index={current_index}, profiles_shown={profiles_shown}")
    
    if 'game' not in data:
        user = await db.get_user(user_id)
        game = user['current_game']
        
        await state.update_data(
            game=game,
            current_index=current_index,
            profiles_shown=profiles_shown,
            profiles=profiles,
            user_id=user_id
        )
        logger.warning(f"⚠️ Восстановлена game в handle_search_action, сохранены: current_index={current_index}, profiles_shown={profiles_shown}")
    else:
        game = data['game']
    
    if action == "like":
        is_match = await db.add_like(user_id, target_user_id, game, message=None)
        
        if is_match:
            target_profile = await db.get_user_profile(target_user_id, game)
            await notify_about_match(callback.bot, target_user_id, user_id, game, db)
            
            if target_profile:
                match_text = texts.format_profile(target_profile, show_contact=True)
                text = f"{texts.MATCH_CREATED}\n\n{match_text}"
            else:
                text = texts.MATCH_CREATED
                if target_profile and target_profile.get('username'):
                    text += f"\n\n@{target_profile['username']}"
                else:
                    text += "\n\n(У пользователя нет @username)"
            
            keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
                [kb.InlineKeyboardButton(text="Продолжить поиск", callback_data="continue_search")],
                [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
            ])
            
            await safe_edit_message(callback, text, keyboard)
            logger.info(f"Мэтч: {user_id} <-> {target_user_id}")
        else:
            await callback.answer("Лайк отправлен!")
            await notify_about_like(callback.bot, target_user_id, game, db)
            logger.info(f"Лайк: {user_id} -> {target_user_id}")
            await show_next_profile(callback, state, db)
    
    elif action == "skip":
        await db.add_search_skip(user_id, target_user_id, game)
        logger.info(f"Пропуск в поиске: {user_id} пропустил {target_user_id}")
        await show_next_profile(callback, state, db)
    
    elif action == "report":
        await state.update_data(
            report_target_user_id=target_user_id,
            last_bot_message_id=callback.message.message_id
        )
        await state.set_state(SearchForm.waiting_report_message)

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
            [kb.InlineKeyboardButton(text="Отмена", callback_data="cancel_report")]
        ])

        await safe_edit_message(callback, text, keyboard)
        await callback.answer()

async def show_current_profile(callback: CallbackQuery, state: FSMContext):
    """Показ текущего профиля в поиске"""
    data = await state.get_data()
    profiles = data.get('profiles', [])
    index = data.get('current_index', 0)
    
    if not data or 'game' not in data:
        logger.warning(f"⚠️ show_current_profile: Нет данных! data={data}")
        await callback.answer("Сессия поиска истекла", show_alert=True)
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Новый поиск", callback_data="search")],
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, "Начните новый поиск:", keyboard)
        return
    
    if index >= len(profiles):
        game_name = settings.GAMES.get(data.get('game', 'dota'), data.get('game', 'dota'))
        text = f"Больше анкет в {game_name} не найдено!\n\nПопробуйте изменить фильтры или зайти позже"
        
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Новый поиск", callback_data="search")],
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, text, keyboard)
        await callback.answer()
        return
    
    profile = profiles[index]
    profile_text = texts.format_profile(profile)
    
    await show_profile_with_photo(
        callback,
        profile,
        profile_text,
        kb.profile_actions(profile['telegram_id'])
    )

async def show_next_profile(callback: CallbackQuery, state: FSMContext, db):
    """Показ следующего профиля с автоподгрузкой и рекламой"""
    data = await state.get_data()
    current_index = data.get('current_index', 0)
    profiles = data.get('profiles', [])
    profiles_shown = data.get('profiles_shown', 0)

    logger.info(f"🔵 show_next_profile СТАРТ: current_index={current_index}, profiles_shown={profiles_shown}")

    if not data or 'user_id' not in data:
        user_id = callback.from_user.id
        user = await db.get_user(user_id)
        game = user['current_game']
        await state.update_data(
            user_id=user_id,
            game=game,
            profiles_shown=0
        )
        logger.info(f"🟡 Инициализация user_id, установлен profiles_shown=0")
        data = await state.get_data()

    next_index = current_index + 1
    next_profiles_shown = profiles_shown + 1

    logger.info(f"🟢 Увеличены счётчики: next_index={next_index}, next_profiles_shown={next_profiles_shown}")

    if profiles and next_index >= len(profiles) - 5:
        last_offset = data.get('last_loaded_offset', 0)
        new_offset = last_offset + 20

        try:
            new_batch = await db.get_potential_matches(
                user_id=data['user_id'],
                game=data['game'],
                rating_filter=data.get('rating_filter'),
                position_filter=data.get('position_filter'),
                country_filter=data.get('country_filter'),
                goals_filter=data.get('goals_filter'),
                limit=20,
                offset=new_offset
            )

            if new_batch:
                profiles.extend(new_batch)
                await state.update_data(
                    profiles=profiles,
                    last_loaded_offset=new_offset
                )
                logger.info(f"🔄 Подгружено {len(new_batch)} новых анкет, всего: {len(profiles)}")
        except Exception as e:
            logger.error(f"Ошибка при подгрузке анкет: {e}")

    ads = await db.get_active_ads_for_game(data['game'])

    if ads:
        user_profile = await db.get_user_profile(data['user_id'], data['game'])
        user_region = user_profile.get('region', 'any') if user_profile else 'any'

        if user_region != 'any':
            filtered_ads = []
            for ad in ads:
                ad_regions = ad.get('regions', ['all'])
                if 'all' in ad_regions or user_region in ad_regions:
                    filtered_ads.append(ad)
            ads = filtered_ads

    if ads and next_profiles_shown > 0:
        if 'ads_queue_ids' not in data or not data['ads_queue_ids']:
            import random
            ads_ids = [ad['id'] for ad in ads]
            random.shuffle(ads_ids)
            current_ad_index = 0

            first_ad = next((ad for ad in ads if ad['id'] == ads_ids[0]), None)
            next_ad_at = first_ad.get('show_interval', 3) if first_ad else 3

            await state.update_data(
                ads_queue_ids=ads_ids,
                current_ad_index=current_ad_index,
                next_ad_at=next_ad_at
            )
            logger.info(f"🎲 Инициализирована очередь реклам: {len(ads_ids)} реклам (ID: {ads_ids}), первая через {next_ad_at} анкет")
            data = await state.get_data()

        ads_queue_ids = data.get('ads_queue_ids', [])
        current_ad_index = data.get('current_ad_index', 0)
        next_ad_at = data.get('next_ad_at', 3)

        if next_profiles_shown >= next_ad_at and current_ad_index < len(ads_queue_ids):
            current_ad_id = ads_queue_ids[current_ad_index]
            ad = next((a for a in ads if a['id'] == current_ad_id), None)

            if not ad:
                logger.error(f"❌ Реклама #{current_ad_id} не найдена в активных рекламах, пропускаем")
                new_ad_index = current_ad_index + 1
                if new_ad_index >= len(ads_queue_ids):
                    import random
                    ads_ids = [a['id'] for a in ads]
                    random.shuffle(ads_ids)
                    new_ad_index = 0
                    await state.update_data(ads_queue_ids=ads_ids)
                    ads_queue_ids = ads_ids

                await state.update_data(current_ad_index=new_ad_index)
            else:
                logger.info(f"🟠 ПОКАЗЫВАЕМ РЕКЛАМУ #{ad['id']} ({ad.get('ad_type', 'forward')}) на шаге {next_profiles_shown} (запланировано на {next_ad_at}, интервал {ad.get('show_interval', 3)})")

                try:
                    try:
                        await callback.message.delete()
                    except Exception as e:
                        logger.warning(f"Не удалось удалить сообщение: {e}")

                    ad_type = ad.get('ad_type', 'forward')

                    if ad_type == 'copy':
                        copied_msg = await callback.bot.copy_message(
                            chat_id=callback.message.chat.id,
                            from_chat_id=ad['chat_id'],
                            message_id=ad['message_id'],
                            reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
                                [kb.InlineKeyboardButton(text="Продолжить", callback_data="ad_continue")]
                            ])
                        )

                        new_ad_index = current_ad_index + 1

                        if new_ad_index >= len(ads_queue_ids):
                            import random
                            ads_ids = [a['id'] for a in ads]
                            random.shuffle(ads_ids)
                            ads_queue_ids = ads_ids
                            new_ad_index = 0
                            logger.info(f"🔄 Очередь реклам пройдена, перемешиваем и начинаем заново (новые ID: {ads_ids})")

                        next_ad_id = ads_queue_ids[new_ad_index]
                        next_ad = next((a for a in ads if a['id'] == next_ad_id), None)

                        if next_ad:
                            new_next_ad_at = next_profiles_shown + next_ad.get('show_interval', 3)
                            logger.info(f"📍 Следующая реклама: #{next_ad['id']} (интервал {next_ad.get('show_interval', 3)}), покажем на шаге {new_next_ad_at}")
                        else:
                            new_next_ad_at = next_profiles_shown + 3
                            logger.warning(f"⚠️ Следующая реклама #{next_ad_id} не найдена, используем интервал по умолчанию (3)")

                        await state.update_data(
                            current_index=next_index,
                            profiles_shown=next_profiles_shown,
                            ad_copied_message_id=copied_msg.message_id,
                            ads_queue_ids=ads_queue_ids,
                            current_ad_index=new_ad_index,
                            next_ad_at=new_next_ad_at
                        )

                        logger.info(f"✅ Реклама (copy) показана! current_index={next_index}, profiles_shown={next_profiles_shown}")
                        return

                    else:  # forward
                        forwarded_msg = await callback.bot.forward_message(
                            chat_id=callback.message.chat.id,
                            from_chat_id=ad['chat_id'],
                            message_id=ad['message_id']
                        )

                        button_msg = await callback.bot.send_message(
                            chat_id=callback.message.chat.id,
                            text="Нажмите на кнопку ниже, чтобы продолжить просмотр анкет",
                            reply_markup=kb.InlineKeyboardMarkup(inline_keyboard=[
                                [kb.InlineKeyboardButton(text="Продолжить", callback_data="ad_continue")]
                            ])
                        )

                    new_ad_index = current_ad_index + 1

                    if new_ad_index >= len(ads_queue_ids):
                        import random
                        ads_ids = [a['id'] for a in ads]
                        random.shuffle(ads_ids)
                        ads_queue_ids = ads_ids
                        new_ad_index = 0
                        logger.info(f"🔄 Очередь реклам пройдена, перемешиваем и начинаем заново (новые ID: {ads_ids})")

                    next_ad_id = ads_queue_ids[new_ad_index]
                    next_ad = next((a for a in ads if a['id'] == next_ad_id), None)

                    if next_ad:
                        new_next_ad_at = next_profiles_shown + next_ad.get('show_interval', 3)
                        logger.info(f"📍 Следующая реклама: #{next_ad['id']} (интервал {next_ad.get('show_interval', 3)}), покажем на шаге {new_next_ad_at}")
                    else:
                        new_next_ad_at = next_profiles_shown + 3
                        logger.warning(f"⚠️ Следующая реклама #{next_ad_id} не найдена, используем интервал по умолчанию (3)")

                    await state.update_data(
                        current_index=next_index,
                        profiles_shown=next_profiles_shown,
                        ad_forwarded_message_id=forwarded_msg.message_id,
                        ad_button_message_id=button_msg.message_id,
                        ads_queue_ids=ads_queue_ids,
                        current_ad_index=new_ad_index,
                        next_ad_at=new_next_ad_at
                    )

                    logger.info(f"✅ Реклама показана! current_index={next_index}, profiles_shown={next_profiles_shown}")
                    return

                except Exception as e:
                    logger.error(f"❌ Ошибка показа рекламы #{ad.get('id')}: {e}")
        else:
            logger.debug(f"⏭️ Реклама не показывается: profiles_shown={next_profiles_shown}, next_ad_at={next_ad_at}")
    else:
        if not ads:
            logger.debug(f"⏭️ Реклама пропущена: нет активных реклам для игры {data['game']}")
        else:
            logger.debug(f"⏭️ Реклама пропущена: profiles_shown={next_profiles_shown} (ещё не начали показ)")

    logger.info(f"🔵 Показ анкеты: сохраняем current_index={next_index}, profiles_shown={next_profiles_shown}")
    await state.update_data(
        current_index=next_index,
        profiles_shown=next_profiles_shown
    )
    await show_current_profile(callback, state)

# ==================== ОСНОВНЫЕ ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "search")
@check_ban_and_profile()
async def start_search_menu(callback: CallbackQuery, state: FSMContext, db):
    """Показ главного меню поиска"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    game = user['current_game']

    await update_user_activity(user_id, 'search_setup', db)

    data = await state.get_data()
    
    if not data or data.get('game') != game:
        await state.clear()
        await state.update_data(
            user_id=user_id,
            game=game,
            rating_filter=None,
            position_filter=None,
            region_filter=None,
            goals_filter=None,
            role_filter='player',
            profiles=[],
            current_index=0,
            profiles_shown=0
        )
        data = await state.get_data()
    
    await state.set_state(SearchForm.menu)

    text = await get_full_filters_display(data)
    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

@router.callback_query(F.data == "setup_filters", SearchForm.menu)
async def setup_filters_menu(callback: CallbackQuery, state: FSMContext):
    """Переход к настройке фильтров"""
    await state.set_state(SearchForm.filters)
    await update_filters_display(callback, state)
    await callback.answer()

@router.callback_query(F.data == "back_to_search")
async def back_to_search_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат к главному меню поиска"""
    data = await state.get_data()
    await state.set_state(SearchForm.menu)

    text = await get_full_filters_display(data)
    await safe_edit_message(callback, text, kb.search_filters())
    await callback.answer()

@router.callback_query(F.data == "ad_continue")
async def ad_continue_after_ad(callback: CallbackQuery, state: FSMContext, db):
    """Продолжение поиска после просмотра рекламы"""
    data = await state.get_data()

    current_profiles_shown = data.get('profiles_shown', 0)
    logger.info(f"🟢 ad_continue: current_index={data.get('current_index')}, profiles_shown={current_profiles_shown}")

    current_state = await state.get_state()
    if current_state != SearchForm.browsing:
        await callback.answer("Сессия поиска истекла", show_alert=True)
        return

    # Удаляем скопированное сообщение (тип 'copy')
    ad_copied_message_id = data.get('ad_copied_message_id')
    if ad_copied_message_id:
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=ad_copied_message_id
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить скопированную рекламу: {e}")

    # Удаляем пересланное рекламное сообщение (тип 'forward')
    ad_forwarded_message_id = data.get('ad_forwarded_message_id')
    if ad_forwarded_message_id:
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=ad_forwarded_message_id
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить пересланную рекламу: {e}")

    # Удаляем сообщение с кнопкой (текущее сообщение callback, только для типа 'forward')
    ad_button_message_id = data.get('ad_button_message_id')
    if ad_button_message_id:
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=ad_button_message_id
            )
        except Exception as e:
            logger.warning(f"Не удалось удалить кнопку рекламы: {e}")

    # Убираем ID сообщений рекламы из state
    await state.update_data(
        ad_copied_message_id=None,
        ad_forwarded_message_id=None,
        ad_button_message_id=None
    )

    logger.info(f"✅ Продолжаем после рекламы: current_index={data.get('current_index')}, profiles_shown={current_profiles_shown}")

    await show_current_profile(callback, state)
    await callback.answer()

# ==================== НАСТРОЙКА ФИЛЬТРОВ ====================

@router.callback_query(F.data == "filter_role", SearchForm.filters)
async def set_role_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора роли"""
    await safe_edit_message(callback, "Выберите роль:", kb.role_filter())
    await callback.answer()

@router.callback_query(F.data == "filter_rating", SearchForm.filters)
async def set_rating_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора рейтинга"""
    data = await state.get_data()
    game = data.get('game')
    await safe_edit_message(callback, "Выберите рейтинг:", kb.ratings_filter(game))
    await callback.answer()

@router.callback_query(F.data == "filter_position", SearchForm.filters)
async def set_position_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора позиции"""
    data = await state.get_data()
    game = data.get('game')
    await safe_edit_message(callback, "Выберите позицию:", kb.position_filter_menu(game))
    await callback.answer()

@router.callback_query(F.data == "filter_country", SearchForm.filters)
async def set_country_filter(callback: CallbackQuery, state: FSMContext):
    """Настройка фильтра по стране"""
    text = "Выберите страну для поиска:"
    keyboard = kb.countries_filter()
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.callback_query(F.data == "filter_goals", SearchForm.filters)
async def set_goals_filter(callback: CallbackQuery, state: FSMContext):
    """Показать меню выбора цели"""
    await safe_edit_message(callback, "Выберите цель:", kb.goals_filter())
    await callback.answer()

@router.callback_query(F.data == "reset_all_filters", SearchForm.filters)
async def reset_all_filters(callback: CallbackQuery, state: FSMContext):
    """Сброс всех фильтров"""
    await state.update_data(
        rating_filter=None,
        position_filter=None,
        country_filter=None,
        goals_filter=None,
        role_filter='player'
    )
    await update_filters_display(callback, state, "Все фильтры сброшены")

# ==================== СОХРАНЕНИЕ ФИЛЬТРОВ ====================

@router.callback_query(F.data.startswith("role_filter_"), SearchForm.filters)
async def save_role_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранной роли"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        return

    role = parts[2]

    if role not in settings.ROLES:
        return

    data = await state.get_data()
    current_role = data.get('role_filter', 'player')
    
    if current_role == role:
        await callback.answer("Эта роль уже выбрана")
        return

    await state.update_data(role_filter=role)
    
    if role != 'player':
        await state.update_data(
            rating_filter=None,
            position_filter=None,
            goals_filter=None
        )
    
    role_name = settings.ROLES.get(role, role)
    await update_filters_display(callback, state, f"Фильтр по роли: {role_name}")

@router.callback_query(F.data.startswith("rating_"), SearchForm.filters)
async def save_rating_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранного рейтинга"""
    if callback.data.endswith("_reset"):
        await state.update_data(rating_filter=None)
        await update_filters_display(callback, state, "Фильтр по рейтингу сброшен")
        return

    rating = callback.data.split("_")[1]
    data = await state.get_data()
    game = data['game']

    if rating not in settings.RATINGS.get(game, {}):
        return

    current_rating = data.get('rating_filter')
    if current_rating == rating:
        await callback.answer("Этот рейтинг уже выбран")
        return

    await state.update_data(rating_filter=rating)
    rating_name = settings.RATINGS[game].get(rating, rating)
    await update_filters_display(callback, state, f"Фильтр по рейтингу: {rating_name}")

@router.callback_query(F.data.startswith("pos_filter_"), SearchForm.filters)
async def save_position_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранной позиции"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        return

    position = parts[2]
    data = await state.get_data()
    game = data['game']

    if position not in settings.POSITIONS.get(game, {}):
        return

    current_position = data.get('position_filter')
    if current_position == position:
        await callback.answer("Эта позиция уже выбрана")
        return

    await state.update_data(position_filter=position)
    position_name = settings.POSITIONS[game].get(position, position)
    await update_filters_display(callback, state, f"Фильтр по позиции: {position_name}")

@router.callback_query(F.data.startswith("country_filter_"), SearchForm.filters)
async def save_country_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранной страны в фильтре"""
    parts = callback.data.split("_")
    
    if len(parts) < 3:
        return

    if parts[2] == "other":
        await state.set_state(SearchForm.country_filter_input)

        text = "Введите название страны для поиска:\n\nНапример: Молдова, Эстония, Литва, Польша, Германия и т.д."

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_country_filter")]
        ])

        await safe_edit_message(callback, text, keyboard)
        await callback.answer()
        return

    country = parts[2]

    if country not in settings.MAIN_COUNTRIES:
        return

    data = await state.get_data()
    current_country = data.get('country_filter')
    if current_country == country:
        await callback.answer("Эта страна уже выбрана")
        return

    await state.update_data(country_filter=country)
    country_name = settings.MAIN_COUNTRIES.get(country, country)
    await update_filters_display(callback, state, f"Фильтр по стране: {country_name}")

@router.callback_query(F.data == "back_country_filter", SearchForm.country_filter_input)
async def back_to_country_filter(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору страны в фильтре"""
    await state.set_state(SearchForm.filters)
    
    text = "Выберите страну для поиска:"
    keyboard = kb.countries_filter()
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.message(SearchForm.country_filter_input)
async def process_country_filter_input(message: Message, state: FSMContext):
    """Обработка ввода названия страны для фильтра"""
    search_name = message.text.strip()
    
    country_key = settings.find_country_by_name(search_name)
    
    if country_key:
        country_name = settings.COUNTRIES_DICT[country_key]
        text = f"Найдена страна: {country_name}\n\nВыберите действие:"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Использовать {country_name}", callback_data=f"confirm_filter_country_{country_key}")],
            [InlineKeyboardButton(text="Попробовать еще раз", callback_data="retry_country_filter_input")],
            [InlineKeyboardButton(text="Назад", callback_data="back_country_filter")]
        ])
        
        await message.answer(text, reply_markup=keyboard)
    else:
        text = f"Страна '{search_name}' не найдена в словаре.\n\nПопробуйте ввести другое название."
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Попробовать еще раз", callback_data="retry_country_filter_input")],
            [InlineKeyboardButton(text="Назад", callback_data="back_country_filter")]
        ])
        
        await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "retry_country_filter_input", SearchForm.country_filter_input)
async def handle_retry_country_filter_input(callback: CallbackQuery, state: FSMContext):
    """Обработчик повторного ввода страны в фильтре поиска"""  
    text = "Введите название страны для поиска:\n\nНапример: Молдова, Эстония, Литва, Польша, Германия и т.д."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_country_filter")]
    ])
    
    await safe_edit_message(callback, text, keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_filter_country_"), SearchForm.country_filter_input)
async def confirm_country_filter(callback: CallbackQuery, state: FSMContext):
    """Подтверждение выбранной страны для фильтра"""
    country_key = callback.data.split("_", 3)[3]

    await state.update_data(country_filter=country_key)
    await state.set_state(SearchForm.filters)

    country_name = settings.COUNTRIES_DICT[country_key]

    try:
        await callback.message.delete()
    except:
        pass

    await update_filters_display(callback, state, f"Фильтр по стране: {country_name}")

@router.callback_query(F.data.startswith("goals_filter_"), SearchForm.filters)
async def save_goals_filter(callback: CallbackQuery, state: FSMContext):
    """Сохранение выбранной цели"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        return

    goal = parts[2]

    if goal not in settings.GOALS:
        return

    data = await state.get_data()
    current_goal = data.get('goals_filter')
    if current_goal == goal:
        await callback.answer("Эта цель уже выбрана")
        return

    await state.update_data(goals_filter=goal)
    goals_name = settings.GOALS.get(goal, goal)
    await update_filters_display(callback, state, f"Фильтр по цели: {goals_name}")

# ==================== СБРОС ФИЛЬТРОВ ====================

@router.callback_query(F.data == "role_reset", SearchForm.filters)
async def reset_role_filter(callback: CallbackQuery, state: FSMContext):
    """Сброс фильтра по роли"""
    await state.update_data(role_filter='player')
    await update_filters_display(callback, state, "Фильтр по роли сброшен на 'Игрок'")

@router.callback_query(F.data == "rating_reset", SearchForm.filters)
async def reset_rating_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(rating_filter=None)
    await update_filters_display(callback, state, "Фильтр по рейтингу сброшен")

@router.callback_query(F.data == "position_reset", SearchForm.filters)
async def reset_position_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(position_filter=None)
    await update_filters_display(callback, state, "Фильтр по позиции сброшен")

@router.callback_query(F.data == "country_reset", SearchForm.filters)
async def reset_country_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(country_filter=None)
    await update_filters_display(callback, state, "Фильтр по стране сброшен")

@router.callback_query(F.data == "goals_reset", SearchForm.filters)
async def reset_goals_filter(callback: CallbackQuery, state: FSMContext):
    await state.update_data(goals_filter=None)
    await update_filters_display(callback, state, "Фильтр по цели сброшен")

@router.callback_query(F.data == "cancel_filter", SearchForm.filters)
async def cancel_filter(callback: CallbackQuery, state: FSMContext):
    await update_filters_display(callback, state, "Отменено")

# ==================== НАЧАЛО ПОИСКА ====================

@router.callback_query(F.data == "start_search")
async def begin_search(callback: CallbackQuery, state: FSMContext, db):
    """Начать поиск с применением фильтров"""
    data = await state.get_data()
    current_state = await state.get_state()
    
    if current_state == SearchForm.menu:
        await state.set_state(SearchForm.filters)
        data = await state.get_data()
    
    await update_user_activity(data['user_id'], 'search_browsing', db)
    
    all_profiles = []
    for batch_offset in [0, 20, 40]:
        batch = await db.get_potential_matches(
            user_id=data['user_id'],
            game=data['game'],
            rating_filter=data.get('rating_filter'),
            position_filter=data.get('position_filter'),
            country_filter=data.get('country_filter'),
            goals_filter=data.get('goals_filter'),
            role_filter=data.get('role_filter'),
            limit=20,
            offset=batch_offset
        )
        if batch:
            all_profiles.extend(batch)
        else:
            break
    
    if not all_profiles:
        await state.clear()
        game_name = settings.GAMES.get(data['game'], data['game'])
        text = f"Анкеты в {game_name} не найдены!\n\nПопробуйте изменить фильтры или зайти позже"
        
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Новый поиск", callback_data="search")],
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
        ])
        await safe_edit_message(callback, text, keyboard)
        await callback.answer()
        return
    
    # Получаем профиль пользователя для фильтрации рекламы по региону
    user_profile = await db.get_user_profile(data['user_id'], data['game'])
    user_region = user_profile.get('region', 'any') if user_profile else 'any'

    # Инициализируем очередь реклам для нового поиска
    ads = await db.get_active_ads_for_game(data['game'])

    # Фильтруем рекламу по региону пользователя
    if ads and user_region != 'any':
        filtered_ads = []
        for ad in ads:
            ad_regions = ad.get('regions', ['all'])
            # Показываем рекламу если:
            # 1. В рекламе указаны "все регионы" (all)
            # 2. Регион пользователя входит в список регионов рекламы
            if 'all' in ad_regions or user_region in ad_regions:
                filtered_ads.append(ad)
        ads = filtered_ads
        logger.info(f"🌍 Отфильтровано реклам по региону {user_region}: {len(ads)} из {len(filtered_ads)}")

    ads_queue_ids = []
    current_ad_index = 0
    next_ad_at = 0

    if ads:
        import random
        # Сохраняем только ID реклам
        ads_queue_ids = [ad['id'] for ad in ads]
        random.shuffle(ads_queue_ids)
        # Получаем интервал первой рекламы
        first_ad = next((ad for ad in ads if ad['id'] == ads_queue_ids[0]), None)
        next_ad_at = first_ad.get('show_interval', 3) if first_ad else 3
        logger.info(f"🎲 Инициализирована очередь реклам: {len(ads_queue_ids)} реклам (ID: {ads_queue_ids}), первая через {next_ad_at} анкет")

    await state.set_state(SearchForm.browsing)
    await state.update_data(
        profiles=all_profiles,
        current_index=0,
        last_loaded_offset=40,
        profiles_shown=0,
        ads_queue_ids=ads_queue_ids,
        current_ad_index=current_ad_index,
        next_ad_at=next_ad_at
    )
    await show_current_profile(callback, state)

# ==================== ДЕЙСТВИЯ В ПОИСКЕ ====================

@router.callback_query(F.data.startswith("skip_"))
async def skip_profile(callback: CallbackQuery, state: FSMContext, db):
    data_before = await state.get_data()
    logger.info(f"🟤 skip_profile ВЫЗВАН: current_index={data_before.get('current_index')}, profiles_shown={data_before.get('profiles_shown')}")
    
    try:
        target_user_id = int(callback.data.split("_")[1])
    except Exception:
        await state.clear()
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await handle_search_action(callback, "skip", target_user_id, state, db)

@router.callback_query(F.data.regexp(r"^like_\d+$"))
async def like_profile(callback: CallbackQuery, state: FSMContext, db):
    if callback.data.startswith("like_msg_"):
        return
    
    try:
        target_user_id = int(callback.data.split("_")[1])
    except Exception:
        await state.clear()
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await handle_search_action(callback, "like", target_user_id, state, db)

@router.callback_query(F.data.startswith("report_"))
async def report_profile(callback: CallbackQuery, state: FSMContext, db):
    try:
        target_user_id = int(callback.data.split("_")[1])
    except Exception:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    await handle_search_action(callback, "report", target_user_id, state, db)

@router.callback_query(F.data == "continue_search", SearchForm.browsing)
async def continue_search(callback: CallbackQuery, state: FSMContext, db):
    """Продолжить поиск после мэтча"""
    data = await state.get_data()
    
    logger.info(f"🔄 continue_search вызвана: profiles_shown={data.get('profiles_shown')}")
    
    if not data or 'profiles' not in data:
        logger.info(f"⚠️ Нет данных, начинаем новый поиск (profiles_shown будет сброшен)")
        await begin_search(callback, state, db)
    else:
        logger.info(f"✅ Продолжаем текущий поиск")
        await show_next_profile(callback, state, db)

@router.callback_query(F.data.startswith("like_msg_"))
async def like_with_message(callback: CallbackQuery, state: FSMContext, db):
    """Инициация лайка с сообщением"""
    try:
        target_user_id = int(callback.data.split("_")[2])
    except Exception:
        await state.clear()
        await callback.answer("Ошибка данных", show_alert=True)
        return
    
    data = await state.get_data()
    profiles = data.get('profiles', [])
    current_index = data.get('current_index', 0)
    
    if current_index >= len(profiles):
        await callback.answer("Анкета не найдена", show_alert=True)
        return
    
    profile = profiles[current_index]
    
    await state.update_data(
        message_target_user_id=target_user_id,
        message_target_index=current_index,
        last_search_message_id=callback.message.message_id
    )
    await state.set_state(SearchForm.waiting_message)
    
    profile_text = texts.format_profile(profile)
    text = f"{profile_text}\n\n<b>💌 Напишите сообщение этому пользователю:</b>"
    
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text="Отмена", callback_data="cancel_message")]
    ])
    
    await show_profile_with_photo(callback, profile, text, keyboard)
    await callback.answer()

@router.callback_query(F.data == "cancel_message", SearchForm.waiting_message)
async def cancel_message(callback: CallbackQuery, state: FSMContext):
    """Отмена отправки сообщения - возврат к текущей анкете"""
    await state.set_state(SearchForm.browsing)
    
    data = await state.get_data()
    if 'message_target_user_id' in data:
        del data['message_target_user_id']
    if 'message_target_index' in data:
        del data['message_target_index']
    await state.set_data(data)
    
    await show_current_profile(callback, state)
    await callback.answer()

@router.message(SearchForm.waiting_message, F.text)
async def process_message_with_like(message: Message, state: FSMContext, db):
    """Обработка сообщения и отправка лайка"""
    user_id = message.from_user.id
    data = await state.get_data()
    
    target_user_id = data.get('message_target_user_id')
    game = data.get('game')
    user_message = message.text.strip()
    
    if not target_user_id or not game:
        await message.answer("Ошибка: данные не найдены")
        await state.clear()
        return
    
    if len(user_message) > 500:
        await message.answer("Сообщение слишком длинное. Максимум 500 символов.")
        return
    
    try:
        await message.bot.delete_message(message.chat.id, message.message_id)
        await message.bot.delete_message(message.chat.id, message.message_id - 1)
    except Exception:
        pass
    
    is_match = await db.add_like(user_id, target_user_id, game, message=user_message)
    
    await notify_about_like(message.bot, target_user_id, game, db)
    
    if is_match:
        target_profile = await db.get_user_profile(target_user_id, game)
        await notify_about_match(message.bot, target_user_id, user_id, game, db)
        
        if target_profile:
            match_text = texts.format_profile(target_profile, show_contact=True)
            text = f"{texts.MATCH_CREATED}\n\n{match_text}"
        else:
            text = texts.MATCH_CREATED
            if target_profile and target_profile.get('username'):
                text += f"\n\n@{target_profile['username']}"
            else:
                text += "\n\n(У пользователя нет @username)"
        
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Продолжить поиск", callback_data="continue_search")],
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
        logger.info(f"Мэтч с сообщением: {user_id} <-> {target_user_id}")
    else:
        logger.info(f"Лайк с сообщением: {user_id} -> {target_user_id}")
        await state.set_state(SearchForm.browsing)
        
        current_index = data.get('current_index', 0)
        await state.update_data(current_index=current_index + 1)
        
        profiles = data.get('profiles', [])
        next_index = current_index + 1
        
        if next_index >= len(profiles):
            await show_search_end(message, state, game)
        else:
            await show_next_search_profile(message, state, db)

async def show_next_search_profile(message: Message, state: FSMContext, db):
    """Показ следующего профиля после отправки сообщения"""
    data = await state.get_data()
    profiles = data.get('profiles', [])
    current_index = data.get('current_index', 0)
    
    if current_index >= len(profiles):
        game = data.get('game')
        await show_search_end(message, state, game)
        return
    
    profile = profiles[current_index]
    profile_text = texts.format_profile(profile)
    text = f"Поиск игроков:\n\n{profile_text}"
    
    keyboard = kb.profile_actions(profile['telegram_id'])
    
    last_message_id = data.get('last_search_message_id')
    if last_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_message_id)
        except Exception:
            pass
    
    if profile.get('photo_id'):
        try:
            sent_msg = await message.answer_photo(
                photo=profile['photo_id'],
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except Exception:
            sent_msg = await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    else:
        sent_msg = await message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    
    await state.update_data(last_search_message_id=sent_msg.message_id)

async def show_search_end(message: Message, state: FSMContext, game: str):
    """Показ сообщения о конце анкет"""
    await state.clear()
    game_name = settings.GAMES.get(game, game)
    text = f"Больше анкет в {game_name} не найдено.\n\nПопробуйте изменить фильтры или вернитесь позже!"
    
    keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
        [kb.InlineKeyboardButton(text="Настроить фильтры", callback_data="search")],
        [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data == "cancel_report")
async def cancel_report(callback: CallbackQuery, state: FSMContext, db):
    """Отмена жалобы"""
    data = await state.get_data()

    await state.set_state(SearchForm.browsing)

    await state.update_data(report_target_user_id=None)

    await callback.answer("Жалоба отменена")

    await show_next_profile(callback, state, db)

@router.message(SearchForm.waiting_report_message)
async def receive_report_message(message: Message, state: FSMContext, db):
    """Получение сообщения жалобы"""
    data = await state.get_data()
    report_message = message.text
    bot = message.bot
    chat_id = message.chat.id
    last_bot_message_id = data.get('last_bot_message_id')

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение пользователя: {e}")

    if not report_message or len(report_message.strip()) < 5:
        text = "Сообщение слишком короткое\n\nОпишите причину жалобы подробнее (минимум 5 символов):"
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Отмена", callback_data="cancel_report")]
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
    game = data.get('game')
    user_id = message.from_user.id

    if not target_user_id or not game:
        text = "Ошибка: данные жалобы не найдены"
        keyboard = kb.InlineKeyboardMarkup(inline_keyboard=[
            [kb.InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
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
            except Exception:
                await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='HTML')
        else:
            await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode='HTML')

        await state.clear()
        return

    success = await db.add_report(user_id, target_user_id, game, report_message)

    await state.set_state(SearchForm.browsing)
    await state.update_data(report_target_user_id=None)

    if success:
        await db._clear_pattern_cache(f"search:{user_id}:{game}:*")
        await notify_admin_new_report(bot, user_id, target_user_id, game)
        logger.info(f"Жалоба добавлена: {user_id} пожаловался на {target_user_id}, причина: {report_message[:50]}")

    notification_text = "Жалоба отправлена модератору!" if success else "Вы уже жаловались на эту анкету"

    if last_bot_message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=last_bot_message_id,
                text=notification_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения: {e}")
            sent = await bot.send_message(chat_id, notification_text, parse_mode='HTML')
            await state.update_data(last_bot_message_id=sent.message_id)
            last_bot_message_id = sent.message_id
    else:
        sent = await bot.send_message(chat_id, notification_text, parse_mode='HTML')
        await state.update_data(last_bot_message_id=sent.message_id)
        last_bot_message_id = sent.message_id

    await asyncio.sleep(0.5)

    class FakeMessage:
        def __init__(self, msg_id, chat, bot_instance):
            self.message_id = msg_id
            self.chat = chat
            self.bot = bot_instance
            self._bot = bot_instance
            self._chat_id = chat.id

        async def delete(self):
            """Удаляет сообщение бота"""
            try:
                await self._bot.delete_message(chat_id=self._chat_id, message_id=self.message_id)
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение {self.message_id}: {e}")

        async def edit_text(self, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
            """Редактирует текст сообщения"""
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
                logger.error(f"Ошибка редактирования сообщения: {e}")

        async def answer_photo(self, photo, caption=None, reply_markup=None, parse_mode=None, **kwargs):
            """Отправляет новое сообщение с фото"""
            return await self._bot.send_photo(
                chat_id=self._chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

        async def answer(self, text, reply_markup=None, parse_mode=None, **kwargs):
            """Отправляет новое текстовое сообщение"""
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

    await show_next_profile(fake_callback, state, db)

@router.message(SearchForm.waiting_message)
async def wrong_message_format(message: Message):
    """Обработка неправильного формата сообщения"""
    await message.answer(
        "Пожалуйста, отправьте текстовое сообщение или нажмите 'Отмена'",
        parse_mode='HTML'
    )