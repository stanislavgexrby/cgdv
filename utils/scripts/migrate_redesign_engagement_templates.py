#!/usr/bin/env python3
"""
Миграция: Переработка engagement_templates
- Удаляем inactive_2h и inactive_1m (по type)
- Обновляем тексты inactive_3d (3 варианта, по порядку ID)
- Обновляем тексты inactive_1w (3 варианта, по порядку ID)
- Обновляем unviewed_likes: убираем {count}
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEXTS_INACTIVE_3D = [
    "Тебя не было 3 дня\n\nЗа это время {profile_views} человек просматривали анкеты в поиске\n\nВозможно среди них есть подходящий тиммейт",
    "Ты не заходил 3 дня\n\n{profile_views} игроков просматривали анкеты пока тебя не было\n\nВозможно среди них есть подходящий тиммейт",
    "За 3 дня твоего отсутствия в боте появились {profile_views} новых игроков\n\nОни тоже ищут команду — не упусти момент",
]

TEXTS_INACTIVE_1W = [
    "Ты не заходил уже неделю\n\nЗа это время {profile_views} человек искали тиммейта в боте\n\nВернись и проверь — среди них может быть подходящий вариант",
    "Прошла неделя с последнего визита\n\n{profile_views} игроков просматривали анкеты пока тебя не было\n\nТвоя анкета ждёт",
    "За неделю в боте было {profile_views} человек в поиске\n\nВозвращайся — твоя анкета по-прежнему активна",
]

TEXT_UNVIEWED_LIKES = "У тебя есть непросмотренные лайки\n\nКто-то оценил твою анкету — проверь, может это взаимно"


async def migrate():
    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Переработка engagement_templates")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:
            # 1. Удаляем inactive_2h и inactive_1m по type (не по ID)
            result = await conn.execute(
                "DELETE FROM engagement_templates WHERE type IN ('inactive_2h', 'inactive_1m')"
            )
            print(f"✅ Удалены inactive_2h и inactive_1m: {result}")

            # 2. Обновляем тексты inactive_3d по порядку ID
            rows = await conn.fetch(
                "SELECT id FROM engagement_templates WHERE type = 'inactive_3d' ORDER BY id"
            )
            ids = [r['id'] for r in rows]
            if len(ids) != 3:
                print(f"⚠️  inactive_3d: ожидалось 3 шаблона, найдено {len(ids)}: {ids}")
            for i, text in enumerate(TEXTS_INACTIVE_3D):
                if i >= len(ids):
                    break
                r = await conn.execute(
                    "UPDATE engagement_templates SET message_text = $1 WHERE id = $2",
                    text, ids[i]
                )
                print(f"✅ inactive_3d ID={ids[i]}: {r}")

            # 3. Обновляем тексты inactive_1w по порядку ID
            rows = await conn.fetch(
                "SELECT id FROM engagement_templates WHERE type = 'inactive_1w' ORDER BY id"
            )
            ids = [r['id'] for r in rows]
            if len(ids) != 3:
                print(f"⚠️  inactive_1w: ожидалось 3 шаблона, найдено {len(ids)}: {ids}")
            for i, text in enumerate(TEXTS_INACTIVE_1W):
                if i >= len(ids):
                    break
                r = await conn.execute(
                    "UPDATE engagement_templates SET message_text = $1 WHERE id = $2",
                    text, ids[i]
                )
                print(f"✅ inactive_1w ID={ids[i]}: {r}")

            # 4. Обновляем unviewed_likes по type (1 шаблон)
            r = await conn.execute(
                "UPDATE engagement_templates SET message_text = $1 WHERE type = 'unviewed_likes'",
                TEXT_UNVIEWED_LIKES
            )
            print(f"✅ unviewed_likes: {r}")

            # Итоговое состояние
            rows = await conn.fetch(
                "SELECT id, type, min_interval_hours, LEFT(message_text, 70) as msg "
                "FROM engagement_templates ORDER BY type, id"
            )
            print("\nИтоговые шаблоны:")
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
