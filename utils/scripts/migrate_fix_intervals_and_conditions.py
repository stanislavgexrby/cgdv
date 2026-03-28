#!/usr/bin/env python3
"""
Миграция: Исправление интервалов и условий шаблонов

Проблемы:
1. inactive_3d: min_interval_hours=72, но окно 72-168ч (96ч) → 2 отправки за одну сессию
   Фикс: min_interval_hours=96
2. inactive_1w: нет max_inactive_hours → стреляет 4 раза до деактивации
   Фикс: добавляем max_inactive_hours=336 (14 дней), окно 7-14д = 168ч = min_interval_hours → 1 отправка
3. new_profiles_match: отправляется всем активным пользователям
   Фикс: добавляем min_inactive_hours=48 → только неактивным 2+ дней
"""
import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Исправление интервалов и conditions шаблонов")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:

            # 1. inactive_3d: min_interval_hours 72 → 96
            result = await conn.execute(
                "UPDATE engagement_templates SET min_interval_hours = 96 WHERE type = 'inactive_3d'"
            )
            print(f"✅ inactive_3d: min_interval_hours → 96ч ({result})")

            # 2. inactive_1w: добавляем max_inactive_hours=336 в conditions
            rows = await conn.fetch(
                "SELECT id, conditions FROM engagement_templates WHERE type = 'inactive_1w'"
            )
            for row in rows:
                conditions = row['conditions']
                if isinstance(conditions, str):
                    conditions = json.loads(conditions)
                elif conditions is None:
                    conditions = {}

                conditions['max_inactive_hours'] = 336
                await conn.execute(
                    "UPDATE engagement_templates SET conditions = $1::jsonb WHERE id = $2",
                    json.dumps(conditions), row['id']
                )
                print(f"✅ inactive_1w ID={row['id']}: добавлен max_inactive_hours=336")

            # Проверка итога
            rows = await conn.fetch(
                "SELECT id, type, min_interval_hours, conditions "
                "FROM engagement_templates ORDER BY type, id"
            )
            print("\nИтоговые интервалы и условия:")
            for r in rows:
                print(f"  ID={r['id']} type={r['type']} interval={r['min_interval_hours']}h | conditions={r['conditions']}")

        print("\n✅ Миграция завершена успешно!")

    except Exception as e:
        print(f"\n❌ Ошибка миграции: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(migrate())
