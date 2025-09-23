#!/usr/bin/env python3
"""
Скрипт миграции данных из системы регионов в систему стран
"""

import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

# Соответствие старых регионов новым странам (по умолчанию)
REGION_MAPPING = {
    "eeu": "russia",    # Восточная Европа -> Россия (по умолчанию)
    "weu": "poland",    # Западная Европа -> Польша (по умолчанию)  
    "asia": "china",    # Азия -> Китай (по умолчанию)
    "any": "any"        # Не указан остается не указан
}

async def get_db_connection():
    """Получение подключения к базе данных"""
    load_dotenv()
    
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'teammates')
    db_user = os.getenv('DB_USER', 'teammates_user')
    db_password = os.getenv('DB_PASSWORD', '')
    
    if not db_password:
        print("❌ DB_PASSWORD не установлен")
        return None
    
    connection_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    try:
        conn = await asyncpg.connect(connection_url)
        print("✅ Подключение к PostgreSQL успешно")
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return None

async def migrate_regions_to_countries():
    """Миграция старых регионов в новую систему стран"""
    
    conn = await get_db_connection()
    if not conn:
        return False
    
    try:
        print("🔄 Начинаем миграцию регионов в страны...")
        
        # Получить все профили с старыми регионами
        profiles = await conn.fetch("""
            SELECT telegram_id, game, region 
            FROM profiles 
            WHERE region IS NOT NULL
            ORDER BY telegram_id, game
        """)
        
        if not profiles:
            print("✅ Нет профилей для миграции")
            return True
        
        migrated_count = 0
        unchanged_count = 0
        
        print(f"\n📋 Найдено {len(profiles)} профилей:")
        print("-" * 70)
        
        async with conn.transaction():
            for profile in profiles:
                telegram_id = profile['telegram_id']
                game = profile['game']
                old_region = profile['region']
                
                # Если регион уже в новом формате (есть в новых странах), пропускаем
                new_countries = ['russia', 'belarus', 'ukraine', 'kazakhstan', 'any']
                if old_region in new_countries:
                    unchanged_count += 1
                    continue
                    
                # Если это старый регион, мигрируем
                if old_region in REGION_MAPPING:
                    new_country = REGION_MAPPING[old_region]
                    
                    # Обновляем профиль
                    await conn.execute("""
                        UPDATE profiles 
                        SET region = $1 
                        WHERE telegram_id = $2 AND game = $3
                    """, new_country, telegram_id, game)
                    
                    game_name = "Dota 2" if game == 'dota' else "CS2"
                    print(f"ID {telegram_id} ({game_name}): '{old_region}' → '{new_country}'")
                    migrated_count += 1
                else:
                    # Неизвестный регион, устанавливаем "any"
                    await conn.execute("""
                        UPDATE profiles 
                        SET region = 'any' 
                        WHERE telegram_id = $1 AND game = $2
                    """, telegram_id, game)
                    
                    game_name = "Dota 2" if game == 'dota' else "CS2"
                    print(f"ID {telegram_id} ({game_name}): неизвестный '{old_region}' → 'any'")
                    migrated_count += 1
        
        print(f"\n✅ Миграция завершена!")
        print(f"📊 Мигрировано профилей: {migrated_count}")
        print(f"📊 Без изменений: {unchanged_count}")
        print(f"📊 Всего профилей: {migrated_count + unchanged_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        return False
    
    finally:
        await conn.close()

async def reset_all_regions_to_any():
    """Сброс всех регионов в 'any' - пользователи выберут страны заново"""
    
    conn = await get_db_connection()
    if not conn:
        return False
    
    try:
        print("🔄 Начинаем сброс всех регионов в 'any'...")
        
        # Получить все профили с регионами не равными 'any'
        profiles = await conn.fetch("""
            SELECT telegram_id, game, region 
            FROM profiles 
            WHERE region IS NOT NULL AND region != 'any'
            ORDER BY telegram_id, game
        """)
        
        if not profiles:
            print("✅ Нет профилей для сброса - все уже в 'any'")
            return True
        
        reset_count = 0
        
        print(f"\n📋 Найдено {len(profiles)} профилей для сброса:")
        print("-" * 70)
        
        # Спрашиваем подтверждение
        for profile in profiles[:10]:  # Показываем только первые 10
            game_name = "Dota 2" if profile['game'] == 'dota' else "CS2"
            print(f"ID {profile['telegram_id']} ({game_name}): '{profile['region']}' → 'any'")
        
        if len(profiles) > 10:
            print(f"... и еще {len(profiles) - 10} профилей")
        
        print("-" * 70)
        confirm = input(f"\n❓ Сбросить регионы для {len(profiles)} профилей? (да/нет): ").strip().lower()
        
        if confirm != 'да':
            print("❌ Сброс отменен")
            return False
        
        # Выполняем сброс
        async with conn.transaction():
            result = await conn.execute("""
                UPDATE profiles 
                SET region = 'any' 
                WHERE region IS NOT NULL AND region != 'any'
            """)
            
            # Получаем количество измененных записей
            reset_count = int(result.split()[-1])
        
        print(f"\n✅ Сброс завершен!")
        print(f"📊 Сброшено профилей: {reset_count}")
        print(f"💡 Пользователям будет предложено выбрать страну заново при редактировании анкеты")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при сбросе: {e}")
        return False
    
    finally:
        await conn.close()

async def show_current_regions():
    """Показать текущее распределение регионов"""
    
    conn = await get_db_connection()
    if not conn:
        return False
    
    try:
        print("📊 Текущее распределение регионов:")
        print("-" * 50)
        
        # Получить статистику по регионам
        stats = await conn.fetch("""
            SELECT region, game, COUNT(*) as count
            FROM profiles 
            WHERE region IS NOT NULL
            GROUP BY region, game
            ORDER BY region, game
        """)
        
        if not stats:
            print("Нет профилей в базе данных")
            return True
        
        current_region = None
        for stat in stats:
            region = stat['region'] or 'NULL'
            game_name = "Dota 2" if stat['game'] == 'dota' else "CS2"
            count = stat['count']
            
            if region != current_region:
                if current_region is not None:
                    print()
                print(f"📍 {region}:")
                current_region = region
            
            print(f"  {game_name}: {count} профилей")
        
        # Общая статистика
        total = await conn.fetchval("SELECT COUNT(*) FROM profiles")
        print(f"\n📈 Всего профилей: {total}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return False
    
    finally:
        await conn.close()

async def main():
    print("🌍 Миграция системы регионов в страны")
    print("=" * 50)
    
    while True:
        print("\nВыберите действие:")
        print("1. Показать текущее распределение регионов")
        print("2. Мигрировать регионы в страны по умолчанию")
        print("3. Сбросить все регионы в 'any' (рекомендуется)")
        print("0. Выход")
        
        choice = input("\nВведите номер (0-3): ").strip()
        
        if choice == "0":
            print("👋 До свидания!")
            break
        elif choice == "1":
            await show_current_regions()
        elif choice == "2":
            print("\n🔄 Запуск миграции с преобразованием...")
            success = await migrate_regions_to_countries()
            if success:
                print("✅ Миграция выполнена успешно")
            else:
                print("❌ Миграция завершилась с ошибкой")
        elif choice == "3":
            print("\n🔄 Запуск сброса регионов...")
            success = await reset_all_regions_to_any()
            if success:
                print("✅ Сброс выполнен успешно")
            else:
                print("❌ Сброс завершился с ошибкой")
        else:
            print("❌ Неверный выбор. Попробуйте снова.")

if __name__ == "__main__":
    asyncio.run(main())