#!/usr/bin/env python3
"""
Миграция: удаление фамилий из поля name в профилях
Оставляем только первое слово (имя) из поля name
"""

import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

async def migrate_names():
    """Миграция имен - убираем фамилии"""
    print("🔄 Начинаем миграцию имен...")
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Параметры подключения
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'teammates')
    db_user = os.getenv('DB_USER', 'teammates_user')
    db_password = os.getenv('DB_PASSWORD', '')
    
    if not db_password:
        print("❌ DB_PASSWORD не установлен")
        return False
    
    connection_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    try:
        # Подключаемся к базе
        conn = await asyncpg.connect(connection_url)
        print("✅ Подключение к PostgreSQL успешно")
        
        # Сначала показываем что будем менять
        profiles_to_change = await conn.fetch("""
            SELECT telegram_id, game, name 
            FROM profiles 
            WHERE name LIKE '% %'
            ORDER BY telegram_id, game
        """)
        
        if not profiles_to_change:
            print("✅ Нет профилей с фамилиями для миграции")
            await conn.close()
            return True
        
        print(f"\n📋 Найдено {len(profiles_to_change)} профилей с фамилиями:")
        print("-" * 60)
        for profile in profiles_to_change:
            old_name = profile['name']
            new_name = old_name.split()[0]  # Берем первое слово
            game_name = "Dota 2" if profile['game'] == 'dota' else "CS2"
            print(f"ID {profile['telegram_id']} ({game_name}): '{old_name}' → '{new_name}'")
        
        # Спрашиваем подтверждение
        print("-" * 60)
        confirm = input("\n❓ Выполнить миграцию? (да/нет): ").strip().lower()
        
        if confirm != 'да':
            print("❌ Миграция отменена")
            await conn.close()
            return False
        
        # Выполняем миграцию
        print("\n🔄 Выполняем миграцию...")
        
        async with conn.transaction():
            # Обновляем имена - берем только первое слово
            result = await conn.execute("""
                UPDATE profiles 
                SET name = TRIM(SPLIT_PART(name, ' ', 1))
                WHERE name LIKE '% %'
            """)
            
            # Получаем количество измененных записей
            updated_count = int(result.split()[-1])
            
        # Проверяем результат
        remaining_with_spaces = await conn.fetchval("""
            SELECT COUNT(*) FROM profiles WHERE name LIKE '% %'
        """)
        
        await conn.close()
        
        print(f"✅ Миграция завершена!")
        print(f"   Обновлено записей: {updated_count}")
        print(f"   Осталось с пробелами: {remaining_with_spaces}")
        
        if remaining_with_spaces == 0:
            print("🎉 Все фамилии успешно удалены!")
        else:
            print("⚠️  Есть записи с пробелами, возможно нужна дополнительная проверка")
        
        return True
        
    except Exception as e:
        print(f"💥 Ошибка миграции: {e}")
        return False

async def show_current_names():
    """Показать текущие имена без изменений"""
    print("👀 Просмотр текущих имен в базе...")
    
    load_dotenv()
    
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'teammates')
    db_user = os.getenv('DB_USER', 'teammates_user')
    db_password = os.getenv('DB_PASSWORD', '')
    
    if not db_password:
        print("❌ DB_PASSWORD не установлен")
        return
    
    connection_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    try:
        conn = await asyncpg.connect(connection_url)
        
        # Показываем все имена
        all_names = await conn.fetch("""
            SELECT telegram_id, game, name 
            FROM profiles 
            ORDER BY telegram_id, game
        """)
        
        names_with_spaces = [p for p in all_names if ' ' in p['name']]
        names_single = [p for p in all_names if ' ' not in p['name']]
        
        print(f"\n📊 Статистика имен:")
        print(f"   Всего профилей: {len(all_names)}")
        print(f"   С фамилиями (пробелами): {len(names_with_spaces)}")
        print(f"   Только имена: {len(names_single)}")
        
        if names_with_spaces:
            print(f"\n📋 Профили с фамилиями ({len(names_with_spaces)}):")
            for profile in names_with_spaces[:10]:  # Показываем первые 10
                game_name = "Dota 2" if profile['game'] == 'dota' else "CS2"
                print(f"   ID {profile['telegram_id']} ({game_name}): '{profile['name']}'")
            
            if len(names_with_spaces) > 10:
                print(f"   ... и еще {len(names_with_spaces) - 10}")
        
        await conn.close()
        
    except Exception as e:
        print(f"💥 Ошибка просмотра: {e}")

async def main():
    print("🔧 Миграция имен - удаление фамилий")
    print("=" * 50)
    
    while True:
        print("\nВыберите действие:")
        print("1. Просмотреть текущие имена")
        print("2. Выполнить миграцию (удалить фамилии)")
        print("0. Выход")
        
        choice = input("\nВаш выбор: ").strip()
        
        if choice == "0":
            print("👋 До свидания!")
            break
        elif choice == "1":
            await show_current_names()
        elif choice == "2":
            success = await migrate_names()
            if success:
                print("\n🎉 Миграция выполнена! Теперь можно запускать обновленного бота")
                break
        else:
            print("❌ Неверный выбор")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Работа прервана")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)