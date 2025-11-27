#!/usr/bin/env python3
"""
Скрипт для заполнения БД тестовыми данными
Создает реалистичные профили для Dota 2 и CS2
"""
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.database import Database
from config.settings import RATINGS, POSITIONS, COUNTRIES_DICT, GOALS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Русские имена
FIRST_NAMES = [
    "Александр", "Дмитрий", "Максим", "Андрей", "Артем", "Иван", "Михаил", "Даниил",
    "Егор", "Никита", "Владислав", "Кирилл", "Илья", "Алексей", "Роман", "Сергей",
    "Павел", "Денис", "Тимофей", "Владимир", "Константин", "Георгий", "Станислав",
    "Глеб", "Матвей", "Арсений", "Валентин", "Виктор", "Юрий", "Борис",
    "Анастасия", "Мария", "Дарья", "Полина", "Екатерина", "Алина", "Ксения",
    "Виктория", "София", "Анна", "Валерия", "Елизавета", "Вероника", "Кристина"
]

LAST_NAMES = [
    "Иванов", "Петров", "Сидоров", "Смирнов", "Козлов", "Волков", "Соколов",
    "Новиков", "Морозов", "Лебедев", "Васильев", "Павлов", "Михайлов", "Федоров",
    "Алексеев", "Егоров", "Николаев", "Романов", "Кузнецов", "Попов", "Орлов",
    "Макаров", "Григорьев", "Семенов", "Степанов", "Борисов", "Захаров", "Королев",
    "Денисов", "Андреев", "Тихонов", "Соловьев", "Крылов", "Богданов", "Медведев"
]

# Никнеймы в стиле геймеров
NICKNAME_PREFIXES = [
    "Pro", "God", "King", "Dark", "Shadow", "Silent", "Crazy", "Mad", "Lost",
    "Frost", "Fire", "Storm", "Night", "Blood", "Ice", "Mega", "Ultra", "Super",
    "Master", "Lord", "Toxic", "Savage", "Apex", "Neo", "Cyber", "Immortal"
]

NICKNAME_BASES = [
    "Player", "Gamer", "Slayer", "Hunter", "Killer", "Sniper", "Warrior", "Demon",
    "Dragon", "Wolf", "Tiger", "Eagle", "Phantom", "Ghost", "Knight", "Wizard",
    "Ninja", "Samurai", "Legend", "Hero", "Champion", "Beast", "Viper", "Reaper"
]

NICKNAME_SUFFIXES = [
    "228", "777", "666", "420", "999", "123", "2k", "pro", "gg", "ez",
    "uwu", "owo", "xd", "lol", "kek", "top", "god", "1337"
]

# Дополнительная информация
ADDITIONAL_INFO_TEMPLATES = [
    "Играю каждый день после работы, ищу адекватную команду",
    "Токсиков в игнор, хочу найти постоянный стак",
    "Серьезно отношусь к игре, цель - развитие",
    "Общительный, веселый, без тильта",
    "Играю на результат, готов слушать капитана",
    "Микрофон есть, дискорд есть, голова на месте",
    "Не тильтую, играю в свое удовольствие",
    "Ищу друзей для катки, без токсичности",
    "Стараюсь играть на максимум, учусь на ошибках",
    "Адекватность превыше всего, играю для фана",
    "Опыт игры больше 5 лет, знаю мету",
    "Коммуникабельный, умею работать в команде",
    "Играю агрессивно но без фидов",
    "Готов слушать советы, хочу прогрессировать",
    "Без драмы, просто играть и побеждать",
    None, None, None  # Некоторые без доп. инфы
]

# Роли
ROLES = ['player', 'player', 'player', 'player', 'coach', 'manager']  # Больше игроков

def generate_telegram_id(existing_ids: set):
    """Генерация уникального telegram ID"""
    while True:
        telegram_id = random.randint(100000000, 999999999)
        if telegram_id not in existing_ids:
            existing_ids.add(telegram_id)
            return telegram_id

def generate_username():
    """Генерация username в стиле Telegram"""
    base = random.choice([
        f"{random.choice(FIRST_NAMES).lower()}_{random.randint(1, 999)}",
        f"{random.choice(NICKNAME_BASES).lower()}{random.randint(10, 9999)}",
        f"{random.choice(NICKNAME_PREFIXES).lower()}_{random.choice(NICKNAME_BASES).lower()}",
        None  # Некоторые без username
    ])
    return base

