#!/usr/bin/env python3
"""
Безопасная миграция: добавление поля games в ad_posts
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
    
    print("=" * 60)
    print("🔧 МИГРАЦИЯ: Добавление games в ad_posts")
    print("=" * 60)
    
    # Инициализируем Database
    print("\n🔌 Подключение к базе данных...")
    db = Database()
    
    try:
        await db.init()
        print("✅ Подключение установлено\n")
        
        # Проверяем существование колонки
        print("🔍 Проверка существования колонки 'games'...")
        async with db._pg_pool.acquire() as conn:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'ad_posts' AND column_name = 'games'
                )
            """)
            
            if exists:
                print("✅ Колонка 'games' уже существует")
                print("📊 Миграция не требуется\n")
                return
            
            print("⚠️  Колонка 'games' не найдена\n")
            
            # Показываем что будет сделано
            print("📋 Будет выполнено:")
            print("   ALTER TABLE ad_posts")
            print("   ADD COLUMN games TEXT[] DEFAULT ARRAY['dota', 'cs']::TEXT[]")
            print()
            print("   Это безопасная операция:")
            print("   - Добавляется новая колонка")
            print("   - Существующие данные не изменяются")
            print("   - Все существующие рекламы будут показываться в обеих играх")
            print()
            
            # Подтверждение
            confirm = input("❓ Продолжить миграцию? (yes/no): ").strip().lower()
            
            if confirm != 'yes':
                print("❌ Миграция отменена пользователем")
                return
            
            # Выполняем миграцию
            print("\n⏳ Выполнение миграции...")
            await conn.execute("""
                ALTER TABLE ad_posts 
                ADD COLUMN games TEXT[] DEFAULT ARRAY['dota', 'cs']::TEXT[]
            """)
            
            print("✅ Колонка успешно добавлена!")
            
            # Проверяем результат
            print("\n🔍 Проверка результата...")
            columns = await conn.fetch("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'ad_posts'
                ORDER BY ordinal_position
            """)
            
            print("\n📊 Структура таблицы ad_posts:")
            for col in columns:
                default = col['column_default'] or 'NULL'
                print(f"  - {col['column_name']:20} | {col['data_type']:15} | DEFAULT: {default}")
            
            # Показываем текущие рекламы
            ads_count = await conn.fetchval("SELECT COUNT(*) FROM ad_posts")
            if ads_count > 0:
                print(f"\n📢 В базе {ads_count} рекламных постов")
                print("   Все они теперь будут показываться в обеих играх (dota, cs)")
            else:
                print("\n📢 Рекламных постов пока нет")
            
            print("\n✅ Миграция успешно завершена!")
            print("🚀 Теперь можно перезапустить бота")
            
    except Exception as e:
        print(f"\n❌ ОШИБКА при выполнении миграции: {e}")
        logger.exception("Детали ошибки:")
        raise
    
    finally:
        print("\n🔌 Закрытие соединения...")
        await db.close()
        print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)