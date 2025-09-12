import sqlite3
import json
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "data/teammates.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        self._migrate_data()
        logger.info(f"Database инициализирована: {db_path}")

    def _execute_query(self, query: str, params: tuple = (), fetch: str = None):
        """Универсальный метод для выполнения запросов с обработкой ошибок"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if fetch:
                    conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)

                if fetch == 'one':
                    return cursor.fetchone()
                elif fetch == 'all':
                    return cursor.fetchall()
                else:
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            return None if fetch else False

    def _parse_positions(self, positions_str: str) -> List[str]:
        """Парсинг позиций из JSON строки"""
        if not positions_str:
            return []
        try:
            return json.loads(positions_str)
        except:
            return []

    def _format_profile(self, row) -> Dict:
        """Форматирование профиля с парсингом позиций"""
        if not row:
            return None
        
        profile = dict(row)
        profile['positions'] = self._parse_positions(profile.get('positions', ''))
        profile['current_game'] = profile.get('game')
        return profile

    def _init_db(self):
        """Инициализация базы данных"""
        tables = [
            '''CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                current_game TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                game TEXT,
                name TEXT,
                nickname TEXT,
                age INTEGER,
                rating TEXT,
                region TEXT DEFAULT 'eeu',
                positions TEXT,
                additional_info TEXT,
                photo_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(telegram_id, game)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER,
                to_user INTEGER,
                game TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_user, to_user, game)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1 INTEGER,
                user2 INTEGER,
                game TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user1, user2, game)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS skipped_likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                skipped_user_id INTEGER,
                game TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, skipped_user_id, game)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS search_skipped (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                skipped_user_id INTEGER,
                game TEXT,
                skip_count INTEGER DEFAULT 1,
                last_skipped TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, skipped_user_id, game)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER,
                reported_user_id INTEGER,
                game TEXT,
                report_reason TEXT DEFAULT 'inappropriate_content',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                admin_id INTEGER,
                UNIQUE(reporter_id, reported_user_id, game)
            )''',
            
            '''CREATE TABLE IF NOT EXISTS bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                reason TEXT DEFAULT 'нарушение правил',
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            '''CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        ]

        with sqlite3.connect(self.db_path) as conn:
            for table_sql in tables:
                conn.execute(table_sql)

    def _migrate_data(self):
        """Простая система миграций"""
        current_version = self._execute_query(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations", 
            fetch='one'
        )
        current_version = current_version[0] if current_version else 0

        # Миграция 1: добавление region колонки, если её нет
        if current_version < 1:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # Проверяем есть ли колонка region
                    cursor = conn.execute("PRAGMA table_info(profiles)")
                    columns = [col[1] for col in cursor.fetchall()]
                    
                    if 'region' not in columns:
                        conn.execute('ALTER TABLE profiles ADD COLUMN region TEXT DEFAULT "eeu"')
                        conn.execute('UPDATE profiles SET region = "eeu" WHERE region IS NULL')
                    
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (1)")
                    logger.info("Миграция 1 применена успешно")
            except Exception as e:
                logger.error(f"Ошибка миграции 1: {e}")

    # === МЕТОДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ===

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        row = self._execute_query(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,), fetch='one'
        )
        return dict(row) if row else None

    def create_user(self, telegram_id: int, username: str, game: str) -> bool:
        success = self._execute_query(
            "INSERT OR REPLACE INTO users (telegram_id, username, current_game) VALUES (?, ?, ?)",
            (telegram_id, username, game)
        )
        if success:
            logger.info(f"Пользователь создан/обновлен: {telegram_id}")
        return success

    def switch_game(self, telegram_id: int, game: str) -> bool:
        success = self._execute_query(
            "UPDATE users SET current_game = ? WHERE telegram_id = ?",
            (game, telegram_id)
        )
        if success:
            logger.info(f"Игра переключена: {telegram_id} -> {game}")
        return success

    # === МЕТОДЫ ДЛЯ ПРОФИЛЕЙ ===

    def get_user_profile(self, telegram_id: int, game: str) -> Optional[Dict]:
        row = self._execute_query(
            "SELECT * FROM profiles WHERE telegram_id = ? AND game = ?",
            (telegram_id, game), fetch='one'
        )
        
        if not row:
            return None
            
        profile = self._format_profile(row)
        
        # Добавляем username из таблицы users
        user = self.get_user(telegram_id)
        if user:
            profile['username'] = user.get('username')
            
        return profile

    def has_profile(self, telegram_id: int, game: str) -> bool:
        return self.get_user_profile(telegram_id, game) is not None

    def update_user_profile(self, telegram_id: int, game: str, name: str, nickname: str,
                          age: int, rating: str, region: str, positions: List[str],
                          additional_info: str, photo_id: str = None) -> bool:
        success = self._execute_query(
            '''INSERT OR REPLACE INTO profiles
               (telegram_id, game, name, nickname, age, rating, region, positions, additional_info, photo_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (telegram_id, game, name, nickname, age, rating, region, 
             json.dumps(positions), additional_info, photo_id)
        )
        if success:
            logger.info(f"Профиль обновлен: {telegram_id} для {game}")
        return success

    def delete_profile(self, telegram_id: int, game: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Удаляем все связанные данные одной транзакцией
                queries = [
                    ("DELETE FROM likes WHERE (from_user = ? OR to_user = ?) AND game = ?", 
                     (telegram_id, telegram_id, game)),
                    ("DELETE FROM matches WHERE (user1 = ? OR user2 = ?) AND game = ?", 
                     (telegram_id, telegram_id, game)),
                    ("DELETE FROM skipped_likes WHERE (user_id = ? OR skipped_user_id = ?) AND game = ?", 
                     (telegram_id, telegram_id, game)),
                    ("DELETE FROM reports WHERE reported_user_id = ? AND game = ?", 
                     (telegram_id, game)),
                    ("DELETE FROM profiles WHERE telegram_id = ? AND game = ?", 
                     (telegram_id, game))
                ]
                
                for query, params in queries:
                    conn.execute(query, params)
                    
            logger.info(f"Профиль удален: {telegram_id} для {game}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления профиля: {e}")
            return False

    # === МЕТОДЫ ДЛЯ ПОИСКА ===

    def get_potential_matches(self, user_id: int, game: str,
                            rating_filter: str = None,
                            position_filter: str = None,
                            region_filter: str = None,
                            limit: int = 10) -> List[Dict]:
        
        # Базовый запрос исключающий уже лайкнутых и заблокированных
        base_query = '''
            SELECT p.*, u.username
            FROM profiles p
            JOIN users u ON p.telegram_id = u.telegram_id
            WHERE p.telegram_id != ? AND p.game = ?
            AND p.telegram_id NOT IN (
                SELECT to_user FROM likes WHERE from_user = ? AND game = ?
            )
            AND p.telegram_id NOT IN (
                SELECT reported_user_id FROM reports WHERE reporter_id = ? AND game = ?
            )
        '''
        params = [user_id, game, user_id, game, user_id, game]

        # Добавляем фильтры
        if rating_filter and rating_filter != 'any':
            base_query += " AND p.rating = ?"
            params.append(rating_filter)

        if position_filter and position_filter != 'any':
            base_query += " AND p.positions LIKE ?"
            params.append(f'%"{position_filter}"%')

        if region_filter and region_filter != 'any':
            base_query += " AND p.region = ?"
            params.append(region_filter)

        base_query += " ORDER BY RANDOM() LIMIT ?"
        params.append(limit)

        rows = self._execute_query(base_query, tuple(params), fetch='all')
        
        return [self._format_profile(row) for row in rows] if rows else []

    def add_search_skip(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        success = self._execute_query(
            '''INSERT INTO search_skipped (user_id, skipped_user_id, game, skip_count, last_skipped)
               VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, skipped_user_id, game)
               DO UPDATE SET skip_count = skip_count + 1, last_skipped = CURRENT_TIMESTAMP''',
            (user_id, skipped_user_id, game)
        )
        if success:
            logger.info(f"Пропуск в поиске записан: {user_id} пропустил {skipped_user_id}")
        return success

    # === МЕТОДЫ ДЛЯ ЛАЙКОВ И МАТЧЕЙ ===

    def add_like(self, from_user: int, to_user: int, game: str) -> bool:
        """Добавляет лайк и возвращает True если это матч"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Проверяем, есть ли уже такой лайк
                cursor = conn.execute(
                    "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ? AND game = ?",
                    (from_user, to_user, game)
                )
                if cursor.fetchone():
                    return False

                # Добавляем лайк
                conn.execute(
                    "INSERT INTO likes (from_user, to_user, game) VALUES (?, ?, ?)",
                    (from_user, to_user, game)
                )

                # Проверяем взаимный лайк
                cursor = conn.execute(
                    "SELECT 1 FROM likes WHERE from_user = ? AND to_user = ? AND game = ?",
                    (to_user, from_user, game)
                )
                
                if cursor.fetchone():
                    # Создаем матч
                    user1, user2 = min(from_user, to_user), max(from_user, to_user)
                    conn.execute(
                        "INSERT OR IGNORE INTO matches (user1, user2, game) VALUES (?, ?, ?)",
                        (user1, user2, game)
                    )
                    logger.info(f"Матч создан: {from_user} <-> {to_user}")
                    return True

            logger.info(f"Лайк добавлен: {from_user} -> {to_user}")
            return False
        except Exception as e:
            logger.error(f"Ошибка добавления лайка: {e}")
            return False

    def get_likes_for_user(self, user_id: int, game: str) -> List[Dict]:
        rows = self._execute_query(
            '''SELECT p.*, u.username FROM profiles p
               JOIN users u ON p.telegram_id = u.telegram_id
               JOIN likes l ON p.telegram_id = l.from_user
               WHERE l.to_user = ? AND l.game = ? AND p.game = ?
               AND NOT EXISTS (
                   SELECT 1 FROM matches m
                   WHERE ((m.user1 = ? AND m.user2 = p.telegram_id) OR
                          (m.user1 = p.telegram_id AND m.user2 = ?))
                   AND m.game = ?
               )
               AND NOT EXISTS (
                   SELECT 1 FROM skipped_likes sl
                   WHERE sl.user_id = ? AND sl.skipped_user_id = p.telegram_id AND sl.game = ?
               )
               ORDER BY l.created_at DESC''',
            (user_id, game, game, user_id, user_id, game, user_id, game),
            fetch='all'
        )
        
        return [self._format_profile(row) for row in rows] if rows else []

    def get_matches(self, user_id: int, game: str) -> List[Dict]:
        rows = self._execute_query(
            '''SELECT p.*, u.username FROM profiles p
               JOIN users u ON p.telegram_id = u.telegram_id
               JOIN matches m ON (p.telegram_id = m.user1 OR p.telegram_id = m.user2)
               WHERE (m.user1 = ? OR m.user2 = ?) AND p.telegram_id != ?
               AND m.game = ? AND p.game = ?
               ORDER BY m.created_at DESC''',
            (user_id, user_id, user_id, game, game),
            fetch='all'
        )
        
        return [self._format_profile(row) for row in rows] if rows else []

    def skip_like(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        success = self._execute_query(
            "INSERT OR IGNORE INTO skipped_likes (user_id, skipped_user_id, game) VALUES (?, ?, ?)",
            (user_id, skipped_user_id, game)
        )
        if success:
            logger.info(f"Лайк пропущен: {user_id} пропустил {skipped_user_id}")
        return success

    # === МЕТОДЫ ДЛЯ БАНОВ ===

    def is_user_banned(self, user_id: int) -> bool:
        row = self._execute_query(
            "SELECT 1 FROM bans WHERE user_id = ? AND expires_at > CURRENT_TIMESTAMP",
            (user_id,), fetch='one'
        )
        return row is not None

    def get_user_ban(self, user_id: int) -> Optional[Dict]:
        row = self._execute_query(
            "SELECT * FROM bans WHERE user_id = ? AND expires_at > CURRENT_TIMESTAMP",
            (user_id,), fetch='one'
        )
        return dict(row) if row else None

    def get_all_bans(self) -> List[Dict]:
        rows = self._execute_query(
            '''SELECT b.*, u.username, p.name, p.nickname
               FROM bans b
               LEFT JOIN users u ON b.user_id = u.telegram_id
               LEFT JOIN profiles p ON b.user_id = p.telegram_id
               WHERE b.expires_at > CURRENT_TIMESTAMP
               ORDER BY b.created_at DESC''',
            fetch='all'
        )
        return [dict(row) for row in rows] if rows else []

    def add_ban(self, user_id: int, reason: str, duration_days: int = 7) -> bool:
        expires_at = datetime.now() + timedelta(days=duration_days)
        success = self._execute_query(
            "INSERT OR REPLACE INTO bans (user_id, reason, expires_at) VALUES (?, ?, ?)",
            (user_id, reason, expires_at)
        )
        if success:
            logger.info(f"Пользователь {user_id} забанен до {expires_at}")
        return success

    def unban_user(self, user_id: int) -> bool:
        success = self._execute_query(
            "DELETE FROM bans WHERE user_id = ?",
            (user_id,)
        )
        if success:
            logger.info(f"Пользователь {user_id} разбанен")
        return success

    # === МЕТОДЫ ДЛЯ ЖАЛОБ ===

    def add_report(self, reporter_id: int, reported_user_id: int, game: str) -> bool:
        success = self._execute_query(
            '''INSERT OR IGNORE INTO reports
               (reporter_id, reported_user_id, game, report_reason, status)
               VALUES (?, ?, ?, 'inappropriate_content', 'pending')''',
            (reporter_id, reported_user_id, game)
        )
        if success:
            logger.info(f"Жалоба добавлена: {reporter_id} пожаловался на {reported_user_id}")
        return success

    def get_pending_reports(self) -> List[Dict]:
        rows = self._execute_query(
            '''SELECT r.*, p.name, p.nickname, p.photo_id, u.username
               FROM reports r
               JOIN profiles p ON r.reported_user_id = p.telegram_id AND r.game = p.game
               LEFT JOIN users u ON p.telegram_id = u.telegram_id
               WHERE r.status = 'pending'
               ORDER BY r.created_at DESC''',
            fetch='all'
        )
        return [dict(row) for row in rows] if rows else []

    def get_report_info(self, report_id: int) -> Optional[Dict]:
        row = self._execute_query(
            '''SELECT r.*, p.name, p.nickname, u.username
               FROM reports r
               LEFT JOIN profiles p ON r.reported_user_id = p.telegram_id AND r.game = p.game
               LEFT JOIN users u ON p.telegram_id = u.telegram_id
               WHERE r.id = ?''',
            (report_id,), fetch='one'
        )
        return dict(row) if row else None

    def process_report(self, report_id: int, action: str, admin_id: int) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Получаем информацию о жалобе
                cursor = conn.execute("SELECT reported_user_id, game FROM reports WHERE id = ?", (report_id,))
                report = cursor.fetchone()
                
                if not report:
                    return False

                reported_user_id, game = report

                # Выполняем действие
                if action in ['approve', 'ban']:
                    self.delete_profile(reported_user_id, game)
                    if action == 'ban':
                        self.add_ban(reported_user_id, 'нарушение правил')
                    status = action + ('ned' if action == 'ban' else 'd')
                elif action == 'dismiss':
                    status = 'dismissed'
                else:
                    return False

                # Обновляем статус жалобы
                conn.execute(
                    '''UPDATE reports SET status = ?, reviewed_at = CURRENT_TIMESTAMP, admin_id = ?
                       WHERE id = ?''',
                    (status, admin_id, report_id)
                )

            logger.info(f"Жалоба {report_id} обработана админом {admin_id}: {action}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обработки жалобы: {e}")
            return False