def generate_name():
    """Генерация полного имени"""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)

    # Корректируем фамилию для женских имен
    if first in ["Анастасия", "Мария", "Дарья", "Полина", "Екатерина",
                 "Алина", "Ксения", "Виктория", "София", "Анна",
                 "Валерия", "Елизавета", "Вероника", "Кристина"]:
        if last.endswith('ов'):
            last = last[:-2] + 'ова'
        elif last.endswith('ев'):
            last = last[:-2] + 'ева'
        elif last.endswith('ин'):
            last = last[:-2] + 'ина'

    return f"{first} {last}"

def generate_nickname():
    """Генерация игрового никнейма"""
    style = random.randint(1, 5)

    if style == 1:
        return f"{random.choice(NICKNAME_PREFIXES)}{random.choice(NICKNAME_BASES)}"
    elif style == 2:
        return f"{random.choice(NICKNAME_BASES)}{random.choice(NICKNAME_SUFFIXES)}"
    elif style == 3:
        return f"{random.choice(NICKNAME_PREFIXES)}_{random.choice(NICKNAME_BASES)}"
    elif style == 4:
        return f"{random.choice(NICKNAME_BASES)}_{random.choice(NICKNAME_SUFFIXES)}"
    else:
        return f"{random.choice(NICKNAME_PREFIXES)}{random.choice(NICKNAME_SUFFIXES)}"

def generate_age():
    """Генерация возраста (больше людей 18-25)"""
    weights = [
        (16, 17, 5),   # 16-17: 5%
        (18, 22, 35),  # 18-22: 35%
        (23, 27, 30),  # 23-27: 30%
        (28, 35, 20),  # 28-35: 20%
        (36, 45, 10),  # 36-45: 10%
    ]

    range_choice = random.choices(weights, weights=[w[2] for w in weights])[0]
    return random.randint(range_choice[0], range_choice[1])

def generate_positions(game):
    """Генерация позиций (1-3 позиции)"""
    positions_list = list(POSITIONS[game].keys())
    num_positions = random.choices([1, 2, 3], weights=[50, 35, 15])[0]
    return random.sample(positions_list, num_positions)

def generate_goals():
    """Генерация целей"""
    goals_list = list(GOALS.keys())

    # Иногда только одна цель, иногда несколько
    if random.random() < 0.4:
        return [random.choice(goals_list)]
    else:
        num_goals = random.randint(1, len(goals_list))
        return random.sample(goals_list, num_goals)

def generate_region():
    """Генерация региона (больше СНГ стран)"""
    cis_countries = ["russia", "belarus", "ukraine", "kazakhstan", "armenia",
                     "azerbaijan", "georgia", "moldova"]
    other_countries = list(set(COUNTRIES_DICT.keys()) - set(cis_countries))

    # 70% СНГ, 30% остальные
    if random.random() < 0.7:
        return random.choice(cis_countries)
    else:
        return random.choice(other_countries)

def generate_rating(game):
    """Генерация рейтинга"""
    ratings_list = list(RATINGS[game].keys())

    if game == "dota":
        # Нормальное распределение для Dota (больше в середине)
        weights = [5, 10, 15, 20, 20, 15, 10, 3, 1, 0.5, 0.3, 0.2]
    else:  # CS
        # Для CS2 тоже нормальное распределение
        weights = [3, 5, 8, 12, 15, 17, 15, 12, 8, 4, 0.5, 0.3, 0.2, 0.05]

    return random.choices(ratings_list, weights=weights)[0]

def generate_additional_info():
    """Генерация дополнительной информации"""
    return random.choice(ADDITIONAL_INFO_TEMPLATES)

async def create_test_profile(db: Database, game: str, existing_ids: set):
    """Создание одного тестового профиля"""
    telegram_id = generate_telegram_id(existing_ids)
    username = generate_username()
    name = generate_name()
    nickname = generate_nickname()
    age = generate_age()
    rating = generate_rating(game)
    region = generate_region()
    positions = generate_positions(game)
    goals = generate_goals()
    additional_info = generate_additional_info()
    role = random.choice(ROLES)

    # Создаем пользователя
    await db.create_user(telegram_id, username, game)

    # Создаем профиль
    await db.update_user_profile(
        telegram_id=telegram_id,
        game=game,
        name=name,
        nickname=nickname,
        age=age,
        rating=rating,
        region=region,
        positions=positions,
        goals=goals,
        additional_info=additional_info,
        photo_id=None,  # Фото пока не добавляем
        profile_url=None,
        username=username,
        role=role
    )

    return telegram_id

