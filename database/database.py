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
            'matches': 900,       # 15 минут для мэтчей
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

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS ad_posts (
                    id SERIAL PRIMARY KEY,
                    message_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    caption TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by BIGINT,
                    show_interval INTEGER DEFAULT 3,
                    games TEXT[] DEFAULT ARRAY['dota', 'cs']::TEXT[]
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

                # === ИНДЕКСЫ ДЛЯ МЭТЧЕЙ ===
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

            try:
                await conn.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                await conn.execute("UPDATE profiles SET updated_at = created_at WHERE updated_at IS NULL")
                logger.info("✅ Миграция: добавлена колонка updated_at в profiles")
            except Exception as e:
                logger.warning(f"Миграция поля updated_at: {e}")

            try:
                await conn.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'player'")
                await conn.execute("UPDATE profiles SET role = 'player' WHERE role IS NULL")
                logger.info("✅ Миграция: добавлена колонка role в profiles")
            except Exception as e:
                logger.warning(f"Миграция поля role: {e}")

            try:
                await conn.execute("ALTER TABLE likes ADD COLUMN IF NOT EXISTS message TEXT")
                logger.info("✅ Миграция: добавлена колонка message в likes")
            except Exception as e:
                logger.warning(f"Миграция поля message: {e}")

            try:
                await conn.execute("ALTER TABLE ad_posts ADD COLUMN IF NOT EXISTS games TEXT[] DEFAULT ARRAY['dota', 'cs']::TEXT[]")
                logger.info("✅ Миграция: добавлена колонка games в ad_posts")
            except Exception as e:
                logger.warning(f"Миграция поля games: {e}")

            try:
                await conn.execute("ALTER TABLE ad_posts ADD COLUMN IF NOT EXISTS regions TEXT[] DEFAULT ARRAY['all']::TEXT[]")
                logger.info("✅ Миграция: добавлена колонка regions в ad_posts")
            except Exception as e:
                logger.warning(f"Миграция поля games: {e}")

            try:
                await conn.execute("ALTER TABLE reports ADD COLUMN IF NOT EXISTS report_message TEXT")
                logger.info("✅ Миграция: добавлена колонка report_message в reports")
            except Exception as e:
                logger.warning(f"Миграция поля report_message: {e}")

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
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Ошибка парсинга позиций для профиля {profile.get('telegram_id')}: {e}")
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

        # ← ДОБАВИТЬ ТОЛЬКО ЭТУ СТРОКУ:
        if 'role' not in profile or profile['role'] is None:
            profile['role'] = 'player'

        return profile

    def _generate_filters_hash(self, rating_filter, position_filter, region_filter, goals_filter, role_filter) -> str:
        """Генерация хэша для фильтров поиска"""
        filters_str = f"{rating_filter or 'any'}_{position_filter or 'any'}_{region_filter or 'any'}_{goals_filter or 'any'}_{role_filter or 'player'}"
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

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Получение пользователя по username"""
        # Убираем @ если есть
        username = username.lstrip('@')

        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE LOWER(username) = LOWER($1)",
                username
            )
            return dict(row) if row else None

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
            row = await conn.fetchrow(
                '''SELECT p.*, u.username
                   FROM profiles p
                   LEFT JOIN users u ON p.telegram_id = u.telegram_id
                   WHERE p.telegram_id = $1 AND p.game = $2''',
                telegram_id, game
            )

            if row:
                profile = self._format_profile(row)
                await self._set_cache(cache_key, profile, self._cache_ttl['profile'])
                return profile

            return None

    async def has_profile(self, telegram_id: int, game: str) -> bool:
        """Проверка наличия профиля с кэшированием"""
        profile = await self.get_user_profile(telegram_id, game)
        return profile is not None

    async def update_user_profile(self, telegram_id: int, game: str, name: str, nickname: str,
                                 age: int, rating: str, region: str, positions: List[str],
                                 goals: List[str], additional_info: str = "", photo_id: str = None,
                                 profile_url: str = None, username: str = None,
                                 role: str = 'player'):
        """Создание или обновление профиля пользователя"""

        async with self._pg_pool.acquire() as conn:
            try:
                # Проверяем существует ли профиль
                existing = await conn.fetchrow(
                    'SELECT telegram_id FROM profiles WHERE telegram_id = $1 AND game = $2',
                    telegram_id, game
                )

                if existing:
                    # ОБНОВЛЕНИЕ существующего профиля (БЕЗ username)
                    await conn.execute(
                        '''UPDATE profiles 
                           SET name = $3, nickname = $4, age = $5, rating = $6, region = $7,
                               positions = $8, goals = $9, additional_info = $10, photo_id = $11,
                               profile_url = $12, role = $13, updated_at = NOW()
                           WHERE telegram_id = $1 AND game = $2''',
                        telegram_id, game, name, nickname, age, rating, region,
                        json.dumps(positions), json.dumps(goals), additional_info,
                        photo_id, profile_url, role
                    )
                else:
                    # СОЗДАНИЕ нового профиля (БЕЗ username)
                    await conn.execute(
                        '''INSERT INTO profiles 
                           (telegram_id, game, name, nickname, age, rating, region, positions, goals,
                            additional_info, photo_id, profile_url, role, created_at, updated_at)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())''',
                        telegram_id, game, name, nickname, age, rating, region,
                        json.dumps(positions), json.dumps(goals), additional_info,
                        photo_id, profile_url, role
                    )

                # Если передан username, обновляем его в таблице users
                if username is not None:
                    await conn.execute(
                        '''INSERT INTO users (telegram_id, username, current_game)
                           VALUES ($1, $2, $3)
                           ON CONFLICT (telegram_id)
                           DO UPDATE SET username = $2''',
                        telegram_id, username, game
                    )

                # Инвалидация кэша
                await self._clear_user_cache(telegram_id)
                await self._clear_pattern_cache(f"search:*:{game}:*")
                await self._clear_pattern_cache(f"profile:*:{game}")

                logger.info(f"Профиль обновлён: {telegram_id} в {game}, роль: {role}")
                return True

            except Exception as e:
                logger.error(f"Ошибка обновления профиля: {e}")
                return False

    async def update_user_activity(self, user_id: int) -> bool:
        """Обновление времени последней активности пользователя"""
        try:
            async with self._pg_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE users 
                    SET last_activity = CURRENT_TIMESTAMP 
                    WHERE telegram_id = $1
                """, user_id)
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления активности пользователя {user_id}: {e}")
            return False

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
                                   role_filter: str = None,
                                   limit: int = 20,
                                   offset: int = 0) -> List[Dict]:
        """Умный поиск с приоритетом активным пользователям, близким рейтингом и комплементарностью"""

        # Получаем file_id дефолтных аватарок для определения кастомных фото
        from config import settings
        default_dota_avatar = settings.get_cached_photo_id('avatar_dota')
        default_cs_avatar = settings.get_cached_photo_id('avatar_cs')

        # Получаем данные текущего пользователя для расчета совместимости
        user_profile = await self.get_user_profile(user_id, game)
        user_rating = user_profile.get('rating') if user_profile else None
        user_goals = user_profile.get('goals', []) if user_profile else []
        user_positions = user_profile.get('positions', []) if user_profile else []

        # Создаем маппинг рейтингов для расчета близости
        rating_order = {}
        if game == 'dota':
            ratings_list = ['herald', 'guardian', 'crusader', 'archon', 'legend', 'ancient', 'divine', 'immortal1', 'immortal2', 'immortal3', 'immortal4', 'immortal5']
        else:  # cs
            ratings_list = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '10_plus', '10_advanced', '10_elite', 'pro']

        for idx, rating in enumerate(ratings_list):
            rating_order[rating] = idx

        user_rating_idx = rating_order.get(user_rating, -1) if user_rating else -1

        # Генерация ключа кэша
        filters_hash = self._generate_filters_hash(
            rating_filter, position_filter, country_filter, goals_filter, role_filter
        )
        cache_key = f"search:{user_id}:{game}:{filters_hash}:{offset//limit}"

        # Кэшируем только первые 3 страницы
        if offset < 60:
            cached = await self._get_cache(cache_key)
            if cached:
                return cached

        # Умный SQL-запрос с приоритетами
        query = '''
            WITH excluded_users AS (
                SELECT DISTINCT to_user as excluded_id FROM likes WHERE from_user = $1 AND game = $2
                UNION
                SELECT DISTINCT reported_user_id as excluded_id FROM reports WHERE reporter_id = $1 AND game = $2
                UNION
                SELECT DISTINCT user_id as excluded_id FROM bans WHERE expires_at > CURRENT_TIMESTAMP
            ),
            skipped_users AS (
                SELECT skipped_user_id as skipped_id, skip_count, last_skipped
                FROM search_skipped WHERE user_id = $1 AND game = $2
            ),
            rating_indices AS (
                SELECT unnest($10::text[]) as rating, generate_series(0, array_length($10::text[], 1) - 1) as rating_idx
            ),
            potential_profiles AS (
                SELECT
                    p.telegram_id, p.game, p.name, p.nickname, p.age,
                    p.rating, p.region, p.positions, p.goals,
                    p.additional_info, p.photo_id, p.profile_url,
                    p.created_at, p.updated_at, p.role,
                    u.username, u.last_activity,
                    COALESCE(s.skip_count, 0) as skip_count,
                    s.last_skipped,

                    -- Приоритет отображения (новые vs пропущенные)
                    CASE
                        WHEN s.skipped_id IS NULL THEN 0
                        WHEN s.skip_count = 1 AND s.last_skipped < NOW() - INTERVAL '1 day' THEN 0.5
                        WHEN s.last_skipped < NOW() - INTERVAL '7 days' THEN 1
                        ELSE 2
                    END as display_priority,

                    -- Приоритет фото: 0 = кастомное, 1 = дефолтное
                    CASE
                        WHEN p.photo_id IS NULL THEN 1
                        WHEN (p.game = 'dota' AND p.photo_id = $11) OR (p.game = 'cs' AND p.photo_id = $12) THEN 1
                        ELSE 0
                    END as photo_priority,

                    -- Приоритет активности
                    CASE
                        WHEN u.last_activity > NOW() - INTERVAL '3 days' THEN 0
                        WHEN u.last_activity > NOW() - INTERVAL '7 days' THEN 1
                        WHEN u.last_activity > NOW() - INTERVAL '30 days' THEN 2
                        ELSE 3
                    END as activity_priority,

                    -- Близость рейтинга
                    COALESCE(ABS(ri.rating_idx - $13), 999) as rating_distance,

                    -- Совпадение целей
                    (SELECT COUNT(*) FROM jsonb_array_elements_text(p.goals) AS goal WHERE goal = ANY($14)) as goals_overlap,

                    -- ОБРАТНОЕ совпадение позиций (меньше = лучше)
                    (SELECT COUNT(*) FROM jsonb_array_elements_text(p.positions) AS pos WHERE pos = ANY($15)) as position_overlap,

                    -- Заполненность анкеты
                    (
                        CASE WHEN p.rating IS NOT NULL AND p.rating != '' AND p.rating != 'any' THEN 1 ELSE 0 END +
                        CASE WHEN p.positions IS NOT NULL AND jsonb_array_length(p.positions) > 0 AND p.positions != '["any"]'::jsonb THEN 1 ELSE 0 END +
                        CASE WHEN p.region IS NOT NULL AND p.region != '' AND p.region != 'any' THEN 1 ELSE 0 END +
                        CASE WHEN p.goals IS NOT NULL AND jsonb_array_length(p.goals) > 0 AND p.goals != '["any"]'::jsonb THEN 1 ELSE 0 END +
                        CASE WHEN p.additional_info IS NOT NULL AND LENGTH(p.additional_info) > 20 THEN 2 ELSE 0 END +
                        CASE WHEN p.profile_url IS NOT NULL AND p.profile_url != '' THEN 1 ELSE 0 END
                    ) as filled_score

                FROM profiles p
                JOIN users u ON p.telegram_id = u.telegram_id
                LEFT JOIN skipped_users s ON p.telegram_id = s.skipped_id
                LEFT JOIN rating_indices ri ON p.rating = ri.rating
                WHERE p.telegram_id != $1
                    AND p.game = $2
                    AND p.telegram_id NOT IN (SELECT excluded_id FROM excluded_users)
                    AND COALESCE(p.role, 'player') = $7
            ),
            filtered_profiles AS (
                SELECT * FROM potential_profiles
                WHERE
                    ($3 IS NULL OR rating = $3)
                    AND ($4 IS NULL OR positions ? $4 OR positions ? 'any')
                    AND ($5 IS NULL OR region = $5 OR region = 'any')
                    AND ($6 IS NULL OR goals ? $6)
            )
            SELECT
                telegram_id, game, name, nickname, age, rating, region,
                positions, goals, additional_info, photo_id, profile_url,
                username, created_at, updated_at, role, display_priority
            FROM (
                SELECT *,
                    -- Разбиваем на группы качества для чередования
                    CASE
                        WHEN filled_score >= 6 THEN 1  -- Premium
                        WHEN filled_score >= 4 THEN 2  -- Good
                        ELSE 3                          -- Basic
                    END as quality_tier,
                    ROW_NUMBER() OVER (
                        PARTITION BY CASE
                            WHEN filled_score >= 6 THEN 1
                            WHEN filled_score >= 4 THEN 2
                            ELSE 3
                        END
                        ORDER BY
                            display_priority ASC,
                            photo_priority ASC,
                            activity_priority ASC,
                            rating_distance ASC,
                            goals_overlap DESC,
                            position_overlap ASC,
                            skip_count ASC,
                            last_skipped ASC NULLS FIRST,
                            created_at DESC
                    ) as tier_position
                FROM filtered_profiles
            ) as ranked
            ORDER BY
                -- Чередуем: Premium → Good → Premium → Basic
                CASE
                    WHEN quality_tier = 1 THEN tier_position * 3
                    WHEN quality_tier = 2 THEN tier_position * 3 + 1
                    ELSE tier_position * 3 + 2
                END
            LIMIT $8 OFFSET $9
        '''

        params = [
            user_id, game,
            rating_filter if rating_filter and rating_filter != 'any' else None,
            position_filter if position_filter and position_filter != 'any' else None,
            country_filter if country_filter and country_filter != 'any' else None,
            goals_filter if goals_filter and goals_filter != 'any' else None,
            role_filter if role_filter and role_filter != 'player' else 'player',
            limit, offset,
            ratings_list,              # $10
            default_dota_avatar,       # $11
            default_cs_avatar,         # $12
            user_rating_idx,           # $13
            user_goals,                # $14
            user_positions             # $15
        ]

        async with self._pg_pool.acquire() as conn:
            try:
                rows = await conn.fetch(query, *params)
                results = [self._format_profile(row) for row in rows]

                # Детерминированное перемешивание новых анкет на первой странице
                # Seed меняется каждый день, чтобы анкеты не застревали в одном порядке
                if offset == 0 and len(results) > 1:
                    new_profiles = [p for p in results if p.get('display_priority', 0) == 0]
                    skipped_profiles = [p for p in results if p.get('display_priority', 0) > 0]

                    if new_profiles:
                        import hashlib, random
                        from datetime import datetime
                        # Добавляем день в seed, чтобы порядок менялся ежедневно
                        today = datetime.now().strftime("%Y-%m-%d")
                        seed_str = f"{user_id}{game}{filters_hash}{today}"
                        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
                        random.seed(seed)
                        random.shuffle(new_profiles)

                    results = new_profiles + skipped_profiles

                # Кэшируем только первые страницы
                if offset < 60:
                    await self._set_cache(cache_key, results, self._cache_ttl['search'])

                return results

            except Exception as e:
                logger.error(f"Ошибка поиска анкет: {e}")
                return await self._fallback_search(user_id, game, limit, offset)

    async def _fallback_search(self, user_id: int, game: str, limit: int, offset: int) -> List[Dict]:
        """Резервный поиск при ошибках в основном запросе"""
        query = '''
            SELECT p.*, u.username
            FROM profiles p
            JOIN users u ON p.telegram_id = u.telegram_id
            WHERE p.telegram_id != $1 
                AND p.game = $2
                AND NOT EXISTS (
                    SELECT 1 FROM likes 
                    WHERE from_user = $1 AND to_user = p.telegram_id AND game = $2
                )
                AND NOT EXISTS (
                    SELECT 1 FROM reports 
                    WHERE reporter_id = $1 AND reported_user_id = p.telegram_id AND game = $2
                )
                AND NOT EXISTS (
                    SELECT 1 FROM bans 
                    WHERE user_id = p.telegram_id AND expires_at > CURRENT_TIMESTAMP
                )
            ORDER BY 
                CASE WHEN p.photo_id IS NOT NULL THEN 0 ELSE 1 END,  -- Сначала с фото
                p.created_at DESC
            LIMIT $3 OFFSET $4
        '''

        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, user_id, game, limit, offset)
            return [self._format_profile(row) for row in rows]

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
            await self._clear_pattern_cache(f"search:{user_id}:{game}:*")
            return True

    # === ЛАЙКИ И МЭТЧИ ===

    async def add_like(self, from_user: int, to_user: int, game: str, message: str = None) -> bool:
        """Добавление лайка с опциональным сообщением (возвращает True если мэтч)"""
        async with self._pg_pool.acquire() as conn:
            async with conn.transaction():
                existing = await conn.fetchval(
                    "SELECT 1 FROM likes WHERE from_user = $1 AND to_user = $2 AND game = $3",
                    from_user, to_user, game
                )
                if existing:
                    return False

                await conn.execute(
                    "INSERT INTO likes (from_user, to_user, game, message) VALUES ($1, $2, $3, $4)",
                    from_user, to_user, game, message
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
        """Получение лайков для пользователя с сообщениями"""
        cache_key = f"likes:{user_id}:{game}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT p.telegram_id, p.game, p.name, p.nickname, p.age, 
                        p.rating, p.region, p.positions, p.goals,
                        p.additional_info, p.photo_id, p.profile_url,
                        p.created_at, p.updated_at,
                        u.username,
                        l.message, l.created_at as like_created_at
                FROM profiles p
                JOIN users u ON p.telegram_id = u.telegram_id
                JOIN likes l ON p.telegram_id = l.from_user AND l.game = p.game
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
        """Получение мэтчей пользователя с кэшированием"""
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

    async def add_report(self, reporter_id: int, reported_user_id: int, game: str, report_message: str) -> bool:
        """Добавление жалобы с обязательным сообщением от пользователя

        Args:
            reporter_id: ID пользователя, который подал жалобу
            reported_user_id: ID пользователя, на которого жалуются
            game: Игра (dota/cs)
            report_message: Причина жалобы от пользователя (минимум 5 символов)

        Returns:
            bool: True если жалоба добавлена, False если пользователь уже жаловался
        """
        if not report_message or len(report_message.strip()) < 5:
            raise ValueError("report_message должно быть минимум 5 символов")

        async with self._pg_pool.acquire() as conn:
            try:
                await conn.execute(
                    '''INSERT INTO reports (reporter_id, reported_user_id, game, report_reason, status, report_message)
                       VALUES ($1, $2, $3, 'inappropriate_content', 'pending', $4)''',
                    reporter_id, reported_user_id, game, report_message.strip()
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

    # === РЕКЛАМНЫЕ ПОСТЫ ===

    async def add_ad_post(self, message_id: int, chat_id: int, caption: str, admin_id: int,
                          show_interval: int = 3, games: List[str] = None, regions: List[str] = None,
                          ad_type: str = 'forward', expires_at = None) -> int:
        """Добавление рекламного поста

        Args:
            message_id: ID сообщения в Telegram
            chat_id: ID чата откуда сообщение
            caption: Название рекламы для админки
            admin_id: ID админа создавшего рекламу
            show_interval: Через сколько анкет показывать
            games: Список игр ['dota', 'cs']
            regions: Список регионов ['all'] или конкретные регионы
            ad_type: Тип рекламы 'copy' (копировать) или 'forward' (пересылать)
            expires_at: Дата/время окончания показа (None = бессрочно)
        """
        if games is None:
            games = ['dota', 'cs']
        if regions is None:
            regions = ['all']

        async with self._pg_pool.acquire() as conn:
            post_id = await conn.fetchval(
                """INSERT INTO ad_posts (message_id, chat_id, caption, created_by, show_interval, games, regions, ad_type, expires_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   RETURNING id""",
                message_id, chat_id, caption, admin_id, show_interval, games, regions, ad_type, expires_at
            )
            await self._redis.delete("active_ads:dota")
            await self._redis.delete("active_ads:cs")

            expires_info = f", истекает: {expires_at}" if expires_at else ", бессрочно"
            logger.info(f"Добавлен рекламный пост #{post_id} ({ad_type}) для игр: {games}, регионов: {regions}{expires_info}")
            return post_id

    async def get_active_ads_for_game(self, game: str) -> List[Dict]:
        """Получение активных рекламных постов для конкретной игры (не истекших)"""
        cache_key = f"active_ads:{game}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM ad_posts
                   WHERE is_active = TRUE
                   AND $1 = ANY(games)
                   AND (expires_at IS NULL OR expires_at > NOW())
                   ORDER BY created_at DESC""",
                game
            )
            result = [dict(row) for row in rows]
            await self._set_cache(cache_key, result, 600)
            return result

    async def update_ad_games(self, ad_id: int, games: List[str]) -> bool:
        """Обновление списка игр для рекламы"""
        try:
            async with self._pg_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE ad_posts SET games = $1 WHERE id = $2",
                    games, ad_id
                )
                await self._redis.delete("active_ads:dota")
                await self._redis.delete("active_ads:cs")
                logger.info(f"Обновлены игры для рекламы #{ad_id}: {games}")
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления игр рекламы #{ad_id}: {e}")
            return False

    async def update_ad_regions(self, ad_id: int, regions: List[str]) -> bool:
        """Обновление списка регионов для рекламы"""
        try:
            async with self._pg_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE ad_posts SET regions = $1 WHERE id = $2",
                    regions, ad_id
                )
                await self._redis.delete("active_ads:dota")
                await self._redis.delete("active_ads:cs")
                logger.info(f"Обновлены регионы для рекламы #{ad_id}: {regions}")
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления регионов рекламы #{ad_id}: {e}")
            return False

    async def get_all_ads(self) -> List[Dict]:
        """Получение всех рекламных постов для админ панели"""
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM ad_posts ORDER BY created_at DESC"
            )
            return [dict(row) for row in rows]

    async def toggle_ad_status(self, ad_id: int) -> bool:
        """Переключение статуса рекламы (вкл/выкл)"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                "UPDATE ad_posts SET is_active = NOT is_active WHERE id = $1",
                ad_id
            )
            await self._redis.delete("active_ads")
            return True

    async def update_ad_interval(self, ad_id: int, interval: int) -> bool:
        """Обновление интервала показа рекламы"""
        try:
            async with self._pg_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE ad_posts SET show_interval = $1 WHERE id = $2",
                    interval, ad_id
                )
                # Очищаем кэш для обеих игр
                await self._redis.delete("active_ads:dota")
                await self._redis.delete("active_ads:cs")
                logger.info(f"Обновлён интервал рекламы #{ad_id}: {interval}, кэш очищен")
                return True
        except Exception as e:
            logger.error(f"Ошибка обновления интервала рекламы #{ad_id}: {e}")
            return False

    async def delete_ad_post(self, ad_id: int) -> bool:
        """Удаление рекламного поста"""
        async with self._pg_pool.acquire() as conn:
            await conn.execute("DELETE FROM ad_posts WHERE id = $1", ad_id)
            await self._redis.delete("active_ads")
            return True

    async def cleanup_expired_ads(self) -> int:
        """Удаление истекших рекламных постов

        Returns:
            Количество удаленных постов
        """
        async with self._pg_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM ad_posts WHERE expires_at IS NOT NULL AND expires_at <= NOW()"
            )
            # Парсим результат вида "DELETE N"
            deleted_count = int(result.split()[-1]) if result and result.split() else 0

            if deleted_count > 0:
                await self._redis.delete("active_ads:dota")
                await self._redis.delete("active_ads:cs")
                logger.info(f"🗑️ Удалено {deleted_count} истекших рекламных постов")

            return deleted_count

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