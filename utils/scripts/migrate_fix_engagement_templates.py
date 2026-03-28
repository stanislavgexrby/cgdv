#!/usr/bin/env python3
"""
Миграция: Исправление engagement_templates
- inactive_2h: min_interval_hours 2 → 4 (предотвращаем двойную отправку в окне 2-6ч)
- Шаблон ID=5: исправляем текст (был '{new_profiles} девушек смотрели' — бессмысленно)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FIXED_TEMPLATE_5 = """Тебя не было 3 дня

За это время появилось <b>{new_profiles}</b> новых анкет

Возвращайся — вдруг среди них найдётся твой будущий тиммейт!"""

async def migrate():
    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Исправление engagement_templates")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:
            # Фикс 1: inactive_2h интервал 2h → 4h
            result = await conn.execute(
                "UPDATE engagement_templates SET min_interval_hours = 4 WHERE type = 'inactive_2h'"
            )
            print(f"✅ inactive_2h: min_interval_hours → 4ч ({result})")

            # Фикс 2: шаблон ID=5 — исправляем текст
            old = await conn.fetchval("SELECT LEFT(message_text, 80) FROM engagement_templates WHERE id = 5")
            print(f"   Старый текст: {old}")

            result = await conn.execute(
                "UPDATE engagement_templates SET message_text = $1 WHERE id = 5",
                FIXED_TEMPLATE_5
            )
            print(f"✅ Шаблон ID=5: текст исправлен ({result})")

            # Проверка
            rows = await conn.fetch(
                "SELECT id, type, min_interval_hours, LEFT(message_text, 60) as msg FROM engagement_templates ORDER BY type, id"
            )
            print("\nТекущее состояние шаблонов:")
            for r in rows:
                print(f"  ID={r['id']} type={r['type']} interval={r['min_interval_hours']}h | {r['msg']}")

        print("\n✅ Миграция завершена успешно!")

    except Exception as e:
        print(f"\n❌ Ошибка миграции: {e}")
        raise
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
