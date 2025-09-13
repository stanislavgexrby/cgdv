import asyncpg
import json
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PostgreSQLDatabase:
    def __init__(self):
        self._pool = None
        
    async def init(self):
        """Инициализация подключения"""
        connection_url = (f"postgresql://"
                         f"{os.getenv('DB_USER')}:"
                         f"{os.getenv('DB_PASSWORD')}@"
                         f"{os.getenv('DB_HOST')}:"
                         f"{os.getenv('DB_PORT')}/"
                         f"{os.getenv('DB_NAME')}")
        
        self._pool = await asyncpg.create_pool(connection_url, min_size=5, max_size=20)
        await self._create_tables()
        logger.info("✅ PostgreSQL подключена")

    async def close(self):
        """Закрытие соединений"""
        if self._pool:
            await self._pool.close()

    async def _create_tables(self):
        """Создание таблиц"""
        async with self._pool.acquire() as conn:
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

            # Создаем основные индексы
            indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_game ON profiles(game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_likes_to_game ON likes(to_user, game)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_matches_users ON matches(user1, user2, game)"
            ]
            
            for index_sql in indexes:
                try:
                    await conn.execute(index_sql)
                except:
                    pass  # Индекс уже существует

    def _format_profile(self, row) -> Dict:
        """Форматирование профиля"""
        if not row:
            return None
        
        profile = dict(row)
        # Парсим позиции из JSONB
        positions = profile.get('positions', [])
        if isinstance(positions, str):
            try:
                positions = json.loads(positions)
            except:
                positions = []
        profile['positions'] = positions
        profile['current_game'] = profile.get('game')
        return profile

    # === ПОЛЬЗОВАТЕЛИ ===
    
    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
            return dict(row) if row else None

    async def create_user(self, telegram_id: int, username: str, game: str) -> bool:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (telegram_id, username, current_game) VALUES ($1, $2, $3) ON CONFLICT (telegram_id) DO UPDATE SET username = $2, current_game = $3",
                telegram_id, username, game
            )
            return True

    async def switch_game(self, telegram_id: int, game: str) -> bool:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE users SET current_game = $1 WHERE telegram_id = $2", game, telegram_id)
            return True

    # === ПРОФИЛИ ===
    
    async def get_user_profile(self, telegram_id: int, game: str) -> Optional[Dict]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM profiles WHERE telegram_id = $1 AND game = $2", telegram_id, game)
            if not row:
                return None
                
            profile = self._format_profile(row)
            
            # Добавляем username
            user = await self.get_user(telegram_id)
            if user:
                profile['username'] = user.get('username')
                
            return profile

    async def has_profile(self, telegram_id: int, game: str) -> bool:
        profile = await self.get_user_profile(telegram_id, game)
        return profile is not None

    async def update_user_profile(self, telegram_id: int, game: str, name: str, nickname: str,
                          age: int, rating: str, region: str, positions: List[str],
                          additional_info: str, photo_id: str = None) -> bool:
        async with self._pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO profiles (telegram_id, game, name, nickname, age, rating, region, positions, additional_info, photo_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                   ON CONFLICT (telegram_id, game) DO UPDATE SET 
                       name = $3, nickname = $4, age = $5, rating = $6, 
                       region = $7, positions = $8, additional_info = $9, photo_id = $10''',
                telegram_id, game, name, nickname, age, rating, region, 
                json.dumps(positions), additional_info, photo_id
            )
            return True

    async def delete_profile(self, telegram_id: int, game: str) -> bool:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Удаляем все связанные данные
                await conn.execute("DELETE FROM likes WHERE (from_user = $1 OR to_user = $1) AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM matches WHERE (user1 = $1 OR user2 = $1) AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM skipped_likes WHERE (user_id = $1 OR skipped_user_id = $1) AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM search_skipped WHERE (user_id = $1 OR skipped_user_id = $1) AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM reports WHERE reported_user_id = $1 AND game = $2", telegram_id, game)
                await conn.execute("DELETE FROM profiles WHERE telegram_id = $1 AND game = $2", telegram_id, game)
                return True

    # === ПОИСК ===
    
    async def get_potential_matches(self, user_id: int, game: str,
                            rating_filter: str = None,
                            position_filter: str = None,
                            region_filter: str = None,
                            limit: int = 10) -> List[Dict]:
        
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
            query += f" AND p.region = ${param_count}"
            params.append(region_filter)

        param_count += 1
        query += f" ORDER BY RANDOM() LIMIT ${param_count}"
        params.append(limit)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._format_profile(row) for row in rows]

    async def add_search_skip(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        async with self._pool.acquire() as conn:
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
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Проверяем существующий лайк
                existing = await conn.fetchval(
                    "SELECT 1 FROM likes WHERE from_user = $1 AND to_user = $2 AND game = $3",
                    from_user, to_user, game
                )
                if existing:
                    return False

                # Добавляем лайк
                await conn.execute(
                    "INSERT INTO likes (from_user, to_user, game) VALUES ($1, $2, $3)",
                    from_user, to_user, game
                )

                # Проверяем взаимность
                mutual = await conn.fetchval(
                    "SELECT 1 FROM likes WHERE from_user = $1 AND to_user = $2 AND game = $3",
                    to_user, from_user, game
                )
                
                if mutual:
                    # Создаем матч
                    user1, user2 = sorted([from_user, to_user])
                    await conn.execute(
                        "INSERT INTO matches (user1, user2, game) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                        user1, user2, game
                    )
                    return True

                return False

    async def get_likes_for_user(self, user_id: int, game: str) -> List[Dict]:
        async with self._pool.acquire() as conn:
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
        async with self._pool.acquire() as conn:
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
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO skipped_likes (user_id, skipped_user_id, game) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                user_id, skipped_user_id, game
            )
            return True

    # === БАНЫ ===
    
    async def is_user_banned(self, user_id: int) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchval(
                "SELECT 1 FROM bans WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP",
                user_id
            )
            return row is not None

    async def get_user_ban(self, user_id: int) -> Optional[Dict]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM bans WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP",
                user_id
            )
            return dict(row) if row else None

    async def get_all_bans(self) -> List[Dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT b.*, u.username, p.name, p.nickname
                   FROM bans b
                   LEFT JOIN users u ON b.user_id = u.telegram_id
                   LEFT JOIN profiles p ON b.user_id = p.telegram_id
                   WHERE b.expires_at > CURRENT_TIMESTAMP
                   ORDER BY b.created_at DESC'''
            )
            return [dict(row) for row in rows]

    async def add_ban(self, user_id: int, reason: str, duration_days: int = 7) -> bool:
        expires_at = datetime.now() + timedelta(days=duration_days)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO bans (user_id, reason, expires_at) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET reason = $2, expires_at = $3",
                user_id, reason, expires_at
            )
            return True

    async def unban_user(self, user_id: int) -> bool:
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM bans WHERE user_id = $1", user_id)
            return True

    # === ЖАЛОБЫ ===
    
    async def add_report(self, reporter_id: int, reported_user_id: int, game: str) -> bool:
        async with self._pool.acquire() as conn:
            try:
                await conn.execute(
                    '''INSERT INTO reports (reporter_id, reported_user_id, game, report_reason, status)
                       VALUES ($1, $2, $3, 'inappropriate_content', 'pending')''',
                    reporter_id, reported_user_id, game
                )
                return True
            except:
                return False  # Уже существует

    async def get_pending_reports(self) -> List[Dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT r.*, p.name, p.nickname, p.photo_id, u.username
                   FROM reports r
                   JOIN profiles p ON r.reported_user_id = p.telegram_id AND r.game = p.game
                   LEFT JOIN users u ON p.telegram_id = u.telegram_id
                   WHERE r.status = 'pending'
                   ORDER BY r.created_at DESC'''
            )
            return [dict(row) for row in rows]

    async def get_report_info(self, report_id: int) -> Optional[Dict]:
        async with self._pool.acquire() as conn:
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
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Получаем информацию о жалобе
                report = await conn.fetchrow("SELECT reported_user_id, game FROM reports WHERE id = $1", report_id)
                if not report:
                    return False

                reported_user_id, game = report

                # Выполняем действие
                if action in ['approve', 'ban']:
                    await self.delete_profile(reported_user_id, game)
                    if action == 'ban':
                        await self.add_ban(reported_user_id, 'нарушение правил')
                    status = action + ('ned' if action == 'ban' else 'd')
                elif action == 'dismiss':
                    status = 'dismissed'
                else:
                    return False

                # Обновляем статус жалобы
                await conn.execute(
                    '''UPDATE reports SET status = $1, reviewed_at = CURRENT_TIMESTAMP, admin_id = $2 WHERE id = $3''',
                    status, admin_id, report_id
                )

                return True