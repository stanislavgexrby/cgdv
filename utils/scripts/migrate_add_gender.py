#!/usr/bin/env python3
"""
Миграция: Добавление поля gender в таблицу profiles
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    """Добавление колонки gender в profiles"""

    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Добавление поля gender в profiles")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:
            # Добавляем колонку gender
            await conn.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS gender TEXT")
            print("✅ Колонка gender добавлена в profiles")

            # Проверяем количество профилей без пола
            count = await conn.fetchval("SELECT COUNT(*) FROM profiles WHERE gender IS NULL")
            print(f"ℹ️  Профилей без указанного пола: {count}")

        print("\n✅ Миграция завершена успешно!")

    except Exception as e:
        print(f"\n❌ Ошибка миграции: {e}")
        raise
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
