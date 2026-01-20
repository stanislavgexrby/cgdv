#!/usr/bin/env python3
"""
Миграция: Удаление UNIQUE constraint с type в engagement_templates
Это позволит иметь несколько вариантов шаблонов для одного типа
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
    """Удаление UNIQUE constraint с type"""

    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Удаление UNIQUE constraint с type")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:
            # 1. Проверяем, существует ли constraint
            print("⏳ Проверка существующих constraints...")
            constraint_exists = await conn.fetchval("""
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE conname = 'engagement_templates_type_key'
            """)

            if constraint_exists:
                print("📌 Найден UNIQUE constraint на type, удаляем...")
                await conn.execute("""
                    ALTER TABLE engagement_templates
                    DROP CONSTRAINT IF EXISTS engagement_templates_type_key
                """)
                print("✅ UNIQUE constraint удален")
            else:
                print("ℹ️  UNIQUE constraint не найден (возможно, уже был удален)")

            # 2. Создаем индекс для быстрого поиска по type (не уникальный)
            print("\n⏳ Создание индекса для type...")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_engagement_templates_type_active
                ON engagement_templates(type, is_active)
            """)
            print("✅ Индекс создан")

        print("\n" + "=" * 70)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 70)
        print("\nТеперь можно добавлять несколько вариантов шаблонов для одного типа")
        print("Запустите migrate_add_engagement.py для добавления новых вариантов")

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
