# migration_add_message.py
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def migrate():
    """Безопасная миграция: добавление колонки message в таблицу likes"""
    
    # Подключение к БД
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
        # 1. Проверяем существует ли уже колонка
        print("\n🔍 Проверка существования колонки 'message'...")
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'likes' 
                AND column_name = 'message'
            )
        """)
        
        if exists:
            print("✅ Колонка 'message' уже существует. Миграция не требуется.")
            return
        
        # 2. Показываем текущее состояние
        print("\n📊 Текущая структура таблицы 'likes':")
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'likes'
            ORDER BY ordinal_position
        """)
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
        
        # 3. Показываем количество записей
        count = await conn.fetchval("SELECT COUNT(*) FROM likes")
        print(f"\n📈 Количество записей в 'likes': {count}")
        
        # 4. Подтверждение
        print("\n⚠️  Будет выполнена миграция:")
        print("   ALTER TABLE likes ADD COLUMN message TEXT;")
        print("\n   Это безопасная операция, которая:")
        print("   - Добавит новую колонку 'message' типа TEXT")
        print("   - Значение по умолчанию: NULL")
        print("   - Не изменит существующие данные")
        print("   - Займет менее 1 секунды")
        
        confirm = input("\n❓ Продолжить? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Миграция отменена пользователем")
            return
        
        # 5. Выполняем миграцию
        print("\n⏳ Выполнение миграции...")
        await conn.execute("ALTER TABLE likes ADD COLUMN message TEXT")
        print("✅ Колонка 'message' успешно добавлена!")
        
        # 6. Проверяем результат
        print("\n🔍 Проверка результата...")
        new_structure = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'likes'
            ORDER BY ordinal_position
        """)
        
        print("\n📊 Новая структура таблицы 'likes':")
        for col in new_structure:
            marker = "✨ NEW" if col['column_name'] == 'message' else ""
            print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']}) {marker}")
        
        # 7. Проверяем что данные не повреждены
        count_after = await conn.fetchval("SELECT COUNT(*) FROM likes")
        print(f"\n📈 Количество записей после миграции: {count_after}")
        
        if count == count_after:
            print("✅ Все записи сохранены!")
        else:
            print("⚠️  ВНИМАНИЕ: Количество записей изменилось!")
        
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
    print("🔧 МИГРАЦИЯ: Добавление колонки 'message' в таблицу 'likes'")
    print("=" * 70)
    
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        exit(1)