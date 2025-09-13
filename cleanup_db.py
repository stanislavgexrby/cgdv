#!/usr/bin/env python3
"""
Скрипт очистки базы данных TeammateBot
"""

import asyncio
import asyncpg
import redis.asyncio as redis
import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta

class DatabaseCleaner:
    def __init__(self):
        self.pg_pool = None
        self.redis = None

    async def init(self):
        """Инициализация подключений"""
        load_dotenv()
        
        # PostgreSQL
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'teammates')
        db_user = os.getenv('DB_USER', 'teammates_user')
        db_password = os.getenv('DB_PASSWORD', '')
        
        if not db_password:
            raise ValueError("DB_PASSWORD не установлен")
        
        connection_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        self.pg_pool = await asyncpg.create_pool(connection_url, min_size=1, max_size=5)
        
        # Redis
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = os.getenv('REDIS_PORT', '6379')
        redis_db = os.getenv('REDIS_DB', '0')
        redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
        
        self.redis = redis.from_url(redis_url, decode_responses=True)
        await self.redis.ping()
        
        print("✅ Подключение к PostgreSQL и Redis успешно")

    async def close(self):
        """Закрытие подключений"""
        if self.pg_pool:
            await self.pg_pool.close()
        if self.redis:
            await self.redis.close()

    async def get_stats(self):
        """Получение статистики БД"""
        async with self.pg_pool.acquire() as conn:
            stats = {}
            
            tables = [
                ('users', 'Пользователи'),
                ('profiles', 'Анкеты'),
                ('likes', 'Лайки'),
                ('matches', 'Матчи'),
                ('reports', 'Жалобы'),
                ('bans', 'Баны'),
                ('search_skipped', 'Пропуски в поиске'),
                ('skipped_likes', 'Пропуски лайков')
            ]
            
            for table, name in tables:
                try:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    stats[name] = count or 0
                except Exception as e:
                    stats[name] = f"Ошибка: {e}"
            
            # Redis статистика
            try:
                redis_keys = await self.redis.dbsize()
                stats['Redis ключи'] = redis_keys
            except Exception as e:
                stats['Redis ключи'] = f"Ошибка: {e}"
            
            return stats

    async def clear_redis(self):
        """Очистка Redis"""
        try:
            await self.redis.flushdb()
            print("✅ Redis очищен")
            return True
        except Exception as e:
            print(f"❌ Ошибка очистки Redis: {e}")
            return False

    async def clear_test_users(self):
        """Удаление тестовых пользователей (с ID > 10000000)"""
        async with self.pg_pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Удаляем связанные данные
                    await conn.execute("DELETE FROM search_skipped WHERE user_id > 10000000 OR skipped_user_id > 10000000")
                    await conn.execute("DELETE FROM skipped_likes WHERE user_id > 10000000 OR skipped_user_id > 10000000")
                    await conn.execute("DELETE FROM reports WHERE reporter_id > 10000000 OR reported_user_id > 10000000")
                    await conn.execute("DELETE FROM bans WHERE user_id > 10000000")
                    await conn.execute("DELETE FROM matches WHERE user1 > 10000000 OR user2 > 10000000")
                    await conn.execute("DELETE FROM likes WHERE from_user > 10000000 OR to_user > 10000000")
                    await conn.execute("DELETE FROM profiles WHERE telegram_id > 10000000")
                    result = await conn.execute("DELETE FROM users WHERE telegram_id > 10000000")
                    
                    print(f"✅ Удалены тестовые пользователи: {result}")
                    return True
                except Exception as e:
                    print(f"❌ Ошибка удаления тестовых пользователей: {e}")
                    return False

    async def clear_old_data(self, days: int = 30):
        """Удаление старых данных"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.pg_pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Удаляем старые жалобы
                    result1 = await conn.execute(
                        "DELETE FROM reports WHERE created_at < $1 AND status != 'pending'",
                        cutoff_date
                    )
                    
                    # Удаляем истекшие баны
                    result2 = await conn.execute(
                        "DELETE FROM bans WHERE expires_at < NOW()"
                    )
                    
                    # Удаляем старые пропуски в поиске
                    result3 = await conn.execute(
                        "DELETE FROM search_skipped WHERE last_skipped < $1",
                        cutoff_date
                    )
                    
                    print(f"✅ Удалены старые данные:")
                    print(f"   Жалобы: {result1}")
                    print(f"   Истекшие баны: {result2}")
                    print(f"   Старые пропуски: {result3}")
                    return True
                except Exception as e:
                    print(f"❌ Ошибка удаления старых данных: {e}")
                    return False

    async def clear_specific_user(self, user_id: int):
        """Удаление конкретного пользователя"""
        async with self.pg_pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Удаляем все данные пользователя
                    await conn.execute("DELETE FROM search_skipped WHERE user_id = $1 OR skipped_user_id = $1", user_id)
                    await conn.execute("DELETE FROM skipped_likes WHERE user_id = $1 OR skipped_user_id = $1", user_id)
                    await conn.execute("DELETE FROM reports WHERE reporter_id = $1 OR reported_user_id = $1", user_id)
                    await conn.execute("DELETE FROM bans WHERE user_id = $1", user_id)
                    await conn.execute("DELETE FROM matches WHERE user1 = $1 OR user2 = $1", user_id)
                    await conn.execute("DELETE FROM likes WHERE from_user = $1 OR to_user = $1", user_id)
                    await conn.execute("DELETE FROM profiles WHERE telegram_id = $1", user_id)
                    result = await conn.execute("DELETE FROM users WHERE telegram_id = $1", user_id)
                    
                    # Очищаем Redis кэш пользователя
                    try:
                        patterns = [f"profile:{user_id}:*", f"search:{user_id}:*", f"rate_limit:{user_id}:*"]
                        for pattern in patterns:
                            keys = await self.redis.keys(pattern)
                            if keys:
                                await self.redis.delete(*keys)
                    except Exception as redis_error:
                        print(f"⚠️ Ошибка очистки Redis для пользователя {user_id}: {redis_error}")
                    
                    print(f"✅ Пользователь {user_id} полностью удален: {result}")
                    return True
                except Exception as e:
                    print(f"❌ Ошибка удаления пользователя {user_id}: {e}")
                    return False

    async def full_cleanup(self):
        """ПОЛНАЯ очистка всех данных"""
        async with self.pg_pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Удаляем все данные в правильном порядке
                    tables = [
                        'search_skipped',
                        'skipped_likes', 
                        'reports',
                        'bans',
                        'matches',
                        'likes',
                        'profiles',
                        'users'
                    ]
                    
                    for table in tables:
                        result = await conn.execute(f"DELETE FROM {table}")
                        print(f"   {table}: {result}")
                    
                    print("✅ Все данные PostgreSQL удалены")
                    
                    # Очищаем Redis
                    await self.clear_redis()
                    return True
                except Exception as e:
                    print(f"❌ Ошибка полной очистки: {e}")
                    return False

    async def show_menu(self):
        """Показ главного меню"""
        while True:
            print("\n" + "="*50)
            print("🧹 ОЧИСТКА БАЗЫ ДАННЫХ TeammateBot")
            print("="*50)
            
            # Показываем текущую статистику
            stats = await self.get_stats()
            print("\n📊 Текущая статистика:")
            for name, count in stats.items():
                print(f"   {name}: {count}")
            
            print("\n🔧 Опции очистки:")
            print("1. Очистить только Redis (кэш)")
            print("2. Удалить тестовых пользователей (ID > 10M)")
            print("3. Удалить старые данные (30+ дней)")
            print("4. Удалить конкретного пользователя")
            print("5. ПОЛНАЯ ОЧИСТКА (все данные)")
            print("6. Показать статистику")
            print("0. Выход")
            
            choice = input("\nВыберите опцию (0-6): ").strip()
            
            if choice == "0":
                print("👋 До свидания!")
                break
            elif choice == "1":
                await self.clear_redis()
            elif choice == "2":
                if self.confirm_action("удалить всех тестовых пользователей"):
                    await self.clear_test_users()
            elif choice == "3":
                days = input("Сколько дней считать старыми данными? (по умолчанию 30): ").strip()
                try:
                    days = int(days) if days else 30
                    if self.confirm_action(f"удалить данные старше {days} дней"):
                        await self.clear_old_data(days)
                except ValueError:
                    print("❌ Неверное количество дней")
            elif choice == "4":
                user_id = input("Введите ID пользователя для удаления: ").strip()
                try:
                    user_id = int(user_id)
                    if self.confirm_action(f"полностью удалить пользователя {user_id}"):
                        await self.clear_specific_user(user_id)
                except ValueError:
                    print("❌ Неверный ID пользователя")
            elif choice == "5":
                print("⚠️  ВНИМАНИЕ! Это удалит ВСЕ данные из базы!")
                if self.confirm_action("ПОЛНОСТЬЮ ОЧИСТИТЬ базу данных", double_check=True):
                    await self.full_cleanup()
            elif choice == "6":
                continue  # Статистика показывается в начале цикла
            else:
                print("❌ Неверная опция")

    def confirm_action(self, action: str, double_check: bool = False) -> bool:
        """Подтверждение действия"""
        print(f"\n⚠️  Вы собираетесь {action}")
        
        if double_check:
            first = input("Введите 'ДА' для подтверждения: ").strip()
            if first != 'ДА':
                print("❌ Действие отменено")
                return False
            
            second = input("Введите 'ПОДТВЕРЖДАЮ' для финального подтверждения: ").strip()
            if second != 'ПОДТВЕРЖДАЮ':
                print("❌ Действие отменено")
                return False
        else:
            confirm = input("Введите 'да' для подтверждения: ").strip().lower()
            if confirm != 'да':
                print("❌ Действие отменено")
                return False
        
        return True

async def main():
    cleaner = DatabaseCleaner()
    
    try:
        await cleaner.init()
        await cleaner.show_menu()
    except KeyboardInterrupt:
        print("\n👋 Работа прервана пользователем")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
    finally:
        await cleaner.close()

if __name__ == "__main__":
    asyncio.run(main())