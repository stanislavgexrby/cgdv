#!/usr/bin/env python3
"""
Простой скрипт для тестирования подключений к PostgreSQL и Redis
"""

import asyncio
import asyncpg
import redis.asyncio as redis
import os
import sys
from dotenv import load_dotenv

async def test_postgresql():
    """Тестирование PostgreSQL"""
    print("🔍 Тестирование PostgreSQL...")
    try:
        connection_url = (f"postgresql://"
                         f"{os.getenv('DB_USER')}:"
                         f"{os.getenv('DB_PASSWORD')}@"
                         f"{os.getenv('DB_HOST')}:"
                         f"{os.getenv('DB_PORT')}/"
                         f"{os.getenv('DB_NAME')}")
        
        conn = await asyncpg.connect(connection_url, ssl='disable')
        
        # Проверяем подключение
        version = await conn.fetchval('SELECT version()')
        
        # Проверяем что можем создавать таблицы
        await conn.execute('CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY)')
        await conn.execute('DROP TABLE test_table')
        
        await conn.close()
        
        print(f"✅ PostgreSQL подключение успешно")
        print(f"   Версия: {version.split()[1]}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка PostgreSQL: {e}")
        print("   Проверьте:")
        print("   - Запущен ли PostgreSQL")
        print("   - Правильность настроек в .env")
        print("   - Существует ли база данных")
        return False

async def test_redis():
    """Тестирование Redis"""
    print("\n🔍 Тестирование Redis...")
    try:
        redis_url = f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}/{os.getenv('REDIS_DB', 0)}"
        
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Проверяем подключение
        await r.ping()
        
        # Проверяем что можем записывать/читать
        await r.set('test_key', 'test_value', ex=10)
        value = await r.get('test_key')
        assert value == 'test_value'
        await r.delete('test_key')
        
        # Получаем информацию
        info = await r.info()
        
        await r.close()
        
        print(f"✅ Redis подключение успешно")
        print(f"   Версия: {info['redis_version']}")
        print(f"   Память: {info['used_memory_human']}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка Redis: {e}")
        print("   Проверьте:")
        print("   - Запущен ли Redis")
        print("   - Правильность настроек в .env")
        return False

async def test_database_classes():
    """Тестирование классов базы данных"""
    print("\n🔍 Тестирование классов базы данных...")
    try:
        from database.database import Database
        
        # Создаем и инициализируем базу данных
        db = Database()
        await db.init()
        
        # Тестируем простые операции
        test_user_id = 999999999
        test_game = "dota"
        
        # Создание пользователя
        await db.create_user(test_user_id, "test_user", test_game)
        
        # Получение пользователя
        user = await db.get_user(test_user_id)
        assert user is not None
        
        # Создание профиля
        await db.update_user_profile(
            test_user_id, test_game, "Test User", "testuser", 
            25, "legend", "eeu", ["pos1"], "Test description"
        )
        
        # Получение профиля
        profile = await db.get_user_profile(test_user_id, test_game)
        assert profile is not None
        assert profile['name'] == "Test User"
        
        # Удаление тестовых данных
        await db.delete_profile(test_user_id, test_game)
        
        await db.close()
        
        print("✅ Классы базы данных работают корректно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования классов БД: {e}")
        return False

def check_env_vars():
    """Проверка переменных окружения"""
    print("🔍 Проверка переменных окружения...")
    
    required_vars = {
        'BOT_TOKEN': 'Токен Telegram бота',
        'DB_HOST': 'Хост PostgreSQL',
        'DB_PORT': 'Порт PostgreSQL', 
        'DB_NAME': 'Имя базы данных',
        'DB_USER': 'Пользователь PostgreSQL',
        'DB_PASSWORD': 'Пароль PostgreSQL',
        'REDIS_HOST': 'Хост Redis',
        'REDIS_PORT': 'Порт Redis'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value or value in ['your_bot_token_here', 'password', 'your_password']:
            missing_vars.append(f"   {var} - {description}")
    
    if missing_vars:
        print("❌ Отсутствуют или некорректны переменные окружения:")
        for var in missing_vars:
            print(var)
        print("\n   Обновите .env файл!")
        return False
    
    print("✅ Все переменные окружения настроены")
    return True

async def main():
    print("🧪 Тестирование подключений TeammateBot")
    print("=" * 50)
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Проверяем переменные окружения
    if not check_env_vars():
        sys.exit(1)
    
    # Тестируем подключения
    pg_ok = await test_postgresql()
    redis_ok = await test_redis()
    
    # Тестируем классы базы данных
    db_classes_ok = False
    if pg_ok and redis_ok:
        db_classes_ok = await test_database_classes()
    
    # Результат
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"   PostgreSQL: {'✅' if pg_ok else '❌'}")
    print(f"   Redis: {'✅' if redis_ok else '❌'}")
    print(f"   Классы БД: {'✅' if db_classes_ok else '❌'}")
    print("-" * 50)
    
    if pg_ok and redis_ok and db_classes_ok:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("\n🚀 Можно запускать бота:")
        print("   python main.py")
    else:
        print("💥 ЕСТЬ ПРОБЛЕМЫ!")
        print("\n🔧 Что проверить:")
        if not pg_ok:
            print("   - docker-compose up -d (для запуска PostgreSQL)")
            print("   - Настройки DB_* в .env файле")
        if not redis_ok:
            print("   - docker-compose up -d (для запуска Redis)")
            print("   - Настройки REDIS_* в .env файле")
        if not db_classes_ok:
            print("   - Правильность кода database/*.py")
            print("   - Установленные зависимости: pip install asyncpg redis")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Тестирование прервано")
    except Exception as e:
        print(f"\n💥 Неожиданная ошибка: {e}")