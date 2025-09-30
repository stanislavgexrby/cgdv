import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def migrate():
    """Добавление поля role в таблицу profiles"""
    
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'teammates')
    db_user = os.getenv('DB_USER', 'teammates_user')
    db_password = os.getenv('DB_PASSWORD', '')
    
    connection_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    conn = await asyncpg.connect(connection_url)
    
    try:
        print("\n" + "="*70)
        print("🔧 МИГРАЦИЯ: Добавление поля 'role' в таблицу 'profiles'")
        print("="*70)
        
        # 1. Проверяем текущую структуру
        print("\n🔍 Проверка текущей структуры таблицы 'profiles'...")
        columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns
            WHERE table_name = 'profiles'
            ORDER BY ordinal_position
        """)
        
        print("\n📋 Текущие колонки:")
        has_role = False
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']}")
            if col['column_name'] == 'role':
                has_role = True
        
        if has_role:
            print("\n⚠️  Колонка 'role' уже существует!")
            return
        
        # 2. Считаем записи
        count = await conn.fetchval("SELECT COUNT(*) FROM profiles")
        print(f"\n📊 Найдено записей в таблице: {count}")
        
        # 3. Подтверждение
        print("\n⚠️  ВНИМАНИЕ!")
        print("Будет добавлена колонка 'role' с типом TEXT")
        print("Всем существующим анкетам будет присвоена роль 'player'")
        confirm = input("\nПродолжить миграцию? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("❌ Миграция отменена")
            return
        
        # 4. Выполняем миграцию
        print("\n⏳ Выполнение миграции...")
        
        # Добавляем колонку
        await conn.execute("""
            ALTER TABLE profiles 
            ADD COLUMN role TEXT DEFAULT 'player' NOT NULL
        """)
        print("✅ Колонка 'role' добавлена")
        
        # Проставляем всем существующим анкетам роль 'player'
        updated = await conn.execute("""
            UPDATE profiles 
            SET role = 'player' 
            WHERE role IS NULL OR role = ''
        """)
        print(f"✅ Обновлено записей: {updated}")
        
        # 5. Создаём индекс для оптимизации поиска
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_profiles_game_role 
            ON profiles(game, role)
        """)
        print("✅ Индекс idx_profiles_game_role создан")
        
        # 6. Проверяем результат
        print("\n🔍 Проверка результата...")
        new_structure = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'profiles'
            ORDER BY ordinal_position
        """)
        
        print("\n📊 Обновлённая структура таблицы 'profiles':")
        for col in new_structure:
            marker = "✨ NEW" if col['column_name'] == 'role' else ""
            print(f"  - {col['column_name']}: {col['data_type']} "
                  f"(nullable: {col['is_nullable']}, default: {col['column_default']}) {marker}")
        
        # 7. Проверяем данные
        role_stats = await conn.fetch("""
            SELECT role, COUNT(*) as count 
            FROM profiles 
            GROUP BY role
        """)
        
        print("\n📈 Статистика по ролям:")
        for stat in role_stats:
            print(f"   {stat['role']}: {stat['count']}")
        
        print("\n✅ Миграция успешно завершена!")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА при выполнении миграции: {e}")
        raise
    
    finally:
        await conn.close()
        print("\n🔌 Соединение с БД закрыто")

if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        exit(1)