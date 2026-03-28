#!/usr/bin/env python3
"""
Миграция: Финальная чистка шаблонов
- Удаляем new_profiles_match (ID 13): дублирует inactive_3d/inactive_1w по смыслу
- unviewed_likes (ID 12): интервал 24ч → 72ч (не более 1 уведомления в 3 дня)
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
    print("🔧 МИГРАЦИЯ: Финальная чистка шаблонов")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:
            # 1. Удаляем new_profiles_match
            result = await conn.execute(
                "DELETE FROM engagement_templates WHERE type = 'new_profiles_match'"
            )
            print(f"✅ new_profiles_match удалён ({result})")

            # 2. unviewed_likes: интервал 24ч → 72ч
            result = await conn.execute(
                "UPDATE engagement_templates SET min_interval_hours = 72 WHERE type = 'unviewed_likes'"
            )
            print(f"✅ unviewed_likes: min_interval_hours → 72ч ({result})")

            # Итоговое состояние
            rows = await conn.fetch(
                "SELECT id, type, min_interval_hours, conditions, LEFT(message_text, 60) as msg "
                "FROM engagement_templates ORDER BY type, id"
            )
            print("\nИтоговые шаблоны:")
            for r in rows:
                print(f"  ID={r['id']} type={r['type']} interval={r['min_interval_hours']}h")
                print(f"    conditions={r['conditions']}")
                print(f"    text={r['msg']}")

        print("\n✅ Миграция завершена успешно!")

    except Exception as e:
        print(f"\n❌ Ошибка миграции: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(migrate())
