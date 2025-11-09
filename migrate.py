#!/usr/bin/env python3
"""
Безопасная миграция: добавление таблицы ad_posts для рекламных постов
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def migrate():
    """Безопасная миграция: добавление таблицы ad_posts"""
    
    connection_url = (
        f"postgresql://"
        f"{os.getenv('DB_USER')}:"
        f"{os.getenv('DB_PASSWORD')}@"
        f"{os.getenv('DB_HOST')}:"
        f"{os.getenv('DB_PORT')}/"
        f"{os.getenv('DB_NAME')}"
    )
    
    print("🔌 Подключение к базе данных...")
    conn = await asyncpg.connect(connection_url)
    
    try:
        # 1. Проверяем существует ли уже таблица
        print("\n🔍 Проверка существования таблицы 'ad_posts'...")
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_name = 'ad_posts'
            )
        """)
        
        if exists:
            print("✅ Таблица 'ad_posts' уже существует. Миграция не требуется.")
            return
        
        # 2. Показываем текущие таблицы
        print("\n📊 Текущие таблицы в БД:")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        for table in tables:
            print(f"  - {table['table_name']}")
        
        # 3. Подтверждение
        print("\n⚠️  Будет создана новая таблица 'ad_posts':")
        print("""
    CREATE TABLE ad_posts (
        id SERIAL PRIMARY KEY,
        message_id BIGINT NOT NULL,
        chat_id BIGINT NOT NULL,
        caption TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by BIGINT,
        show_interval INTEGER DEFAULT 3
    )
        """)
        print("\n   Это безопасная операция, которая:")
        print("   - Создаст новую таблицу без изменения существующих")
        print("   - Не затронет данные пользователей")
        print("   - Займет менее 1 секунды")
        
        confirm = input("\n❓ Продолжить? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Миграция отменена пользователем")
            return
        
        # 4. Выполняем миграцию
        print("\n⏳ Создание таблицы ad_posts...")
        await conn.execute('''
            CREATE TABLE ad_posts (
                id SERIAL PRIMARY KEY,
                message_id BIGINT NOT NULL,
                chat_id BIGINT NOT NULL,
                caption TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by BIGINT,
                show_interval INTEGER DEFAULT 3
            )
        ''')
        print("✅ Таблица 'ad_posts' успешно создана!")
        
        # 5. Создаем индексы для производительности
        print("\n⏳ Создание индексов...")
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_ad_posts_active 
            ON ad_posts(is_active) 
            WHERE is_active = TRUE
        ''')
        print("✅ Индексы созданы!")
        
        # 6. Проверяем результат
        print("\n🔍 Проверка результата...")
        new_table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_name = 'ad_posts'
            )
        """)
        
        if new_table_exists:
            print("✅ Таблица успешно создана и доступна!")
            
            # Показываем структуру
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'ad_posts'
                ORDER BY ordinal_position
            """)
            print("\n📊 Структура таблицы 'ad_posts':")
            for col in columns:
                print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
        
        print("\n✅ Миграция успешно завершена!")
        print("📝 Теперь можно перезапустить бота")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА при выполнении миграции: {e}")
        print("💡 База данных не была изменена")
        raise
    
    finally:
        await conn.close()
        print("\n🔌 Соединение с БД закрыто")

if __name__ == "__main__":
    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Добавление таблицы ad_posts для рекламных постов")
    print("=" * 70)
    
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        exit(1)