#!/usr/bin/env python3
"""
Скрипт исправления данных last_activity после старой миграции.

Проблема: старая миграция установила last_activity = CURRENT_TIMESTAMP для всех.
Решение: устанавливаем last_activity = created_at для корректной приоритизации.

БЕЗОПАСНО запускать несколько раз - скрипт идемпотентный.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_last_activity():
    """Исправление неправильных значений last_activity"""

    print("=" * 70)
    print("🔧 ИСПРАВЛЕНИЕ ДАННЫХ: last_activity")
    print("=" * 70)

    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        async with db._pg_pool.acquire() as conn:
            # Проверяем существование поля
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'users'
                    AND column_name = 'last_activity'
                )
            """)

            if not exists:
                print("❌ Поле last_activity не существует!")
                print("   Сначала запустите: python migrate_add_last_activity.py")
                return

            # Анализируем текущую ситуацию
            print("📊 Анализ данных...\n")

            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            print(f"Всего пользователей: {total_users}")

            # Пользователи с некорректными данными (last_activity > created_at невозможно)
            invalid_count = await conn.fetchval("""
                SELECT COUNT(*) FROM users
                WHERE last_activity > created_at
            """)

            # Пользователи где last_activity = created_at (уже корректно)
            correct_count = await conn.fetchval("""
                SELECT COUNT(*) FROM users
                WHERE last_activity = created_at
            """)

            # Пользователи где last_activity < created_at (активность после создания)
            updated_count = await conn.fetchval("""
                SELECT COUNT(*) FROM users
                WHERE last_activity < created_at AND last_activity IS NOT NULL
            """)

            print(f"  • С корректными данными (last_activity = created_at): {correct_count}")
            print(f"  • С обновленной активностью (last_activity < created_at): {updated_count}")
            print(f"  • С НЕВОЗМОЖНЫМИ данными (last_activity > created_at): {invalid_count}")

            if invalid_count == 0:
                print("\n✅ Все данные корректны! Исправление не требуется.")
                return

            # Показываем примеры некорректных данных
            print(f"\n⚠️  Найдено {invalid_count} пользователей с некорректными данными")
            print("\nПримеры некорректных записей:")

            samples = await conn.fetch("""
                SELECT
                    telegram_id,
                    created_at,
                    last_activity,
                    EXTRACT(EPOCH FROM (last_activity - created_at)) / 86400 as diff_days
                FROM users
                WHERE last_activity > created_at
                ORDER BY last_activity DESC
                LIMIT 5
            """)

            for row in samples:
                diff = int(row['diff_days'])
                print(f"  • User {row['telegram_id']}: создан {row['created_at'].strftime('%Y-%m-%d %H:%M')}, "
                      f"last_activity {row['last_activity'].strftime('%Y-%m-%d %H:%M')} "
                      f"(+{diff} дней - НЕВОЗМОЖНО)")

            # Спрашиваем подтверждение
            print("\n" + "=" * 70)
            print("🔄 ИСПРАВЛЕНИЕ:")
            print(f"   Для {invalid_count} пользователей будет установлено:")
            print(f"   last_activity = created_at")
            print("=" * 70)

            # В production окружении можно добавить input() для подтверждения
            # response = input("\nПродолжить? (yes/no): ")
            # if response.lower() != 'yes':
            #     print("❌ Отменено")
            #     return

            print("\n⏳ Исправление данных...")

            # Исправляем только некорректные записи
            result = await conn.execute("""
                UPDATE users
                SET last_activity = created_at
                WHERE last_activity > created_at
            """)

            count = int(result.split()[-1]) if result else 0
            print(f"✅ Исправлено {count} записей")

            # Финальная проверка
            remaining_invalid = await conn.fetchval("""
                SELECT COUNT(*) FROM users
                WHERE last_activity > created_at
            """)

            print("\n" + "=" * 70)
            if remaining_invalid == 0:
                print("✅ ИСПРАВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО!")
                print("   Все данные теперь корректны.")
            else:
                print(f"⚠️  Остались некорректные записи: {remaining_invalid}")
            print("=" * 70)

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        logger.exception("Детали ошибки:")
        raise

    finally:
        await db.close()

if __name__ == "__main__":
    try:
        asyncio.run(fix_last_activity())
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
