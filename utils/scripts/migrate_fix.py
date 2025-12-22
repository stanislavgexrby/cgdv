#!/usr/bin/env python3
"""
Универсальная миграция: проверка и добавление всех необходимых колонок в profiles
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.database import Database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Список всех колонок которые должны быть в таблице profiles
REQUIRED_COLUMNS = {
    'id': {
        'type': 'SERIAL PRIMARY KEY',
        'skip_if_exists': True  # Не пытаться изменить PRIMARY KEY
    },
    'telegram_id': {
        'type': 'BIGINT',
        'nullable': True
    },
    'game': {
        'type': 'TEXT',
        'nullable': True
    },
    'name': {
        'type': 'TEXT',
        'nullable': True
    },
    'nickname': {
        'type': 'TEXT',
        'nullable': True
    },
    'age': {
        'type': 'INTEGER',
        'nullable': True
    },
    'rating': {
        'type': 'TEXT',
        'nullable': True
    },
    'region': {
        'type': 'TEXT',
        'default': "'eeu'"
    },
    'positions': {
        'type': 'JSONB',
        'default': "'[]'::jsonb"
    },
    'goals': {
        'type': 'JSONB',
        'default': "'[\"any\"]'::jsonb"
    },
    'additional_info': {
        'type': 'TEXT',
        'nullable': True
    },
    'photo_id': {
        'type': 'TEXT',
        'nullable': True
    },
    'profile_url': {
        'type': 'TEXT',
        'nullable': True
    },
    'role': {
        'type': 'TEXT',
        'default': "'player'"
    },
    'created_at': {
        'type': 'TIMESTAMP',
        'default': 'CURRENT_TIMESTAMP'
    },
    'updated_at': {
        'type': 'TIMESTAMP',
        'default': 'CURRENT_TIMESTAMP'
    }
}

async def migrate():
    """Проверка и добавление всех необходимых колонок"""
    
    print("=" * 70)
    print("🔧 УНИВЕРСАЛЬНАЯ МИГРАЦИЯ: Проверка структуры таблицы profiles")
    print("=" * 70)
    
    db = Database()
    
    try:
        await db.init()
        print("✅ Подключение установлено\n")
        
        async with db._pg_pool.acquire() as conn:
            # Проверяем существование таблицы
            print("🔍 Проверка существования таблицы profiles...")
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'profiles'
                )
            """)
            
            if not table_exists:
                print("❌ Таблица profiles не существует!")
                print("💡 Запустите бота один раз, чтобы создать базовую структуру")
                return
            
            print("✅ Таблица profiles существует\n")
            
            # Получаем текущие колонки
            print("📊 Получение текущей структуры таблицы...")
            existing_columns = await conn.fetch("""
                SELECT column_name, data_type, column_default, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'profiles'
                ORDER BY ordinal_position
            """)
            
            existing_column_names = {col['column_name'] for col in existing_columns}
            
            print(f"📋 Найдено колонок: {len(existing_column_names)}")
            for col in existing_columns:
                default = col['column_default'] or 'NULL'
                print(f"  ✓ {col['column_name']:20} | {col['data_type']:15} | DEFAULT: {default}")
            
            # Определяем какие колонки нужно добавить
            missing_columns = []
            for col_name, col_info in REQUIRED_COLUMNS.items():
                if col_name not in existing_column_names:
                    if not col_info.get('skip_if_exists'):
                        missing_columns.append((col_name, col_info))
            
            if not missing_columns:
                print("\n✅ Все необходимые колонки уже существуют!")
                print("🎉 Миграция не требуется")
                return
            
            print(f"\n⚠️  Найдено отсутствующих колонок: {len(missing_columns)}")
            print("\n📋 Будут добавлены следующие колонки:")
            for col_name, col_info in missing_columns:
                col_type = col_info['type']
                if 'default' in col_info:
                    col_def = f"ADD COLUMN {col_name} {col_type} DEFAULT {col_info['default']}"
                elif col_info.get('nullable'):
                    col_def = f"ADD COLUMN {col_name} {col_type}"
                else:
                    col_def = f"ADD COLUMN {col_name} {col_type} NOT NULL"
                print(f"  • {col_name:20} -> {col_def}")
            
            print()
            confirm = input("❓ Продолжить миграцию? (yes/no): ").strip().lower()
            
            if confirm != 'yes':
                print("❌ Миграция отменена")
                return
            
            # Применяем миграции
            print("\n⏳ Применение миграций...")
            added_count = 0
            errors = []
            
            for col_name, col_info in missing_columns:
                try:
                    col_type = col_info['type']
                    
                    # Формируем SQL запрос
                    if 'default' in col_info:
                        sql = f"ALTER TABLE profiles ADD COLUMN {col_name} {col_type} DEFAULT {col_info['default']}"
                    elif col_info.get('nullable'):
                        sql = f"ALTER TABLE profiles ADD COLUMN {col_name} {col_type}"
                    else:
                        sql = f"ALTER TABLE profiles ADD COLUMN {col_name} {col_type} NOT NULL"
                    
                    await conn.execute(sql)
                    print(f"  ✅ Добавлена колонка: {col_name}")
                    added_count += 1
                    
                except Exception as e:
                    error_msg = f"Ошибка при добавлении {col_name}: {e}"
                    print(f"  ❌ {error_msg}")
                    errors.append(error_msg)
            
            # Обновляем пустые значения для goals если нужно
            try:
                if 'goals' in [c[0] for c in missing_columns]:
                    await conn.execute("UPDATE profiles SET goals = '[\"any\"]'::jsonb WHERE goals IS NULL")
                    print("  ✅ Обновлены пустые значения goals")
            except Exception as e:
                print(f"  ⚠️  Предупреждение при обновлении goals: {e}")
            
            # Обновляем пустые значения для updated_at если нужно
            try:
                if 'updated_at' in [c[0] for c in missing_columns]:
                    await conn.execute("UPDATE profiles SET updated_at = created_at WHERE updated_at IS NULL")
                    print("  ✅ Обновлены пустые значения updated_at")
            except Exception as e:
                print(f"  ⚠️  Предупреждение при обновлении updated_at: {e}")
            
            # Финальная проверка
            print("\n🔍 Проверка результата...")
            final_columns = await conn.fetch("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'profiles'
                ORDER BY ordinal_position
            """)
            
            print(f"\n📊 Итоговая структура таблицы profiles ({len(final_columns)} колонок):")
            for col in final_columns:
                default = col['column_default'] or 'NULL'
                marker = "🆕" if col['column_name'] in [c[0] for c in missing_columns] else "  "
                print(f"{marker} {col['column_name']:20} | {col['data_type']:15} | DEFAULT: {default}")
            
            # Итоговая статистика
            print(f"\n{'='*70}")
            print(f"✅ Миграция завершена!")
            print(f"📊 Добавлено колонок: {added_count}")
            if errors:
                print(f"⚠️  Ошибок: {len(errors)}")
                for error in errors:
                    print(f"   • {error}")
            else:
                print("🎉 Все колонки добавлены успешно!")
            
            # Показываем количество профилей
            profiles_count = await conn.fetchval("SELECT COUNT(*) FROM profiles")
            print(f"📈 Всего профилей в БД: {profiles_count}")
            
            print(f"🚀 Можно запускать бота!")
            print("=" * 70)
            
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.exception("Детали:")
        raise
    
    finally:
        await db.close()

if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)