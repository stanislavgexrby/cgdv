#!/usr/bin/env python3
"""
Миграция: Добавление поля last_activity в таблицу users
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
    """Добавление поля last_activity"""
    
    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Добавление last_activity")
    print("=" * 70)
    
    db = Database()
    
    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")
        
        async with db._pg_pool.acquire() as conn:
            # Проверяем, существует ли уже поле
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'users' 
                    AND column_name = 'last_activity'
                )
            """)
            
            if exists:
                print("⚠️  Поле last_activity уже существует")
                return
            
            print("⏳ Добавление поля last_activity...")
            await conn.execute("""
                ALTER TABLE users 
                ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
            
            print("✅ Поле добавлено")
            
            # Обновляем существующих пользователей (ставим текущее время)
            print("\n⏳ Обновление существующих пользователей...")
            result = await conn.execute("""
                UPDATE users 
                SET last_activity = CURRENT_TIMESTAMP 
                WHERE last_activity IS NULL
            """)
            
            count = int(result.split()[-1]) if result else 0
            print(f"✅ Обновлено {count} пользователей")
            
            # Создаем индекс для быстрого поиска
            print("\n⏳ Создание индекса...")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_last_activity 
                ON users(last_activity DESC)
            """)
            
            print("✅ Индекс создан")
        
        print("\n" + "=" * 70)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 70)
        
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