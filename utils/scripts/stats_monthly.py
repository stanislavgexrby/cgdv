#!/usr/bin/env python3
"""
Скрипт для сбора статистики бота за месяц
"""
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


async def get_monthly_stats():
    """Получение статистики за последний месяц"""

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
        # Определяем период - последние 30 дней
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        print("\n" + "=" * 70)
        print(f"📊 СТАТИСТИКА БОТА ЗА ПОСЛЕДНИЙ МЕСЯЦ")
        print(f"📅 Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
        print("=" * 70)

        # === ПОЛЬЗОВАТЕЛИ ===
        print("\n👥 ПОЛЬЗОВАТЕЛИ:")

        # Новые пользователи за месяц
        new_users = await conn.fetchval("""
            SELECT COUNT(*) FROM users
            WHERE created_at >= $1 AND created_at <= $2
        """, start_date, end_date)

        # Всего пользователей
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")

        # Пользователи с профилями
        users_with_profiles = await conn.fetchval("""
            SELECT COUNT(DISTINCT telegram_id) FROM profiles
        """)

        print(f"  Новых пользователей: {new_users}")
        print(f"  Всего пользователей: {total_users}")
        print(f"  Пользователей с профилями: {users_with_profiles}")

        # === ПРОФИЛИ ===
        print("\n📝 ПРОФИЛИ:")

        # Новые профили за месяц
        new_profiles = await conn.fetchval("""
            SELECT COUNT(*) FROM profiles
            WHERE created_at >= $1 AND created_at <= $2
        """, start_date, end_date)

        # Обновленные профили за месяц
        updated_profiles = await conn.fetchval("""
            SELECT COUNT(*) FROM profiles
            WHERE updated_at >= $1 AND updated_at <= $2
            AND created_at < $1
        """, start_date, end_date)

        # Профили по играм
        profiles_by_game = await conn.fetch("""
            SELECT game, COUNT(*) as count
            FROM profiles
            WHERE created_at >= $1 AND created_at <= $2
            GROUP BY game
            ORDER BY count DESC
        """, start_date, end_date)

        # Всего профилей
        total_profiles = await conn.fetchval("SELECT COUNT(*) FROM profiles")

        print(f"  Новых профилей: {new_profiles}")
        print(f"  Обновленных профилей: {updated_profiles}")
        print(f"  Всего профилей: {total_profiles}")

        if profiles_by_game:
            print("\n  По играм:")
            for row in profiles_by_game:
                game_name = "Dota 2" if row['game'] == 'dota' else "CS2"
                print(f"    {game_name}: {row['count']}")

        # Профили по ролям
        profiles_by_role = await conn.fetch("""
            SELECT role, COUNT(*) as count
            FROM profiles
            WHERE created_at >= $1 AND created_at <= $2
            GROUP BY role
            ORDER BY count DESC
        """, start_date, end_date)

        if profiles_by_role:
            print("\n  По ролям:")
            for row in profiles_by_role:
                role_name = {
                    'player': 'Игрок',
                    'coach': 'Тренер',
                    'manager': 'Менеджер'
                }.get(row['role'], row['role'] or 'player')
                print(f"    {role_name}: {row['count']}")

        # === ЛАЙКИ И МАТЧИ ===
        print("\n❤️  ЛАЙКИ И МАТЧИ:")

        # Лайки за месяц
        new_likes = await conn.fetchval("""
            SELECT COUNT(*) FROM likes
            WHERE created_at >= $1 AND created_at <= $2
        """, start_date, end_date)

        # Лайки с сообщениями
        likes_with_message = await conn.fetchval("""
            SELECT COUNT(*) FROM likes
            WHERE created_at >= $1 AND created_at <= $2
            AND message IS NOT NULL AND message != ''
        """, start_date, end_date)

        # Матчи за месяц
        new_matches = await conn.fetchval("""
            SELECT COUNT(*) FROM matches
            WHERE created_at >= $1 AND created_at <= $2
        """, start_date, end_date)

        # Всего лайков и матчей
        total_likes = await conn.fetchval("SELECT COUNT(*) FROM likes")
        total_matches = await conn.fetchval("SELECT COUNT(*) FROM matches")

        print(f"  Новых лайков: {new_likes}")
        print(f"  Лайков с сообщением: {likes_with_message}")
        print(f"  Новых матчей: {new_matches}")
        print(f"  Всего лайков: {total_likes}")
        print(f"  Всего матчей: {total_matches}")

        # Конверсия лайков в матчи
        if new_likes > 0:
            conversion_rate = (new_matches / new_likes) * 100
            print(f"  Конверсия лайков в матчи: {conversion_rate:.1f}%")

        # Лайки по играм
        likes_by_game = await conn.fetch("""
            SELECT game, COUNT(*) as count
            FROM likes
            WHERE created_at >= $1 AND created_at <= $2
            GROUP BY game
            ORDER BY count DESC
        """, start_date, end_date)

        if likes_by_game:
            print("\n  По играм:")
            for row in likes_by_game:
                game_name = "Dota 2" if row['game'] == 'dota' else "CS2"
                print(f"    {game_name}: {row['count']}")

        # === АКТИВНОСТЬ ===
        print("\n📈 АКТИВНОСТЬ:")

        # Самые активные пользователи по лайкам
        top_likers = await conn.fetch("""
            SELECT from_user, COUNT(*) as likes_count
            FROM likes
            WHERE created_at >= $1 AND created_at <= $2
            GROUP BY from_user
            ORDER BY likes_count DESC
            LIMIT 5
        """, start_date, end_date)

        if top_likers:
            print("\n  Топ-5 пользователей по отправленным лайкам:")
            for i, row in enumerate(top_likers, 1):
                print(f"    {i}. User ID {row['from_user']}: {row['likes_count']} лайков")

        # Самые популярные пользователи по полученным лайкам
        top_liked = await conn.fetch("""
            SELECT to_user, COUNT(*) as likes_received
            FROM likes
            WHERE created_at >= $1 AND created_at <= $2
            GROUP BY to_user
            ORDER BY likes_received DESC
            LIMIT 5
        """, start_date, end_date)

        if top_liked:
            print("\n  Топ-5 пользователей по полученным лайкам:")
            for i, row in enumerate(top_liked, 1):
                print(f"    {i}. User ID {row['to_user']}: {row['likes_received']} лайков")

        # === МОДЕРАЦИЯ ===
        print("\n🛡️  МОДЕРАЦИЯ:")

        # Жалобы за месяц
        new_reports = await conn.fetchval("""
            SELECT COUNT(*) FROM reports
            WHERE created_at >= $1 AND created_at <= $2
        """, start_date, end_date)

        # Обработанные жалобы
        resolved_reports = await conn.fetchval("""
            SELECT COUNT(*) FROM reports
            WHERE reviewed_at >= $1 AND reviewed_at <= $2
        """, start_date, end_date)

        # Новые баны за месяц
        new_bans = await conn.fetchval("""
            SELECT COUNT(*) FROM bans
            WHERE created_at >= $1 AND created_at <= $2
        """, start_date, end_date)

        # Активные баны
        active_bans = await conn.fetchval("""
            SELECT COUNT(*) FROM bans
            WHERE expires_at > NOW()
        """)

        print(f"  Новых жалоб: {new_reports}")
        print(f"  Обработано жалоб: {resolved_reports}")
        print(f"  Новых банов: {new_bans}")
        print(f"  Активных банов: {active_bans}")

        # === РЕКЛАМА ===
        print("\n📢 РЕКЛАМА:")

        # Всего рекламных постов
        total_ads = await conn.fetchval("SELECT COUNT(*) FROM ad_posts")
        active_ads = await conn.fetchval("""
            SELECT COUNT(*) FROM ad_posts
            WHERE is_active = TRUE
            AND (expires_at IS NULL OR expires_at > NOW())
        """)

        print(f"  Всего рекламных постов: {total_ads}")
        print(f"  Активных: {active_ads}")

        # === ДОПОЛНИТЕЛЬНАЯ СТАТИСТИКА ===
        print("\n📊 ДОПОЛНИТЕЛЬНАЯ СТАТИСТИКА:")

        # Средний возраст пользователей
        avg_age = await conn.fetchval("""
            SELECT AVG(age)::int FROM profiles
            WHERE age IS NOT NULL AND age > 0
        """)

        # Самые популярные регионы
        top_regions = await conn.fetch("""
            SELECT region, COUNT(*) as count
            FROM profiles
            WHERE region IS NOT NULL AND region != 'any'
            GROUP BY region
            ORDER BY count DESC
            LIMIT 5
        """)

        if avg_age:
            print(f"  Средний возраст: {avg_age} лет")

        if top_regions:
            print("\n  Топ-5 регионов:")
            for i, row in enumerate(top_regions, 1):
                print(f"    {i}. {row['region']}: {row['count']} пользователей")

        # === ОБЩАЯ СТАТИСТИКА ===
        print("\n" + "=" * 70)
        print("📊 ОБЩАЯ СТАТИСТИКА:")
        print(f"  Новых пользователей за месяц: {new_users}")
        print(f"  Новых профилей: {new_profiles}")
        print(f"  Новых лайков: {new_likes}")
        print(f"  Новых матчей: {new_matches}")
        print(f"  Активность: {new_likes + new_matches} взаимодействий")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        raise

    finally:
        await conn.close()
        print("\n🔌 Соединение с БД закрыто")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("📊 СБОР СТАТИСТИКИ БОТА")
    print("=" * 70)

    try:
        asyncio.run(get_monthly_stats())
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        exit(1)
