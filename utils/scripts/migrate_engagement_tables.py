#!/usr/bin/env python3
"""
Миграция: Создание таблиц engagement_templates и engagement_history
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
    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Таблицы engagement_templates и engagement_history")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS engagement_templates (
                    id SERIAL PRIMARY KEY,
                    type TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    conditions JSONB,
                    min_interval_hours INTEGER DEFAULT 24,
                    priority INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print("✅ Таблица engagement_templates создана (или уже существует)")

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS engagement_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    template_id INTEGER,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data JSONB
                )
            ''')
            print("✅ Таблица engagement_history создана (или уже существует)")

            templates_count = await conn.fetchval("SELECT COUNT(*) FROM engagement_templates")
            history_count = await conn.fetchval("SELECT COUNT(*) FROM engagement_history")
            print(f"\nℹ️  Шаблонов в engagement_templates: {templates_count}")
            print(f"ℹ️  Записей в engagement_history: {history_count}")

        print("\n✅ Миграция завершена успешно!")

    except Exception as e:
        print(f"\n❌ Ошибка миграции: {e}")
        raise
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
