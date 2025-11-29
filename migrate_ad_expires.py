#!/usr/bin/env python3
"""
Безопасная миграция: добавление поля expires_at в ad_posts для автоудаления
Использует существующий класс Database
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    """Миграция через Database класс"""

    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Добавление expires_at в ad_posts для срока действия")
    print("=" * 70)

    # Инициализируем Database
    print("\n🔌 Подключение к базе данных...")
    db = Database()

    try:
        await db.init()
        print("✅ Подключение установлено\n")

        async with db._pg_pool.acquire() as conn:
            # Проверяем существование колонки expires_at
            print("🔍 Проверка существования колонки 'expires_at'...")
            expires_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'ad_posts' AND column_name = 'expires_at'
                )
            """)

            if expires_exists:
                print("✅ Колонка 'expires_at' уже существует")
            else:
                print("⚠️  Колонка 'expires_at' не найдена\n")

                # Показываем что будет сделано
                print("📋 Будет выполнено:")
                print("   ALTER TABLE ad_posts ADD COLUMN expires_at TIMESTAMP DEFAULT NULL")
                print()
                print("   Это безопасная операция:")
                print("   - Добавляется новая nullable колонка")
                print("   - Существующие данные не изменяются")
                print("   - NULL означает, что реклама бессрочная")
                print("   - При создании можно указать дату окончания")
                print()

                # Подтверждение
                confirm = input("❓ Продолжить миграцию? (yes/no): ").strip().lower()

                if confirm != 'yes':
                    print("❌ Миграция отменена пользователем")
                    return

                # Выполняем миграцию
                print("\n⏳ Выполнение миграции...")

                print("   Добавление колонки expires_at...")
                await conn.execute("""
                    ALTER TABLE ad_posts
                    ADD COLUMN expires_at TIMESTAMP DEFAULT NULL
                """)
                print("   ✅ Колонка добавлена")

                print("\n✅ Миграция успешно завершена!")

            # Проверяем результат
            print("\n🔍 Проверка результата...")
            columns = await conn.fetch("""
                SELECT column_name, data_type, column_default, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'ad_posts'
                ORDER BY ordinal_position
            """)

            print("\n📊 Структура таблицы ad_posts:")
            for col in columns:
                default = col['column_default'] or 'NULL'
                nullable = "YES" if col['is_nullable'] == 'YES' else "NO"
                data_type = col['data_type']
                if data_type == 'USER-DEFINED':
                    # Получаем реальное имя типа
                    udt_name = await conn.fetchval("""
                        SELECT udt_name
                        FROM information_schema.columns
                        WHERE table_name = 'ad_posts' AND column_name = $1
                    """, col['column_name'])
                    data_type = f"{data_type} ({udt_name})"
                print(f"  - {col['column_name']:20} | {data_type:30} | NULL: {nullable} | DEFAULT: {default}")

            # Показываем текущие рекламы
            ads_count = await conn.fetchval("SELECT COUNT(*) FROM ad_posts")
            if ads_count > 0:
                print(f"\n📢 В базе {ads_count} рекламных постов")
                print("   Все они имеют expires_at = NULL (бессрочные)")
            else:
                print("\n📢 Рекламных постов пока нет")

            print("\n✅ Миграция завершена!")
            print("🚀 Теперь можно перезапустить бота")
            print("\n📝 Новые возможности:")
            print("   - При создании рекламы можно указать срок действия")
            print("   - Доступные сроки: 1 день, 3 дня, 7 дней, 14 дней, 30 дней, бессрочно")
            print("   - Истекшие рекламы автоматически удаляются")

    except Exception as e:
        print(f"\n❌ ОШИБКА при выполнении миграции: {e}")
        logger.exception("Детали ошибки:")
        raise

    finally:
        print("\n🔌 Закрытие соединения...")
        await db.close()
        print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
