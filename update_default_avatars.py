#!/usr/bin/env python3
"""
Скрипт обновления дефолтных аватарок
Загружает новые аватарки и обновляет профили пользователей
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

        from aiogram.types import FSInputFile
        photo = FSInputFile(avatar_path)

        admin_id = settings.ADMIN_ID
        if not admin_id:
            raise ValueError("ADMIN_ID не установлен в settings!")

        message = await bot.send_photo(
            chat_id=admin_id,
            photo=photo,
            caption=f"🎮 Новая дефолтная аватарка для {game_name}"
        )

        file_id = message.photo[-1].file_id
        logger.info(f"✅ Загружена аватарка {game_name}: {file_id}")

        return file_id

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки аватарки {game_name}: {e}")
        raise

async def get_old_file_ids_from_cache() -> dict:
    """Попытка получить старые file_id из кэша"""
    try:
        cache = settings.load_photo_cache()
        old_ids = {
            'dota': cache.get('avatar_dota'),
            'cs': cache.get('avatar_cs')
        }
        return {k: v for k, v in old_ids.items() if v}
    except:
        return {}

async def get_old_file_ids_from_db(db) -> dict:
    """Автоматически найти старые file_id в БД по частоте использования"""
    try:
        async with db._pg_pool.acquire() as conn:
            # Находим самый популярный photo_id для каждой игры
            # (скорее всего это старая дефолтная аватарка)

            dota_result = await conn.fetchrow("""
                SELECT photo_id, COUNT(*) as count
                FROM profiles
                WHERE game = 'dota' AND photo_id IS NOT NULL
                GROUP BY photo_id
                ORDER BY count DESC
                LIMIT 1
            """)

            cs_result = await conn.fetchrow("""
                SELECT photo_id, COUNT(*) as count
                FROM profiles
                WHERE game = 'cs' AND photo_id IS NOT NULL
                GROUP BY photo_id
                ORDER BY count DESC
                LIMIT 1
            """)

            old_ids = {}
            if dota_result:
                old_ids['dota'] = {
                    'file_id': dota_result['photo_id'],
                    'count': dota_result['count']
                }
            if cs_result:
                old_ids['cs'] = {
                    'file_id': cs_result['photo_id'],
                    'count': cs_result['count']
                }

            return old_ids
    except Exception as e:
        logger.error(f"Ошибка поиска старых file_id в БД: {e}")
        return {}

async def migrate():
    """Основная функция миграции"""

    print("=" * 70)
    print("🔧 ОБНОВЛЕНИЕ ДЕФОЛТНЫХ АВАТАРОК")
    print("=" * 70)

    bot = Bot(token=settings.BOT_TOKEN)
    db = Database()

    try:
        await db.init()
        print("✅ Подключение к БД установлено\n")

        # Загружаем новые аватарки в Telegram
        print("⏳ Загрузка новых аватарок в Telegram...")
        new_dota_file_id = await upload_avatar_to_telegram(bot, DOTA_AVATAR_PATH, "Dota 2")
        new_cs_file_id = await upload_avatar_to_telegram(bot, CS_AVATAR_PATH, "CS2")

        print(f"\n📸 Новые file_id:")
        print(f"   Dota 2: {new_dota_file_id}")
        print(f"   CS2: {new_cs_file_id}\n")

        # Пытаемся получить старые file_id из кэша
        old_ids_cache = await get_old_file_ids_from_cache()

        print("🔍 Поиск старых file_id в кэше...")
        if old_ids_cache:
            print("✅ Найдены в кэше:")
            for game, file_id in old_ids_cache.items():
                print(f"   {game}: {file_id}")
        else:
            print("⚠️  В кэше не найдены")

        # Пытаемся найти в базе данных
        print("\n🔍 Поиск старых file_id в базе данных...")
        old_ids_db = await get_old_file_ids_from_db(db)

        if old_ids_db:
            print("✅ Найдены самые популярные photo_id в БД:")
            for game, data in old_ids_db.items():
                print(f"   {game}: {data['file_id']} (используется в {data['count']} профилях)")
        else:
            print("⚠️  В БД не найдены")

        # Объединяем результаты (приоритет кэшу)
        old_ids = {}
        for game in ['dota', 'cs']:
            if game in old_ids_cache:
                old_ids[game] = old_ids_cache[game]
            elif game in old_ids_db:
                old_ids[game] = old_ids_db[game]['file_id']

        print("\n" + "=" * 70)
        print("ВЫБЕРИТЕ РЕЖИМ МИГРАЦИИ:")
        print("=" * 70)
        print("1. [ТОЧЕЧНАЯ] Обновить только профили со СТАРЫМИ file_id")
        if old_ids:
            print(f"   (найдено {len(old_ids)} старых file_id, можно использовать автоматически)")
        else:
            print("   (потребуется ввести старые file_id вручную)")
        print("2. [ПОЛНАЯ] Обновить ВСЕ профили на новые аватарки")
        print("   (заменит photo_id у всех профилей)")
        print("3. [ОТМЕНА] Выйти без изменений")
        print("=" * 70)

        choice = input("\nВыберите режим (1/2/3): ").strip()

        if choice == "1":
            await migrate_by_old_ids(db, old_ids, new_dota_file_id, new_cs_file_id)
        elif choice == "2":
            await migrate_all_profiles(db, new_dota_file_id, new_cs_file_id)
        else:
            print("❌ Миграция отменена")
            return

        # Обновляем кэш
        print("\n⏳ Обновление кэша...")
        settings.cache_photo_id('avatar_dota', new_dota_file_id)
        settings.cache_photo_id('avatar_cs', new_cs_file_id)
        print("✅ Кэш обновлен")

        print("\n" + "=" * 70)
        print("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ ОШИБКА при выполнении миграции: {e}")
        logger.exception("Детали ошибки:")
        raise

    finally:
        print("\n🔌 Закрытие соединений...")
        await db.close()
        await bot.session.close()
        print("=" * 70)

async def migrate_by_old_ids(db, old_ids_auto, new_dota_id, new_cs_id):
    """Миграция по старым file_id"""
    print("\n" + "=" * 70)
    print("РЕЖИМ: ТОЧЕЧНАЯ МИГРАЦИЯ")
    print("=" * 70)

    # Запрашиваем старые file_id
    if old_ids_auto:
        print("\nНайдены старые file_id автоматически.")
        print("Нажмите Enter для использования или введите свои вручную:")
    else:
        print("\nВведите старые file_id вручную:")

    old_dota = input(f"Старый Dota 2 file_id [{old_ids_auto.get('dota', '')}]: ").strip()
    old_dota = old_dota or old_ids_auto.get('dota')

    old_cs = input(f"Старый CS2 file_id [{old_ids_auto.get('cs', '')}]: ").strip()
    old_cs = old_cs or old_ids_auto.get('cs')

    if not old_dota and not old_cs:
        print("❌ Не указаны старые file_id. Миграция невозможна.")
        return

    async with db._pg_pool.acquire() as conn:
        total_updated = 0

        # Обновляем Dota 2
        if old_dota:
            print(f"\n⏳ Поиск профилей Dota 2 с file_id: {old_dota}")
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM profiles
                WHERE game = 'dota' AND photo_id = $1
            """, old_dota)

            if count > 0:
                print(f"📊 Найдено профилей: {count}")
                confirm = input(f"Обновить {count} профилей Dota 2? (yes/no): ").strip().lower()

                if confirm == 'yes':
                    await conn.execute("""
                        UPDATE profiles
                        SET photo_id = $1
                        WHERE game = 'dota' AND photo_id = $2
                    """, new_dota_id, old_dota)
                    print(f"✅ Обновлено {count} профилей Dota 2")
                    total_updated += count
            else:
                print("ℹ️  Профилей со старым file_id не найдено")

        # Обновляем CS2
        if old_cs:
            print(f"\n⏳ Поиск профилей CS2 с file_id: {old_cs}")
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM profiles
                WHERE game = 'cs' AND photo_id = $1
            """, old_cs)

            if count > 0:
                print(f"📊 Найдено профилей: {count}")
                confirm = input(f"Обновить {count} профилей CS2? (yes/no): ").strip().lower()

                if confirm == 'yes':
                    await conn.execute("""
                        UPDATE profiles
                        SET photo_id = $1
                        WHERE game = 'cs' AND photo_id = $2
                    """, new_cs_id, old_cs)
                    print(f"✅ Обновлено {count} профилей CS2")
                    total_updated += count
            else:
                print("ℹ️  Профилей со старым file_id не найдено")

        print(f"\n📊 Всего обновлено профилей: {total_updated}")

async def migrate_all_profiles(db, new_dota_id, new_cs_id):
    """Миграция всех профилей"""
    print("\n" + "=" * 70)
    print("РЕЖИМ: ПОЛНАЯ МИГРАЦИЯ")
    print("⚠️  ВНИМАНИЕ: Это заменит photo_id у ВСЕХ профилей!")
    print("=" * 70)

    async with db._pg_pool.acquire() as conn:
        # Считаем профили
        dota_count = await conn.fetchval("""
            SELECT COUNT(*) FROM profiles WHERE game = 'dota'
        """)

        cs_count = await conn.fetchval("""
            SELECT COUNT(*) FROM profiles WHERE game = 'cs'
        """)

        total = dota_count + cs_count

        print(f"\n📊 Будет обновлено:")
        print(f"   Dota 2: {dota_count} профилей")
        print(f"   CS2: {cs_count} профилей")
        print(f"   Всего: {total} профилей")
        print("\n⚠️  У всех пользователей будет установлена новая дефолтная аватарка!")
        print("⚠️  Включая тех, у кого была своя собственная фотография!")

        confirm = input("\n❓ ВЫ УВЕРЕНЫ? Введите 'YES I AM SURE' для продолжения: ").strip()

        if confirm != "YES I AM SURE":
            print("❌ Миграция отменена")
            return

        # Обновляем все профили
        print("\n⏳ Обновление всех профилей Dota 2...")
        await conn.execute("""
            UPDATE profiles
            SET photo_id = $1
            WHERE game = 'dota'
        """, new_dota_id)
        print(f"✅ Обновлено {dota_count} профилей Dota 2")

        print("⏳ Обновление всех профилей CS2...")
        await conn.execute("""
            UPDATE profiles
            SET photo_id = $1
            WHERE game = 'cs'
        """, new_cs_id)
        print(f"✅ Обновлено {cs_count} профилей CS2")

        print(f"\n📊 Всего обновлено: {total} профилей")

if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except KeyboardInterrupt:
        print("\n\n⚠️  Миграция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
