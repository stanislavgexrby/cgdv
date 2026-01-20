#!/usr/bin/env python3
"""
Миграция: Добавление таблиц для системы рассылок (broadcasts)
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
    """Добавление таблиц broadcasts и broadcast_stats"""

    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Добавление системы рассылок")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:
            # 1. Создание таблицы broadcasts
            print("⏳ Создание таблицы broadcasts...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id SERIAL PRIMARY KEY,
                    message_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    caption TEXT NOT NULL,
                    created_by BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent_at TIMESTAMP,
                    status TEXT DEFAULT 'draft',
                    broadcast_type TEXT DEFAULT 'copy',
                    target_games TEXT[] DEFAULT ARRAY['dota', 'cs'],
                    target_regions TEXT[] DEFAULT ARRAY['all'],
                    target_purposes TEXT[],
                    total_recipients INTEGER DEFAULT 0,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    CONSTRAINT broadcasts_status_check CHECK (status IN ('draft', 'sending', 'completed', 'failed')),
                    CONSTRAINT broadcasts_type_check CHECK (broadcast_type IN ('copy', 'forward'))
                )
            """)
            print("✅ Таблица broadcasts создана")

            # 2. Создание таблицы broadcast_stats
            print("\n⏳ Создание таблицы broadcast_stats...")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_stats (
                    id SERIAL PRIMARY KEY,
                    broadcast_id INTEGER REFERENCES broadcasts(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    status TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    error_message TEXT,
                    CONSTRAINT broadcast_stats_status_check CHECK (status IN ('sent', 'failed', 'blocked'))
                )
            """)
            print("✅ Таблица broadcast_stats создана")

            # 3. Создание индексов
            print("\n⏳ Создание индексов...")

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_broadcasts_created_at
                ON broadcasts(created_at DESC)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_broadcasts_status
                ON broadcasts(status)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_broadcasts_created_by
                ON broadcasts(created_by)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_broadcast_stats_broadcast_id
                ON broadcast_stats(broadcast_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_broadcast_stats_user_id
                ON broadcast_stats(user_id)
            """)

            print("✅ Индексы созданы")

        print("\n" + "=" * 70)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 70)
        print("\nСозданы таблицы:")
        print("  • broadcasts - хранение рассылок")
        print("  • broadcast_stats - статистика отправки")
        print("\nДобавлены индексы для оптимизации запросов")

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
