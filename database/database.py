import asyncpg
import redis.asyncio as redis
import json
import os
import hashlib
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Database:
    """Объединенный класс для работы с PostgreSQL + Redis"""
    async def init(self):
        """Инициализация подключений"""
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
        """Инициализация PostgreSQL"""
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'teammates')
        db_user = os.getenv('DB_USER', 'teammates_user')
        db_password = os.getenv('DB_PASSWORD', '')

        if not db_password:
            raise ValueError("DB_PASSWORD не установлен в переменных окружения")

        connection_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

        self._pg_pool = await asyncpg.create_pool(connection_url, min_size=5, max_size=20)
        await self._create_tables()
        logger.info("✅ PostgreSQL подключена")

    async def _init_redis(self):
        """Инициализация Redis"""
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = os.getenv('REDIS_PORT', '6379')
        redis_db = os.getenv('REDIS_DB', '0')

        redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

        self._redis = redis.from_url(redis_url, decode_responses=True)
        await self._redis.ping()
        logger.info("✅ Redis подключен")

    async def _create_tables(self):
        """Создание таблиц"""
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
                    additional_info TEXT,
                    photo_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(telegram_id, game)
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

            indexes = [
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_game ON profiles(game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_telegram_id_game ON profiles(telegram_id, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_to_game ON likes(to_user, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_from_game ON likes(from_user, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_created_at ON likes(created_at DESC)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_matches_users ON matches(user1, user2, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_matches_user1_game ON matches(user1, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_matches_user2_game ON matches(user2, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_matches_created_at ON matches(created_at DESC)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reports_status ON reports(status)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reports_reported_user_game ON reports(reported_user_id, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bans_user_expires ON bans(user_id, expires_at)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_skipped_user_game ON search_skipped(user_id, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_skipped_likes_user_game ON skipped_likes(user_id, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_rating ON profiles(rating)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_region ON profiles(region)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_positions_gin ON profiles USING gin (positions jsonb_path_ops)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_from_to_game ON likes(from_user, to_user, game)",
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reports_reporter_reported_game ON reports(reporter_id, reported_user_id, game)"
                    ]

            for index_sql in indexes:
                try:
                    await conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"Не удалось создать индекс: {index_sql}, ошибка: {e}")

    def _format_profile(self, row) -> Dict:
        """Форматирование профиля"""
        if not row:
            return None

        profile = dict(row)
        positions = profile.get('positions', [])
        if isinstance(positions, str):
            try:
                positions = json.loads(positions)
            except:
                positions = []
        profile['positions'] = positions
        profile['current_game'] = profile.get('game')
        return profile

    def _generate_filters_hash(self, rating_filter, position_filter, region_filter) -> str:
        """Генерация хэша для фильтров поиска"""
        filters_str = f"{rating_filter or 'any'}_{position_filter or 'any'}_{region_filter or 'any'}"
        return hashlib.md5(filters_str.encode()).hexdigest()[:8]

    # === КЭШИРОВАНИЕ ===

    async def _get_cache(self, key: str):
        """Получение из кэша"""
        try:
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Ошибка чтения из кэша {key}: {e}")
        return None

    async def _set_cache(self, key: str, data, ttl: int = 600):
        """Сохранение в кэш"""
        try:
            await self._redis.setex(key, ttl, json.dumps(data, default=str))
        except Exception as e:
            logger.error(f"Ошибка записи в кэш {key}: {e}")

    async def _clear_user_cache(self, user_id: int):
        """Очистка кэша пользователя"""
        try:
            patterns = [f"profile:{user_id}:*", f"search:{user_id}:*"]
            for pattern in patterns:
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")

    # === ПОЛЬЗОВАТЕЛИ ===

    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
            return dict(row) if row else None

    async def create_user(self, telegram_id: int, username: str, game: str) -> bool:
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (telegram_id, username, current_game) VALUES ($1, $2, $3) ON CONFLICT (telegram_id) DO UPDATE SET username = $2, current_game = $3",
                telegram_id, username, game
            )
            await self._clear_user_cache(telegram_id)
            return True

    async def switch_game(self, telegram_id: int, game: str) -> bool:
        async with self._pg_pool.acquire() as conn:
            await conn.execute("UPDATE users SET current_game = $1 WHERE telegram_id = $2", game, telegram_id)
            await self._clear_user_cache(telegram_id)
            return True

    # === ПРОФИЛИ ===

    async def get_user_profile(self, telegram_id: int, game: str) -> Optional[Dict]:
        cache_key = f"profile:{telegram_id}:{game}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM profiles WHERE telegram_id = $1 AND game = $2", telegram_id, game)
            if not row:
                return None

            profile = self._format_profile(row)

            user = await self.get_user(telegram_id)
            if user:
                profile['username'] = user.get('username')

            await self._set_cache(cache_key, profile)
            return profile

    async def has_profile(self, telegram_id: int, game: str) -> bool:
        profile = await self.get_user_profile(telegram_id, game)
        return profile is not None

    async def update_user_profile(self, telegram_id: int, game: str, name: str, nickname: str,
                          age: int, rating: str, region: str, positions: List[str],
                          additional_info: str, photo_id: str = None) -> bool:
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO profiles (telegram_id, game, name, nickname, age, rating, region, positions, additional_info, photo_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                   ON CONFLICT (telegram_id, game) DO UPDATE SET 
                       name = $3, nickname = $4, age = $5, rating = $6, 
                       region = $7, positions = $8, additional_info = $9, photo_id = $10''',
                telegram_id, game, name, nickname, age, rating, region, 
                json.dumps(positions), additional_info, photo_id
            )
            await self._clear_user_cache(telegram_id)
            return True

    async def delete_profile(self, telegram_id: int, game: str) -> bool:
        async with self._pg_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM likes WHERE (from_user = $1 OR to_user = $1) AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM matches WHERE (user1 = $1 OR user2 = $1) AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM skipped_likes WHERE (user_id = $1 OR skipped_user_id = $1) AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM search_skipped WHERE (user_id = $1 OR skipped_user_id = $1) AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM reports WHERE reported_user_id = $1 AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM profiles WHERE telegram_id = $1 AND game = $2", telegram_id, game)
                await self._clear_user_cache(telegram_id)
                return True

    # === ПОИСК ===

    async def get_potential_matches(self, user_id: int, game: str,
                            rating_filter: str = None,
                            position_filter: str = None,
                            region_filter: str = None,
                            limit: int = 10) -> List[Dict]:

        filters_hash = self._generate_filters_hash(rating_filter, position_filter, region_filter)
        cache_key = f"search:{user_id}:{game}:{filters_hash}"
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        query = '''
            SELECT p.*, u.username
            FROM profiles p
            JOIN users u ON p.telegram_id = u.telegram_id
            WHERE p.telegram_id != $1 AND p.game = $2
            AND NOT EXISTS (SELECT 1 FROM likes l WHERE l.from_user = $1 AND l.to_user = p.telegram_id AND l.game = $2)
            AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.reporter_id = $1 AND r.reported_user_id = p.telegram_id AND r.game = $2)
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

        if region_filter and region_filter != 'any':
            param_count += 1
            query += f" AND (p.region = ${param_count} OR p.region = 'any')"
            params.append(region_filter)

        param_count += 1
        query += f" ORDER BY RANDOM() LIMIT ${param_count}"
        params.append(limit)

        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            results = [self._format_profile(row) for row in rows]

            await self._set_cache(cache_key, results, 300)
            return results

    async def add_search_skip(self, user_id: int, skipped_user_id: int, game: str) -> bool:
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
        """Возвращает True если это матч"""
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

                return False

    async def get_likes_for_user(self, user_id: int, game: str) -> List[Dict]:
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT p.*, u.username FROM profiles p
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
            return [self._format_profile(row) for row in rows]

    async def get_matches(self, user_id: int, game: str) -> List[Dict]:
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT p.*, u.username FROM profiles p
                   JOIN users u ON p.telegram_id = u.telegram_id
                   JOIN matches m ON (p.telegram_id = m.user1 OR p.telegram_id = m.user2)
                   WHERE (m.user1 = $1 OR m.user2 = $1) AND p.telegram_id != $1
                   AND m.game = $2 AND p.game = $2
                   ORDER BY m.created_at DESC''',
                user_id, game
            )
            return [self._format_profile(row) for row in rows]

    async def skip_like(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO skipped_likes (user_id, skipped_user_id, game) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                user_id, skipped_user_id, game
            )
            return True

    # === БАНЫ ===

    async def is_user_banned(self, user_id: int) -> bool:
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT 1 FROM bans WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP",
                user_id
            )
            return row is not None

    async def get_user_ban(self, user_id: int) -> Optional[Dict]:
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM bans WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP",
                user_id
            )
            return dict(row) if row else None

    async def get_all_bans(self) -> List[Dict]:
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

    # async def add_ban(self, user_id: int, reason: str, duration_days: int = 7) -> bool:
    #     expires_at = datetime.now() + timedelta(days=duration_days)
    #     async with self._pg_pool.acquire() as conn:
    #         await conn.execute(
    #             "INSERT INTO bans (user_id, reason, expires_at) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET reason = $2, expires_at = $3",
    #             user_id, reason, expires_at
    #         )
    #         await self._clear_user_cache(user_id)
    #         return True
    async def ban_user(self, user_id: int, reason: str, expires_at: datetime | None):
        async with self._pg_pool.acquire() as conn:
            # upsert: если бан уже есть — обновим
            await conn.execute("""
                INSERT INTO bans (user_id, reason, expires_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id)
                DO UPDATE SET reason=EXCLUDED.reason, expires_at=EXCLUDED.expires_at, created_at=CURRENT_TIMESTAMP
            """, user_id, reason, expires_at)
        # подчистим кэш
        await self._clear_user_cache(user_id)
        return True

    async def unban_user(self, user_id: int):
        async with self._pg_pool.acquire() as conn:
            await conn.execute("DELETE FROM bans WHERE user_id = $1", user_id)
        await self._clear_user_cache(user_id)
        return True

    # === ЖАЛОБЫ ===

    async def add_report(self, reporter_id: int, reported_user_id: int, game: str) -> bool:
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

    async def get_pending_reports(self):
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM reports WHERE status = 'pending' ORDER BY created_at ASC LIMIT 100"
            )
        return [dict(r) for r in rows]

    async def get_report_info(self, report_id: int) -> Optional[Dict]:
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                '''SELECT r.*, p.name, p.nickname, u.username
                   FROM reports r
                   LEFT JOIN profiles p ON r.reported_user_id = p.telegram_id AND r.game = p.game
                   LEFT JOIN users u ON p.telegram_id = u.telegram_id
                   WHERE r.id = $1''',
                report_id
            )
            return dict(row) if row else None

    async def process_report(self, report_id: int, action: str, admin_id: int) -> bool:
        async with self._pg_pool.acquire() as conn:
            async with conn.transaction():
                report = await conn.fetchrow("SELECT reported_user_id, game FROM reports WHERE id = $1", report_id)
                if not report:
                    return False

                reported_user_id, game = report

                if action in ['approve', 'ban']:
                    await self.delete_profile(reported_user_id, game)
                    if action == 'ban':
                        await self.add_ban(reported_user_id, 'нарушение правил')
                    status = action + ('ned' if action == 'ban' else 'd')
                elif action == 'dismiss':
                    status = 'dismissed'
                else:
                    return False

                await conn.execute(
                    '''UPDATE reports SET status = $1, reviewed_at = CURRENT_TIMESTAMP, admin_id = $2 WHERE id = $3''',
                    status, admin_id, report_id
                )

                return True

    async def update_report_status(self, report_id: int, status: str, admin_id: int):
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                "UPDATE reports SET status=$1, reviewed_at=CURRENT_TIMESTAMP, admin_id=$2 WHERE id=$3",
                status, admin_id, report_id
            )
        return True