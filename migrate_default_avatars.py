#!/usr/bin/env python3
"""
Миграция: Установка дефолтных аватарок для пользователей без фото
Загружает аватарки в Telegram и обновляет пользователей с photo_id = NULL
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.database import Database
from aiogram import Bot
import config.settings as settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Пути к аватаркам
DOTA_AVATAR_PATH = "assets/dotaemptyavatar.png"
CS_AVATAR_PATH = "assets/csemptyavatar.png"

async def upload_avatar_to_telegram(bot: Bot, avatar_path: str, game_name: str) -> str:
    """Загрузить аватарку в Telegram и получить file_id"""
    try:
        if not Path(avatar_path).exists():
            raise FileNotFoundError(f"Файл {avatar_path} не найден!")
        
        # Загружаем фото в Telegram
        from aiogram.types import FSInputFile
        photo = FSInputFile(avatar_path)
        
        # Отправляем админу (чтобы получить file_id)
        admin_id = settings.ADMIN_ID
        if not admin_id:
            raise ValueError("ADMIN_ID не установлен в settings!")
        
        message = await bot.send_photo(
            chat_id=admin_id,
            photo=photo,
            caption=f"🎮 Дефолтная аватарка для {game_name}"
        )
        
        file_id = message.photo[-1].file_id
        logger.info(f"✅ Загружена аватарка {game_name}: {file_id}")
        
        return file_id
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки аватарки {game_name}: {e}")
        raise

async def migrate():
    """Основная функция миграции"""
    
    print("=" * 70)
    print("🔧 МИГРАЦИЯ: Установка дефолтных аватарок")
    print("=" * 70)
    
    # Инициализируем бота
    bot = Bot(token=settings.BOT_TOKEN)
    
    # Инициализируем БД
    db = Database()
    
    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")
        
        # Загружаем аватарки в Telegram
        print("⏳ Загрузка аватарок в Telegram...")
        dota_file_id = await upload_avatar_to_telegram(bot, DOTA_AVATAR_PATH, "Dota 2")
        cs_file_id = await upload_avatar_to_telegram(bot, CS_AVATAR_PATH, "CS2")
        
        print(f"\n📸 Dota 2 file_id: {dota_file_id}")
        print(f"📸 CS2 file_id: {cs_file_id}\n")
        
        # Проверяем количество пользователей без фото
        async with db._pg_pool.acquire() as conn:
            # Считаем пользователей без фото по играм
            dota_count = await conn.fetchval("""
                SELECT COUNT(*) FROM profiles 
                WHERE game = 'dota' AND photo_id IS NULL
            """)
            
            cs_count = await conn.fetchval("""
                SELECT COUNT(*) FROM profiles 
                WHERE game = 'cs' AND photo_id IS NULL
            """)
            
            total_count = dota_count + cs_count
            
            print("📊 Статистика:")
            print(f"   Dota 2 без фото: {dota_count}")
            print(f"   CS2 без фото: {cs_count}")
            print(f"   Всего: {total_count}\n")
            
            if total_count == 0:
                print("✅ Все пользователи уже имеют фото!")
                return
            
            # Подтверждение
            print("📋 Будет выполнено:")
            print(f"   1. Обновить {dota_count} профилей Dota 2")
            print(f"   2. Обновить {cs_count} профилей CS2")
            print()
            
            confirm = input("❓ Продолжить миграцию? (yes/no): ").strip().lower()
            
            if confirm != 'yes':
                print("❌ Миграция отменена пользователем")
                return
            
            # Обновляем Dota 2
            print("\n⏳ Обновление профилей Dota 2...")
            updated_dota = await conn.execute("""
                UPDATE profiles 
                SET photo_id = $1 
                WHERE game = 'dota' AND photo_id IS NULL
            """, dota_file_id)
            print(f"✅ Обновлено {dota_count} профилей Dota 2")
            
            # Обновляем CS2
            print("⏳ Обновление профилей CS2...")
            updated_cs = await conn.execute("""
                UPDATE profiles 
                SET photo_id = $1 
                WHERE game = 'cs' AND photo_id IS NULL
            """, cs_file_id)
            print(f"✅ Обновлено {cs_count} профилей CS2")
            
            # Проверяем результат
            print("\n🔍 Проверка результата...")
            remaining = await conn.fetchval("""
                SELECT COUNT(*) FROM profiles WHERE photo_id IS NULL
            """)
            
            if remaining == 0:
                print("✅ Все профили успешно обновлены!")
            else:
                print(f"⚠️  Осталось {remaining} профилей без фото")
        
        print("\n" + "=" * 70)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 70)
        
        # Сохраняем file_id в настройки (опционально)
        print("\n💡 Сохраните эти file_id для будущего использования:")
        print(f"   DOTA_DEFAULT_AVATAR = '{dota_file_id}'")
        print(f"   CS_DEFAULT_AVATAR = '{cs_file_id}'")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА при выполнении миграции: {e}")
        logger.exception("Детали ошибки:")
        raise
    
    finally:
        print("\n🔌 Закрытие соединений...")
        await db.close()
        await bot.session.close()
        print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
