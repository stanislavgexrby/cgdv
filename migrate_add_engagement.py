#!/usr/bin/env python3
"""
Миграция: Добавление таблиц для автоматических engagement-уведомлений
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    """Добавление таблиц engagement_templates и engagement_history"""

    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Добавление системы автоматических уведомлений")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:
            # 1. Создание таблицы engagement_templates
            print("⏳ Создание таблицы engagement_templates...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS engagement_templates (
                    id SERIAL PRIMARY KEY,
                    type TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    min_interval_hours INTEGER DEFAULT 24,
                    priority INTEGER DEFAULT 0,
                    conditions JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ Таблица engagement_templates создана")

            # 2. Создание таблицы engagement_history
            print("\n⏳ Создание таблицы engagement_history...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS engagement_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    template_id INTEGER REFERENCES engagement_templates(id) ON DELETE CASCADE,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data JSONB,
                    CONSTRAINT engagement_history_user_template UNIQUE (user_id, template_id, sent_at)
                )
            """)
            print("✅ Таблица engagement_history создана")

            # 3. Создание индексов
            print("\n⏳ Создание индексов...")

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_engagement_templates_type
                ON engagement_templates(type)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_engagement_templates_active
                ON engagement_templates(is_active)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_engagement_history_user_id
                ON engagement_history(user_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_engagement_history_sent_at
                ON engagement_history(sent_at DESC)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_engagement_history_template
                ON engagement_history(template_id, user_id)
            """)

            print("✅ Индексы созданы")

            # 4. Добавление базовых шаблонов
            print("\n⏳ Добавление базовых шаблонов...")

            templates = [
                # inactive_2h - варианты для 2-6 часов неактивности
                {
                    'type': 'inactive_2h',
                    'message': 'Тебя не было пару часов\n\nЗа это время появились новые анкеты — может среди них найдется кто-то интересный?',
                    'interval': 2,
                    'priority': 1,
                    'conditions': {'min_inactive_hours': 2, 'max_inactive_hours': 6}
                },
                {
                    'type': 'inactive_2h',
                    'message': 'Давно не виделись!\n\nПока тебя не было, появилось несколько новых анкет\n\n Глянь, вдруг среди них найдется твой идеальный тиммейт',
                    'interval': 2,
                    'priority': 1,
                    'conditions': {'min_inactive_hours': 2, 'max_inactive_hours': 6}
                },
                {
                    'type': 'inactive_2h',
                    'message': 'Пропустил несколько часов активности\n\nВ боте появились новые игроки, которые тоже ищут команду',
                    'interval': 2,
                    'priority': 1,
                    'conditions': {'min_inactive_hours': 2, 'max_inactive_hours': 6}
                },

                # inactive_3d - варианты для 3 дней неактивности
                {
                    'type': 'inactive_3d',
                    'message': 'Тебя не было 3 дня\n\nЗа это время появилось <b>{new_profiles}</b> новых анкет\n\nВозвращайся, проверь что нового',
                    'interval': 72,
                    'priority': 3,
                    'conditions': {'min_inactive_hours': 72, 'max_inactive_hours': 168}
                },
                {
                    'type': 'inactive_3d',
                    'message': 'Пока тебя не было <b>{new_profiles}</b> девушек смотрели твою анкету\n\n Может быть, среди них есть твой будущий тиммейт',
                    'interval': 72,
                    'priority': 3,
                    'conditions': {'min_inactive_hours': 72, 'max_inactive_hours': 168}
                },
                {
                    'type': 'inactive_3d',
                    'message': 'Прошло 3 дня с последнего визита\n\n<b>{new_profiles}</b> новых игроков присоединились к поиску\n\n Не упусти возможность найти классную команду',
                    'interval': 72,
                    'priority': 3,
                    'conditions': {'min_inactive_hours': 72, 'max_inactive_hours': 168}
                },

                # inactive_1w - варианты для недели неактивности
                {
                    'type': 'inactive_1w',
                    'message': 'Прошла неделя с последнего визита\n\nПока ты отсутствовал:\n• <b>{new_profiles}</b> игроков ищут тиммейтов\n• <b>{unviewed_likes}</b> человек оценили твою анкету\n\nНе упусти свой шанс',
                    'interval': 168,
                    'priority': 4,
                    'conditions': {'min_inactive_hours': 168, 'max_inactive_hours': 336}
                },
                {
                    'type': 'inactive_1w',
                    'message': 'Целая неделя без тебя!\n\nВот что произошло:\n• <b>{new_profiles}</b> новых анкет\n• <b>{unviewed_likes}</b> лайков на твоей анкете\n\nПора возвращаться и проверить, кто там тебя ждет',
                    'interval': 168,
                    'priority': 4,
                    'conditions': {'min_inactive_hours': 168, 'max_inactive_hours': 336}
                },
                {
                    'type': 'inactive_1w',
                    'message': 'Твой профиль просмотрели <b>{unviewed_likes}</b> человек',
                    'interval': 168,
                    'priority': 4,
                    'conditions': {'min_inactive_hours': 168, 'max_inactive_hours': 336}
                },

                # inactive_1m - варианты для месяца неактивности
                {
                    'type': 'inactive_1m',
                    'message': 'Целый месяц без посещения\n\nЗа месяц в боте:\n• <b>{new_profiles}</b> новых пользователей\n• <b>{unviewed_likes}</b> непросмотренных лайков\n\nВозвращайся, если ещё актуально',
                    'interval': 720,
                    'priority': 6,
                    'conditions': {'min_inactive_hours': 720}
                },
                {
                    'type': 'inactive_1m',
                    'message': 'Месяц — это долго!\n\nМногое изменилось за это время:\n• <b>{new_profiles}</b> новых игроков в поиске\n• <b>{unviewed_likes}</b> оценок твоей анкеты\n\nЕсли всё ещё ищешь команду — заходи, посмотри что нового',
                    'interval': 720,
                    'priority': 6,
                    'conditions': {'min_inactive_hours': 720}
                },

                # unviewed_likes - непросмотренные лайки
                {
                    'type': 'unviewed_likes',
                    'message': 'У тебя <b>{count}</b> непросмотренных лайков\n\nКто-то оценил твою анкету — проверь, может это взаимно',
                    'interval': 48,
                    'priority': 10,
                    'conditions': {'min_unviewed_likes': 1}
                },

                # new_profiles_match - новые подходящие анкеты
                {
                    'type': 'new_profiles_match',
                    'message': 'За последнюю неделю <b>{count}</b> новых игроков присоединились к поиску\n\nВозможно среди них есть подходящие тиммейты — посмотри их анкеты',
                    'interval': 168,
                    'priority': 8,
                    'conditions': {'min_new_profiles': 5}
                }
            ]

            for tpl in templates:
                await conn.execute("""
                    INSERT INTO engagement_templates
                    (type, message_text, min_interval_hours, priority, conditions, is_active)
                    VALUES ($1, $2, $3, $4, $5::jsonb, true)
                """, tpl['type'], tpl['message'], tpl['interval'], tpl['priority'],
                    str(tpl['conditions']).replace("'", '"'))

            print("✅ Базовые шаблоны добавлены")

        print("\n" + "=" * 70)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 70)
        print("\nСозданы таблицы:")
        print("  • engagement_templates - шаблоны уведомлений")
        print("  • engagement_history - история отправки")
        print("\nДобавлены базовые шаблоны:")
        print("  • Неактивность: 1ч, 3д, 1нед, 2нед, 1мес")
        print("  • Непросмотренные лайки")
        print("  • Новые подходящие анкеты")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        logger.exception("Детали ошибки:")
        raise

    finally:
        await db.close()

if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
