import asyncpg
import redis.asyncio as redis
import json
import os
import hashlib
import logging
from typing import List, Dict, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Database:
    """Объединенный класс для работы с PostgreSQL + Redis с оптимизациями"""
    
    def __init__(self):
        self._pg_pool = None
        self._redis = None
        self._connection_retries = 3
        self._cache_ttl = {
            'user': 300,          # 5 минут для пользователей
            'profile': 600,       # 10 минут для профилей 
            'search': 180,        # 3 минуты для результатов поиска
            'matches': 900,       # 15 минут для матчей
            'likes': 300          # 5 минут для лайков
        }
    
    async def init(self):
        """Инициализация подключений с улучшенной обработкой ошибок"""
        logger.info("Начинаем инициализацию базы данных...")
        try:
            await self._init_postgres()
            logger.info("PostgreSQL инициализирован успешно")
            await self._init_redis()  
            logger.info("Redis инициализирован успешно")
            logger.info("✅ Database (PostgreSQL + Redis) готова")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            raise

    async def close(self):
        """Закрытие подключений"""
        if self._pg_pool:
            await self._pg_pool.close()
        if self._redis:
            await self._redis.close()
        logger.info("Database закрыта")

    async def _init_postgres(self):
        """Инициализация PostgreSQL с улучшенными настройками пула"""
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'teammates')
        db_user = os.getenv('DB_USER', 'teammates_user')
        db_password = os.getenv('DB_PASSWORD', '')

        if not db_password:
            raise ValueError("DB_PASSWORD не установлен в переменных окружения")

        connection_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

        self._pg_pool = await asyncpg.create_pool(
            connection_url, 
            min_size=3,           # Минимум подключений
            max_size=15,          # Максимум подключений
            max_queries=50000,    # Максимум запросов на подключение
            max_inactive_connection_lifetime=300.0,  # 5 минут жизни неактивных соединений
            command_timeout=30.0, # 30 секунд таймаут на команду
        )
        await self._create_tables()
        logger.info("✅ PostgreSQL подключена с оптимизированным пулом")

    async def _init_redis(self):
        """Инициализация Redis с connection pooling"""
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = os.getenv('REDIS_PORT', '6379')
        redis_db = os.getenv('REDIS_DB', '0')

        redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

        self._redis = redis.from_url(
            redis_url, 
            decode_responses=True,
            max_connections=20,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={}
        )
        await self._redis.ping()
        logger.info("✅ Redis подключен с connection pooling")

    async def _create_tables(self):
        """Создание таблиц с оптимизированными индексами"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    username TEXT,
                    current_game TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS likes (
                    id SERIAL PRIMARY KEY,
                    from_user BIGINT,
                    to_user BIGINT,
                    game TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(from_user, to_user, game)
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    id SERIAL PRIMARY KEY,
                    user1 BIGINT,
                    user2 BIGINT,
                    game TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user1, user2, game)
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS skipped_likes (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    skipped_user_id BIGINT,
                    game TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, skipped_user_id, game)
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS search_skipped (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    skipped_user_id BIGINT,
                    game TEXT,
                    skip_count INTEGER DEFAULT 1,
                    last_skipped TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, skipped_user_id, game)
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    reporter_id BIGINT,
                    reported_user_id BIGINT,
                    game TEXT,
                    report_reason TEXT DEFAULT 'inappropriate_content',
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    admin_id BIGINT,
                    UNIQUE(reporter_id, reported_user_id, game)
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS bans (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE,
                    reason TEXT DEFAULT 'нарушение правил',
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT,
                    game TEXT,
                    name TEXT,
                    nickname TEXT,
                    age INTEGER,
                    rating TEXT,
                    region TEXT DEFAULT 'eeu',
                    positions JSONB DEFAULT '[]'::jsonb,
                    goals JSONB DEFAULT '["any"]'::jsonb,
                    additional_info TEXT,
                    photo_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(telegram_id, game)
                )
            ''')

            optimized_indexes = [
                # === ОСНОВНЫЕ ИНДЕКСЫ ===
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_game ON profiles(game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_telegram_id_game ON profiles(telegram_id, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_current_game ON users(current_game)",

                # === ИНДЕКСЫ ДЛЯ ЛАЙКОВ ===
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_to_game ON likes(to_user, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_from_game ON likes(from_user, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_from_to_game ON likes(from_user, to_user, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_created_at_desc ON likes(created_at DESC)",

                # === ИНДЕКСЫ ДЛЯ МАТЧЕЙ ===
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_matches_user1_game ON matches(user1, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_matches_user2_game ON matches(user2, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_matches_users_game ON matches(user1, user2, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_matches_created_at_desc ON matches(created_at DESC)",

                # === ИНДЕКСЫ ДЛЯ ПОИСКА ===
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_game_rating ON profiles(game, rating)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_game_region ON profiles(game, region)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_game_active ON profiles(game, telegram_id) WHERE telegram_id IS NOT NULL",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_goals_gin ON profiles USING gin (goals)",

                # === GIN ИНДЕКС ДЛЯ ПОЗИЦИЙ ===
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_positions_gin ON profiles USING gin (positions)",

                # === СОСТАВНЫЕ ИНДЕКСЫ ДЛЯ СЛОЖНЫХ ЗАПРОСОВ ===
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_search_composite ON profiles(game, rating, region) WHERE telegram_id IS NOT NULL",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_mutual_check ON likes(to_user, from_user, game)",

                # === ИНДЕКСЫ ДЛЯ ПРОПУСКОВ ===
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_skipped_user_game ON search_skipped(user_id, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_skipped_likes_user_game ON skipped_likes(user_id, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_skipped_composite ON search_skipped(user_id, skipped_user_id, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_skipped_likes_composite ON skipped_likes(user_id, skipped_user_id, game)",

                # === ИНДЕКСЫ ДЛЯ ОТЧЕТОВ И БАНОВ ===
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reports_status ON reports(status)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reports_reported_user_game ON reports(reported_user_id, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reports_created_at_desc ON reports(created_at DESC) WHERE status = 'pending'",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bans_user_expires ON bans(user_id, expires_at)",

                # === ЧАСТИЧНЫЕ ИНДЕКСЫ ДЛЯ АКТИВНЫХ ЗАПИСЕЙ ===
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_active_with_photo ON profiles(game, telegram_id) WHERE photo_id IS NOT NULL",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_updated_at ON profiles(updated_at)"
            ]

            try:
                await conn.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS goals JSONB DEFAULT '[\"any\"]'::jsonb")
                await conn.execute("UPDATE profiles SET goals = '[\"any\"]'::jsonb WHERE goals IS NULL")
            except Exception as e:
                logger.warning(f"Миграция поля goals: {e}")

            try:
                await conn.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS profile_url TEXT")
            except Exception as e:
                logger.warning(f"Миграция поля profile_url: {e}")

            for index_sql in optimized_indexes:
                try:
                    await conn.execute(index_sql)
                except Exception as e:
                    index_name = index_sql.split("idx_")[1].split(" ")[0] if "idx_" in index_sql else "unknown"
                    logger.warning(f"Индекс {index_name} уже существует или ошибка: {e}")

    def _format_profile(self, row) -> Dict:
        """Форматирование профиля с кэшированием"""
        if not row:
            return None

        profile = dict(row)

        # Обработка позиций
        positions = profile.get('positions', [])
        if isinstance(positions, str):
            try:
                positions = json.loads(positions)
            except:
                positions = []
        profile['positions'] = positions

        # Обработка целей
        goals = profile.get('goals', ['any'])
        if isinstance(goals, str):
            try:
                goals = json.loads(goals)
            except:
                goals = ['any']
        profile['goals'] = goals

        profile['current_game'] = profile.get('game')
        return profile

    def _generate_filters_hash(self, rating_filter, position_filter, region_filter, goals_filter) -> str:
        """Генерация хэша для фильтров поиска"""
        filters_str = f"{rating_filter or 'any'}_{position_filter or 'any'}_{region_filter or 'any'}_{goals_filter or 'any'}"
        return hashlib.md5(filters_str.encode()).hexdigest()[:8]

    # === ОПТИМИЗИРОВАННОЕ КЭШИРОВАНИЕ ===

    async def _get_cache(self, key: str):
        raw = await self._redis.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            return json.loads(raw)
        except Exception:
            return raw


    async def _set_cache(self, key: str, data, ttl: int = 600):
        """Сохранение в кэш с обработкой ошибок"""
        try:
            await self._redis.setex(key, ttl, json.dumps(data, default=str))
        except Exception as e:
            logger.warning(f"Ошибка записи в кэш {key}: {e}")

    async def _clear_user_cache(self, user_id: int):
        """Очистка всего кэша пользователя"""
        try:
            patterns = [
                f"user:{user_id}*",
                f"profile:{user_id}:*", 
                f"search:{user_id}:*",
                f"matches:{user_id}:*",
                f"likes:{user_id}:*"
            ]
            for pattern in patterns:
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"Ошибка очистки кэша пользователя {user_id}: {e}")

    async def _clear_pattern_cache(self, pattern: str):
        """Очистка кэша по паттерну"""
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception as e:
            logger.warning(f"Ошибка очистки кэша по паттерну {pattern}: {e}")

    # === ПОЛЬЗОВАТЕЛИ ===

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Получение пользователя с кэшированием"""
        cache_key = f"user:{telegram_id}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
            result = dict(row) if row else None

            if result:
                await self._set_cache(cache_key, result, self._cache_ttl['user'])

            return result

    async def create_user(self, telegram_id: int, username: str, game: str) -> bool:
        """Создание или обновление пользователя"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO users (telegram_id, username, current_game)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (telegram_id)
                   DO UPDATE SET username = $2, current_game = $3""",
                telegram_id, username, game
            )
            await self._clear_user_cache(telegram_id)
            return True

    async def switch_game(self, telegram_id: int, game: str) -> bool:
        """Переключение текущей игры"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET current_game = $1 WHERE telegram_id = $2",
                game, telegram_id
            )
            await self._clear_user_cache(telegram_id)
            return True

    # === ПРОФИЛИ ===

    async def get_user_profile(self, telegram_id: int, game: str) -> Optional[Dict]:
        """Получение профиля пользователя с кэшированием"""
        cache_key = f"profile:{telegram_id}:{game}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT p.*, u.username
                FROM profiles p
                JOIN users u ON p.telegram_id = u.telegram_id
                WHERE p.telegram_id = $1 AND p.game = $2
            """, telegram_id, game)

            if not row:
                return None

            profile = self._format_profile(row)
            await self._set_cache(cache_key, profile, self._cache_ttl['profile'])
            return profile

    async def has_profile(self, telegram_id: int, game: str) -> bool:
        """Проверка наличия профиля с кэшированием"""
        profile = await self.get_user_profile(telegram_id, game)
        return profile is not None

    async def update_user_profile(self, telegram_id: int, game: str, name: str, nickname: str,
                        age: int, rating: str, region: str, positions: List[str],
                        goals: List[str], additional_info: str, photo_id: str = None,
                        profile_url: str = None) -> bool:
        """Создание/обновление профиля пользователя"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO profiles (telegram_id, game, name, nickname, age, rating, region, positions, goals, additional_info, photo_id, profile_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (telegram_id, game)
                DO UPDATE SET
                    name = $3, nickname = $4, age = $5, rating = $6,
                    region = $7, positions = $8, goals = $9, additional_info = $10, photo_id = $11, profile_url = $12''',
                telegram_id, game, name, nickname, age, rating, region,
                json.dumps(positions), json.dumps(goals), additional_info, photo_id, profile_url
            )
            await self._clear_user_cache(telegram_id)
            await self._clear_pattern_cache(f"search:*:{game}:*")
            return True

    async def delete_profile(self, telegram_id: int, game: str) -> bool:
        """Удаление профиля и связанных данных"""
        async with self._pg_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM likes WHERE (from_user = $1 OR to_user = $1) AND game = $2",
                    telegram_id, game
                )
                await conn.execute(
                    "DELETE FROM matches WHERE (user1 = $1 OR user2 = $1) AND game = $2",
                    telegram_id, game
                )
                await conn.execute(
                    "DELETE FROM skipped_likes WHERE (user_id = $1 OR skipped_user_id = $1) AND game = $2",
                    telegram_id, game
                )
                await conn.execute(
                    "DELETE FROM search_skipped WHERE (user_id = $1 OR skipped_user_id = $1) AND game = $2",
                    telegram_id, game
                )
                await conn.execute(
                    "DELETE FROM reports WHERE reported_user_id = $1 AND game = $2",
                    telegram_id, game
                )
                await conn.execute(
                    "DELETE FROM profiles WHERE telegram_id = $1 AND game = $2",
                    telegram_id, game
                )

                await self._clear_user_cache(telegram_id)
                await self._clear_pattern_cache(f"search:*:{game}:*")
                return True

    async def clear_invalid_photo(self, user_id: int, game: str) -> bool:
        """Очистка невалидного photo_id у пользователя"""
        try:
            async with self._pg_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE profiles SET photo_id = NULL WHERE telegram_id = $1 AND game = $2",
                    user_id, game
                )
                await self._clear_user_cache(user_id)
                logger.info(f"Очищен невалидный photo_id для пользователя {user_id} в игре {game}")
                return True
        except Exception as e:
            logger.error(f"Ошибка очистки photo_id: {e}")
            return False

    # === ОПТИМИЗИРОВАННЫЙ ПОИСК ===

    async def get_potential_matches(self, user_id: int, game: str,
                        rating_filter: str = None,
                        position_filter: str = None,
                        country_filter: str = None,
                        goals_filter: str = None,
                        limit: int = 10) -> List[Dict]:
        """Оптимизированный поиск потенциальных матчей"""

        filters_hash = self._generate_filters_hash(rating_filter, position_filter, country_filter, goals_filter)
        cache_key = f"search:{user_id}:{game}:{filters_hash}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        query = '''
            WITH excluded_users AS (
                SELECT DISTINCT to_user as user_id FROM likes
                WHERE from_user = $1 AND game = $2
                UNION
                SELECT DISTINCT reported_user_id as user_id FROM reports
                WHERE reporter_id = $1 AND game = $2
                UNION
                SELECT DISTINCT user_id FROM bans
                WHERE expires_at > CURRENT_TIMESTAMP
            )
            SELECT p.*, u.username
            FROM profiles p
            JOIN users u ON p.telegram_id = u.telegram_id
            WHERE p.telegram_id != $1
                AND p.game = $2
                AND p.telegram_id NOT IN (SELECT user_id FROM excluded_users WHERE user_id IS NOT NULL)
        '''

        params = [user_id, game]
        param_count = 2

        if rating_filter and rating_filter != 'any':
            param_count += 1
            query += f" AND p.rating = ${param_count}"
            params.append(rating_filter)

        if position_filter and position_filter != 'any':
            param_count += 1
            query += f" AND (p.positions ? ${param_count} OR p.positions ? 'any')"
            params.append(position_filter)

        if country_filter and country_filter != 'any':
            param_count += 1
            query += f" AND (p.region = ${param_count} OR p.region = 'any')"
            params.append(country_filter)

        if goals_filter and goals_filter != 'any':
            param_count += 1
            query += f" AND p.goals ? ${param_count}"
            params.append(goals_filter)

        param_count += 1
        query += f" ORDER BY p.created_at DESC, p.id LIMIT ${param_count}"
        params.append(limit * 3)

        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            all_results = [self._format_profile(row) for row in rows]

            import hashlib
            seed = int(hashlib.md5(f"{user_id}{game}".encode()).hexdigest()[:8], 16)
            import random
            random.seed(seed)
            random.shuffle(all_results)
            results = all_results[:limit]

            await self._set_cache(cache_key, results, self._cache_ttl['search'])
            return results

    async def add_search_skip(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        """Добавление пропуска в поиске"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO search_skipped (user_id, skipped_user_id, game, skip_count, last_skipped)
                   VALUES ($1, $2, $3, 1, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id, skipped_user_id, game)
                   DO UPDATE SET skip_count = search_skipped.skip_count + 1, last_skipped = CURRENT_TIMESTAMP''',
                user_id, skipped_user_id, game
            )
            return True

    # === ЛАЙКИ И МАТЧИ ===

    async def add_like(self, from_user: int, to_user: int, game: str) -> bool:
        """Добавление лайка с проверкой на матч (возвращает True если матч)"""
        async with self._pg_pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchval(
                    "SELECT 1 FROM likes WHERE from_user = $1 AND to_user = $2 AND game = $3",
                    from_user, to_user, game
                )
                if existing:
                    return False

                await conn.execute(
                    "INSERT INTO likes (from_user, to_user, game) VALUES ($1, $2, $3)",
                    from_user, to_user, game
                )

                mutual = await conn.fetchval(
                    "SELECT 1 FROM likes WHERE from_user = $1 AND to_user = $2 AND game = $3",
                    to_user, from_user, game
                )

                if mutual:
                    user1, user2 = sorted([from_user, to_user])
                    await conn.execute(
                        "INSERT INTO matches (user1, user2, game) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                        user1, user2, game
                    )

                    await self._clear_user_cache(from_user)
                    await self._clear_user_cache(to_user)
                    return True

                await self._clear_pattern_cache(f"likes:{to_user}:*")
                return False

    async def get_likes_for_user(self, user_id: int, game: str) -> List[Dict]:
        """Получение лайков для пользователя с кэшированием"""
        cache_key = f"likes:{user_id}:{game}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT p.*, u.username 
                   FROM profiles p
                   JOIN users u ON p.telegram_id = u.telegram_id
                   JOIN likes l ON p.telegram_id = l.from_user
                   WHERE l.to_user = $1 AND l.game = $2 AND p.game = $2
                   AND NOT EXISTS (
                       SELECT 1 FROM matches m
                       WHERE ((m.user1 = $1 AND m.user2 = p.telegram_id) OR
                              (m.user1 = p.telegram_id AND m.user2 = $1))
                       AND m.game = $2
                   )
                   AND NOT EXISTS (
                       SELECT 1 FROM skipped_likes sl
                       WHERE sl.user_id = $1 AND sl.skipped_user_id = p.telegram_id AND sl.game = $2
                   )
                   ORDER BY l.created_at DESC''',
                user_id, game
            )

            results = [self._format_profile(row) for row in rows]
            await self._set_cache(cache_key, results, self._cache_ttl['likes'])
            return results

    async def get_matches(self, user_id: int, game: str) -> List[Dict]:
        """Получение матчей пользователя с кэшированием"""
        cache_key = f"matches:{user_id}:{game}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT p.*, u.username 
                   FROM profiles p
                   JOIN users u ON p.telegram_id = u.telegram_id
                   JOIN matches m ON (p.telegram_id = m.user1 OR p.telegram_id = m.user2)
                   WHERE (m.user1 = $1 OR m.user2 = $1) 
                       AND p.telegram_id != $1
                       AND m.game = $2 AND p.game = $2
                   ORDER BY m.created_at DESC''',
                user_id, game
            )

            results = [self._format_profile(row) for row in rows]
            await self._set_cache(cache_key, results, self._cache_ttl['matches'])
            return results

    async def skip_like(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        """Пропуск лайка"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO skipped_likes (user_id, skipped_user_id, game) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                user_id, skipped_user_id, game
            )
            await self._clear_pattern_cache(f"likes:{user_id}:*")
            return True

    async def remove_like(self, from_user: int, to_user: int, game: str) -> bool:
        """Удаление лайка"""
        async with self._pg_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM likes WHERE from_user = $1 AND to_user = $2 AND game = $3",
                from_user, to_user, game
            )

            await self._clear_pattern_cache(f"likes:{to_user}:*")
            await self._clear_pattern_cache(f"matches:{from_user}:*")
            await self._clear_pattern_cache(f"matches:{to_user}:*")

            return result != "DELETE 0"

    # === БАНЫ ===

    async def is_user_banned(self, user_id: int) -> bool:
        """Проверка бана пользователя с кэшированием"""
        cache_key = f"ban:{user_id}"
        cached = await self._get_cache(cache_key)
        if cached is not None:
            return bool(cached)

        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT 1 FROM bans WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP",
                user_id
            )
            result = row is not None
            await self._set_cache(cache_key, result, 60)
            return result

    async def get_user_ban(self, user_id: int) -> Optional[Dict]:
        """Получение информации о бане"""
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM bans WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP",
                user_id
            )
            return dict(row) if row else None

    async def get_all_bans(self) -> List[Dict]:
        """Получение всех активных банов"""
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT b.*, u.username, p.name, p.nickname
                   FROM bans b
                   LEFT JOIN users u ON b.user_id = u.telegram_id
                   LEFT JOIN profiles p ON b.user_id = p.telegram_id
                   WHERE b.expires_at > CURRENT_TIMESTAMP
                   ORDER BY b.created_at DESC'''
            )
            return [dict(row) for row in rows]

    async def get_user_moderation_stats(self, user_id: int) -> Dict:
        """Получение статистики модерации пользователя"""
        async with self._pg_pool.acquire() as conn:
            stats = {}

            reports_count = await conn.fetchval(
                "SELECT COUNT(*) FROM reports WHERE reported_user_id = $1",
                user_id
            )
            stats['reports_total'] = reports_count or 0

            resolved_reports = await conn.fetchval(
                "SELECT COUNT(*) FROM reports WHERE reported_user_id = $1 AND status = 'resolved'",
                user_id
            )
            stats['reports_resolved'] = resolved_reports or 0

            bans_count = await conn.fetchval(
                "SELECT COUNT(*) FROM bans WHERE user_id = $1",
                user_id
            )
            stats['bans_total'] = bans_count or 0

            last_ban = await conn.fetchrow(
                "SELECT reason, created_at, expires_at FROM bans WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
                user_id
            )
            stats['last_ban'] = dict(last_ban) if last_ban else None

            return stats

    async def ban_user(self, user_id: int, reason: str, expires_at: datetime = None) -> bool:
        """Бан пользователя"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO bans (user_id, reason, expires_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id)
                DO UPDATE SET reason=EXCLUDED.reason, expires_at=EXCLUDED.expires_at, created_at=CURRENT_TIMESTAMP
            """, user_id, reason, expires_at)

            await self._clear_user_cache(user_id)
            await self._clear_pattern_cache(f"ban:{user_id}")
            return True

    async def unban_user(self, user_id: int) -> bool:
        """Снятие бана"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute("DELETE FROM bans WHERE user_id = $1", user_id)

            await self._clear_user_cache(user_id)
            await self._clear_pattern_cache(f"ban:{user_id}")
            return True

    # === ЖАЛОБЫ ===

    async def add_report(self, reporter_id: int, reported_user_id: int, game: str) -> bool:
        """Добавление жалобы"""
        async with self._pg_pool.acquire() as conn:
            try:
                await conn.execute(
                    '''INSERT INTO reports (reporter_id, reported_user_id, game, report_reason, status)
                       VALUES ($1, $2, $3, 'inappropriate_content', 'pending')''',
                    reporter_id, reported_user_id, game
                )
                return True
            except:
                return False

    async def get_pending_reports(self) -> List[Dict]:
        """Получение ожидающих жалоб с username"""
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT r.*, 
                       u1.username as reporter_username,
                       u2.username as reported_username
                FROM reports r
                LEFT JOIN users u1 ON r.reporter_id = u1.telegram_id
                LEFT JOIN users u2 ON r.reported_user_id = u2.telegram_id
                WHERE r.status = 'pending' 
                ORDER BY r.created_at ASC 
                LIMIT 100
            """)
            return [dict(r) for r in rows]

    async def get_report_info(self, report_id: int) -> Optional[Dict]:
        """Получение информации о жалобе с username"""
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT r.*, 
                       p.name, p.nickname, 
                       u1.username as reporter_username,
                       u2.username as reported_username
                FROM reports r
                LEFT JOIN profiles p ON r.reported_user_id = p.telegram_id AND r.game = p.game
                LEFT JOIN users u1 ON r.reporter_id = u1.telegram_id
                LEFT JOIN users u2 ON r.reported_user_id = u2.telegram_id
                WHERE r.id = $1
            """, report_id)
            return dict(row) if row else None

    async def update_report_status(self, report_id: int, status: str, admin_id: int) -> bool:
        """Обновление статуса жалобы"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                "UPDATE reports SET status=$1, reviewed_at=CURRENT_TIMESTAMP, admin_id=$2 WHERE id=$3",
                status, admin_id, report_id
            )
            return True

    # === СЛУЖЕБНЫЕ МЕТОДЫ ===

    async def get_users_for_monthly_reminder(self) -> List[Dict]:
        """Получение пользователей для ежемесячного напоминания об обновлении анкеты"""
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT p.telegram_id, p.game, u.username, p.updated_at
                FROM profiles p
                JOIN users u ON p.telegram_id = u.telegram_id
                WHERE p.updated_at < NOW() - INTERVAL '25 days'
                    AND p.created_at < NOW() - INTERVAL '7 days'
                    AND NOT EXISTS (
                        SELECT 1 FROM bans b
                        WHERE b.user_id = p.telegram_id
                        AND b.expires_at > NOW()
                    )
                ORDER BY p.updated_at ASC
                LIMIT 1000
            """)
            return [dict(row) for row in rows]

    async def get_database_stats(self) -> Dict[str, Union[int, str]]:
        """Получение детальной статистики базы данных"""
        stats = {}

        try:
            async with self._pg_pool.acquire() as conn:
                stats_queries = [
                    ("users_total", "SELECT COUNT(DISTINCT telegram_id) FROM users"),
                    ("users_with_profiles", "SELECT COUNT(DISTINCT telegram_id) FROM profiles"),
                    ("profiles_total", "SELECT COUNT(*) FROM profiles"),
                    ("matches_total", "SELECT COUNT(*) FROM matches"),
                    ("likes_total", "SELECT COUNT(*) FROM likes"),
                    ("reports_total", "SELECT COUNT(*) FROM reports"),
                    ("reports_pending", "SELECT COUNT(*) FROM reports WHERE status = 'pending'"),
                    ("active_bans", "SELECT COUNT(*) FROM bans WHERE expires_at > NOW()"),
                ]

                for name, query in stats_queries:
                    try:
                        count = await conn.fetchval(query)
                        stats[name] = count or 0
                    except Exception as e:
                        logger.warning(f"Ошибка получения статистики {name}: {e}")
                        stats[name] = "error"

                try:
                    rows = await conn.fetch("""
                        SELECT 
                            game,
                            COUNT(*) as profiles_count,
                            COUNT(DISTINCT telegram_id) as users_count
                        FROM profiles 
                        GROUP BY game
                    """)

                    stats["games_breakdown"] = {}
                    for row in rows:
                        game = row["game"]
                        stats["games_breakdown"][game] = {
                            "profiles": row["profiles_count"],
                            "users": row["users_count"]
                        }
                except Exception as e:
                    logger.warning(f"Ошибка получения статистики по играм: {e}")
                    stats["games_breakdown"] = {}

        except Exception as e:
            logger.error(f"Ошибка получения статистики базы данных: {e}")
            stats["error"] = str(e)

        return stats

    async def cleanup_old_data(self, days: int = 30):
        """Очистка старых данных"""
        cutoff_date = datetime.now() - timedelta(days=days)

        async with self._pg_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM search_skipped WHERE last_skipped < $1", cutoff_date
                )

                await conn.execute(
                    "DELETE FROM bans WHERE expires_at < CURRENT_TIMESTAMP"
                )

                await conn.execute(
                    "DELETE FROM reports WHERE status != 'pending' AND reviewed_at < $1", cutoff_date
                )

                logger.info(f"Очищены данные старше {days} дней")