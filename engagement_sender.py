#!/usr/bin/env python3
"""
Автоматическая отправка engagement-уведомлений пользователям

Этот скрипт запускается периодически (например, каждые 30 минут через cron)
и отправляет уведомления пользователям согласно настроенным шаблонам.
"""
import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from database.database import Database
from aiogram import Bot
import config.settings as settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EngagementSender:
    """Класс для отправки engagement-уведомлений"""

    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.sent_count = 0
        self.failed_count = 0

    async def send_engagement_notifications(self):
        """Основной метод отправки всех engagement-уведомлений"""
        import random

        logger.info("=" * 60)
        logger.info("🚀 Запуск отправки engagement-уведомлений")
        logger.info(f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        try:
            # Получаем все активные шаблоны
            templates = await self.db.get_active_engagement_templates()

            if not templates:
                logger.info("ℹ️  Нет активных шаблонов для отправки")
                return

            logger.info(f"📋 Найдено активных шаблонов: {len(templates)}")

            # Группируем шаблоны по типу
            templates_by_type = {}
            for template in templates:
                template_type = template['type']
                if template_type not in templates_by_type:
                    templates_by_type[template_type] = []
                templates_by_type[template_type].append(template)

            logger.info(f"🔀 Типов шаблонов: {len(templates_by_type)}")

            # Обрабатываем каждый тип шаблона
            for template_type, template_variants in templates_by_type.items():
                await self._process_template_type(template_type, template_variants)

            logger.info("\n" + "=" * 60)
            logger.info(f"✅ Отправка завершена")
            logger.info(f"📊 Отправлено: {self.sent_count}")
            logger.info(f"❌ Ошибок: {self.failed_count}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ Критическая ошибка при отправке: {e}", exc_info=True)

    async def _process_template_type(self, template_type: str, template_variants: list):
        """Обработка группы шаблонов одного типа с рандомным выбором варианта для каждого пользователя

        Args:
            template_type: Тип шаблона (например, 'inactive_2h')
            template_variants: Список вариантов шаблонов этого типа
        """
        import random

        logger.info(f"\n🔄 Обработка типа: {template_type} ({len(template_variants)} вариантов)")

        try:
            # Используем первый шаблон для получения списка пользователей
            # (условия одинаковые для всех вариантов одного типа)
            reference_template = template_variants[0]
            users = await self.db.get_users_for_engagement(reference_template)

            if not users:
                logger.info(f"   ℹ️  Нет пользователей для отправки")
                return

            logger.info(f"   👥 Найдено пользователей: {len(users)}")

            # Отправляем уведомления
            sent_in_template = 0
            failed_in_template = 0

            for user_id in users:
                # Выбираем случайный вариант шаблона для этого пользователя
                chosen_template = random.choice(template_variants)

                success = await self._send_to_user(user_id, chosen_template)

                if success:
                    sent_in_template += 1
                    self.sent_count += 1
                else:
                    failed_in_template += 1
                    self.failed_count += 1

                # Небольшая задержка между отправками
                await asyncio.sleep(0.05)

            logger.info(f"   ✅ Отправлено: {sent_in_template}, ❌ Ошибок: {failed_in_template}")

        except Exception as e:
            logger.error(f"   ❌ Ошибка обработки типа {template_type}: {e}")

    async def _send_to_user(self, user_id: int, template: dict) -> bool:
        """Отправка уведомления одному пользователю"""
        try:
            # Форматируем сообщение с данными пользователя
            message = await self.db.format_engagement_message(template, user_id)

            # Отправляем сообщение
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML'
            )

            # Сохраняем в историю
            await self.db.add_engagement_history(
                user_id=user_id,
                template_id=template['id'],
                data={'message': message[:200]}  # Сохраняем начало сообщения
            )

            return True

        except Exception as e:
            error_msg = str(e).lower()

            # Логируем только серьезные ошибки (не блокировки)
            if 'blocked' not in error_msg and 'bot was blocked' not in error_msg:
                logger.warning(f"   ⚠️  Ошибка отправки пользователю {user_id}: {e}")

            return False


async def main():
    """Главная функция"""
    logger.info("🤖 Инициализация бота и БД...")

    # Инициализируем бота
    bot = Bot(token=settings.BOT_TOKEN)

    # Инициализируем БД
    db = Database()
    await db.init()

    try:
        # Создаем sender и запускаем отправку
        sender = EngagementSender(bot, db)
        await sender.send_engagement_notifications()

    finally:
        # Закрываем соединения
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Прервано пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