async def create_test_likes_and_matches(db: Database, user_ids: list, game: str):
    """Создание тестовых лайков и матчей"""
    num_likes = random.randint(len(user_ids) // 4, len(user_ids) // 2)
    created_likes = set()  # Отслеживаем созданные лайки

    for _ in range(num_likes):
        # Пробуем найти уникальную пару
        attempts = 0
        while attempts < 10:
            from_user = random.choice(user_ids)
            to_user = random.choice(user_ids)

            like_pair = (from_user, to_user)

            if from_user != to_user and like_pair not in created_likes:
                try:
                    # С вероятностью 30% добавляем сообщение к лайку
                    message = None
                    if random.random() < 0.3:
                        messages = [
                            "Привет! Давай катнем?",
                            "Ищу стак, го?",
                            "Хочу поиграть на твоей роли, научишь?",
                            "Адекватный игрок? Го в команду",
                            "Го постоянная катка?",
                            None
                        ]
                        message = random.choice(messages)

                    await db.add_like(from_user, to_user, game, message)
                    created_likes.add(like_pair)
                    break
                except Exception as e:
                    # Игнорируем ошибки дубликатов
                    pass

            attempts += 1

async def create_test_skips(db: Database, user_ids: list, game: str):
    """Создание тестовых пропусков в поиске"""
    num_skips = random.randint(len(user_ids) // 10, len(user_ids) // 5)

    for _ in range(num_skips):
        user_id = random.choice(user_ids)
        skipped_user_id = random.choice(user_ids)

        if user_id != skipped_user_id:
            try:
                await db.add_search_skip(user_id, skipped_user_id, game)
            except:
                pass

async def seed_database(num_dota_profiles: int = 50, num_cs_profiles: int = 50):
    """Основная функция заполнения БД"""
    print("=" * 70)
    print("🌱 ЗАПОЛНЕНИЕ БД ТЕСТОВЫМИ ДАННЫМИ")
    print("=" * 70)

    db = Database()

    try:
        print("\n🔌 Подключение к базе данных...")
        await db.init()
        print("✅ Подключение установлено\n")

        # Получаем текущую статистику
        stats_before = await db.get_database_stats()
        print("📊 Текущее состояние БД:")
        print(f"   Пользователей: {stats_before.get('users_total', 0)}")
        print(f"   Профилей: {stats_before.get('profiles_total', 0)}")
        print(f"   Лайков: {stats_before.get('likes_total', 0)}")
        print(f"   Матчей: {stats_before.get('matches_total', 0)}\n")

        # Подтверждение
        print(f"⚠️  Будет создано:")
        print(f"   - {num_dota_profiles} профилей для Dota 2")
        print(f"   - {num_cs_profiles} профилей для CS2")
        print(f"   - Случайные лайки между пользователями")
        print(f"   - Случайные матчи\n")

        confirm = input("❓ Продолжить? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("❌ Отменено пользователем")
            return

        # Отслеживание уникальных telegram_id
        existing_ids = set()

        # Создаем профили для Dota 2
        print(f"\n⏳ Создание {num_dota_profiles} профилей для Dota 2...")
        dota_user_ids = []
        for i in range(num_dota_profiles):
            user_id = await create_test_profile(db, "dota", existing_ids)
            dota_user_ids.append(user_id)
            if (i + 1) % 10 == 0:
                print(f"   ✓ Создано {i + 1}/{num_dota_profiles} профилей Dota 2")

        print(f"✅ Создано {num_dota_profiles} профилей Dota 2\n")

        # Создаем профили для CS2
        print(f"⏳ Создание {num_cs_profiles} профилей для CS2...")
        cs_user_ids = []
        for i in range(num_cs_profiles):
            user_id = await create_test_profile(db, "cs", existing_ids)
            cs_user_ids.append(user_id)
            if (i + 1) % 10 == 0:
                print(f"   ✓ Создано {i + 1}/{num_cs_profiles} профилей CS2")

        print(f"✅ Создано {num_cs_profiles} профилей CS2\n")

        # Создаем профили для пользователей с обеими играми (10-15% от общего числа)
        num_dual_users = min(num_dota_profiles, num_cs_profiles) // 8
        if num_dual_users > 0:
            print(f"⏳ Создание {num_dual_users} пользователей с профилями в обеих играх...")
            dual_user_ids = []
            for i in range(num_dual_users):
                # Используем один telegram_id для обеих игр
                telegram_id = generate_telegram_id(existing_ids)
                username = generate_username()
                name = generate_name()

                # Создаем профиль для Dota 2
                await db.create_user(telegram_id, username, "dota")
                await db.update_user_profile(
                    telegram_id=telegram_id,
                    game="dota",
                    name=name,
                    nickname=generate_nickname(),
                    age=generate_age(),
                    rating=generate_rating("dota"),
                    region=generate_region(),
                    positions=generate_positions("dota"),
                    goals=generate_goals(),
                    additional_info=generate_additional_info(),
                    photo_id=None,
                    profile_url=None,
                    username=username,
                    role=random.choice(ROLES)
                )
                dota_user_ids.append(telegram_id)

                # Создаем профиль для CS2 для того же пользователя
                await db.switch_game(telegram_id, "cs")
                await db.update_user_profile(
                    telegram_id=telegram_id,
                    game="cs",
                    name=name,  # То же имя
                    nickname=generate_nickname(),  # Но другой никнейм
                    age=generate_age(),
                    rating=generate_rating("cs"),
                    region=generate_region(),
                    positions=generate_positions("cs"),
                    goals=generate_goals(),
                    additional_info=generate_additional_info(),
                    photo_id=None,
                    profile_url=None,
                    username=username,
                    role=random.choice(ROLES)
                )
                cs_user_ids.append(telegram_id)
                dual_user_ids.append(telegram_id)

            print(f"✅ Создано {num_dual_users} пользователей с профилями в обеих играх\n")

        # Создаем лайки и матчи для Dota 2
        print("⏳ Генерация лайков и матчей для Dota 2...")
        await create_test_likes_and_matches(db, dota_user_ids, "dota")
        print("✅ Лайки и матчи для Dota 2 созданы\n")

        # Создаем лайки и матчи для CS2
        print("⏳ Генерация лайков и матчей для CS2...")
        await create_test_likes_and_matches(db, cs_user_ids, "cs")
        print("✅ Лайки и матчи для CS2 созданы\n")

        # Создаем тестовые пропуски
        print("⏳ Генерация пропусков в поиске для Dota 2...")
        await create_test_skips(db, dota_user_ids, "dota")
        print("✅ Пропуски для Dota 2 созданы\n")

        print("⏳ Генерация пропусков в поиске для CS2...")
        await create_test_skips(db, cs_user_ids, "cs")
        print("✅ Пропуски для CS2 созданы\n")

        # Финальная статистика
        stats_after = await db.get_database_stats()
        print("=" * 70)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 70)
        print(f"Пользователей: {stats_after.get('users_total', 0)}")
        print(f"Профилей: {stats_after.get('profiles_total', 0)}")
        print(f"Лайков: {stats_after.get('likes_total', 0)}")
        print(f"Матчей: {stats_after.get('matches_total', 0)}")

        if 'games_breakdown' in stats_after:
            print("\nПо играм:")
            for game, data in stats_after['games_breakdown'].items():
                game_name = "Dota 2" if game == "dota" else "CS2"
                print(f"  {game_name}: {data['profiles']} профилей, {data['users']} уникальных пользователей")

        # Дополнительная статистика
        async with db._pg_pool.acquire() as conn:
            # Подсчет пропусков
            skips_count = await conn.fetchval("SELECT COUNT(*) FROM search_skipped")
            print(f"\nПропусков в поиске: {skips_count or 0}")

            # Подсчет пользователей с обеими играми
            dual_users = await conn.fetchval("""
                SELECT COUNT(*)
                FROM (
                    SELECT telegram_id
                    FROM profiles
                    GROUP BY telegram_id
                    HAVING COUNT(DISTINCT game) = 2
                ) AS dual_users_subquery
            """)
            print(f"Пользователей с профилями в обеих играх: {dual_users or 0}")

            # Статистика по ролям
            roles_stats = await conn.fetch("""
                SELECT role, COUNT(*) as count
                FROM profiles
                GROUP BY role
            """)
            if roles_stats:
                print("\nПо ролям:")
                for row in roles_stats:
                    role_name = {'player': 'Игроки', 'coach': 'Тренеры', 'manager': 'Менеджеры'}.get(row['role'], row['role'])
                    print(f"  {role_name}: {row['count']}")

        print("\n✅ ЗАПОЛНЕНИЕ БД ЗАВЕРШЕНО УСПЕШНО!")
        print("🎮 Теперь можно тестировать бота с реальными данными")
        print("\n💡 Советы для тестирования:")
        print("   - Используй команду /start в боте")
        print("   - Попробуй поиск с разными фильтрами")
        print("   - Проверь систему лайков и матчей")
        print("   - Посмотри как работает редактирование профиля\n")

    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        logger.exception("Детали ошибки:")
        raise

    finally:
        await db.close()
        print("🔌 Соединение закрыто")
        print("=" * 70)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Заполнение БД тестовыми данными')
    parser.add_argument('--dota', type=int, default=50, help='Количество Dota 2 профилей (default: 50)')
    parser.add_argument('--cs', type=int, default=50, help='Количество CS2 профилей (default: 50)')

    args = parser.parse_args()

    try:
        asyncio.run(seed_database(args.dota, args.cs))
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
