#!/usr/bin/env python3
"""
Скрипт для очистки кэша поиска после обновления алгоритма
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def clear_search_cache():
    """Очистка всего кэша поиска"""

    print("=" * 70)
    print("🧹 ОЧИСТКА КЭША ПОИСКА")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        # Очищаем все ключи кэша поиска
        print("⏳ Поиск ключей кэша поиска...")

        # Используем SCAN для поиска всех ключей search:*
        # SCAN лучше чем KEYS, т.к. не блокирует Redis
        cursor = 0
        deleted_count = 0
        batch_count = 0

        while True:
            cursor, keys = await db._redis.scan(cursor=cursor, match="search:*", count=100)

            if keys:
                # Удаляем найденные ключи
                deleted = await db._redis.delete(*keys)
                deleted_count += deleted
                batch_count += 1
                print(f"  Батч {batch_count}: удалено {deleted} ключей...")

            # Когда cursor == 0, итерация завершена
            if not cursor:
                break

        if deleted_count > 0:
            print(f"\n✅ Очищено {deleted_count} ключей кэша поиска")
        else:
            print(f"\n⚠️  Ключи кэша поиска не найдены (уже чистый кэш)")

        # Также очищаем кэш профилей для перезагрузки данных
        print("\n⏳ Очистка кэша профилей...")
        cursor = 0
        profile_deleted = 0
        batch_count = 0

        while True:
            cursor, keys = await db._redis.scan(cursor=cursor, match="profile:*", count=100)

            if keys:
                deleted = await db._redis.delete(*keys)
                profile_deleted += deleted
                batch_count += 1

            if not cursor:
                break

        if profile_deleted > 0:
            print(f"✅ Очищено {profile_deleted} ключей кэша профилей")
        else:
            print(f"⚠️  Ключи кэша профилей не найдены")

        print("\n" + "=" * 70)
        print("✅ КЭШИ УСПЕШНО ОЧИЩЕНЫ!")
        print("=" * 70)
        print("\nПоиск анкет теперь будет использовать новый алгоритм.")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        logger.exception("Детали ошибки:")
        raise

    finally:
        await db.close()

if __name__ == "__main__":
    try:
        asyncio.run(clear_search_cache())
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
