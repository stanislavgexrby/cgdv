import sqlite3
import json
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    _instance = None
    _initialized = False

    def __new__(cls, db_path: str = "data/teammates.db"):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = "data/teammates.db"):
        if Database._initialized:
            return

        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        self._migrate_data()

        if not self._verify_database_integrity():
            logger.error("База данных не прошла проверку целостности")

        Database._initialized = True
        logger.info(f"Database инициализирована: {db_path}")

    def is_user_banned(self, user_id: int) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT 1 FROM bans
                    WHERE user_id = ? AND expires_at > CURRENT_TIMESTAMP
                ''', (user_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Ошибка проверки бана: {e}")
            return False

    def get_user_ban(self, user_id: int) -> Optional[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM bans
                    WHERE user_id = ? AND expires_at > CURRENT_TIMESTAMP
                ''', (user_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения бана: {e}")
            return None

    def get_all_bans(self) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT b.*, u.username, p.name, p.nickname
                    FROM bans b
                    LEFT JOIN users u ON b.user_id = u.telegram_id
                    LEFT JOIN profiles p ON b.user_id = p.telegram_id
                    WHERE b.expires_at > CURRENT_TIMESTAMP
                    ORDER BY b.created_at DESC
                ''')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка получения банов: {e}")
            return []

    def add_ban(self, user_id: int, reason: str, duration_days: int = 7) -> bool:
        try:
            from datetime import datetime, timedelta
            expires_at = datetime.now() + timedelta(days=duration_days)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO bans (user_id, reason, expires_at)
                    VALUES (?, ?, ?)
                ''', (user_id, reason, expires_at))

            logger.info(f"Пользователь {user_id} забанен до {expires_at}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления бана: {e}")
            return False

    def unban_user(self, user_id: int) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))

            logger.info(f"Пользователь {user_id} разбанен")
            return True
        except Exception as e:
            logger.error(f"Ошибка разбанивания: {e}")
            return False

    def get_report_info(self, report_id: int) -> Optional[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT r.*, p.name, p.nickname, u.username
                    FROM reports r
                    LEFT JOIN profiles p ON r.reported_user_id = p.telegram_id AND r.game = p.game
                    LEFT JOIN users u ON p.telegram_id = u.telegram_id
                    WHERE r.id = ?
                ''', (report_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения информации о жалобе: {e}")
            return None

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    current_game TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    game TEXT,
                    name TEXT,
                    nickname TEXT,
                    age INTEGER,
                    rating TEXT,
                    region TEXT,
                    positions TEXT,
                    additional_info TEXT,
                    photo_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(telegram_id, game)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user INTEGER,
                    to_user INTEGER,
                    game TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(from_user, to_user, game)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user1 INTEGER,
                    user2 INTEGER,
                    game TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user1, user2, game)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS skipped_likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    skipped_user_id INTEGER,
                    game TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, skipped_user_id, game)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS search_skipped (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    skipped_user_id INTEGER,
                    game TEXT,
                    skip_count INTEGER DEFAULT 1,
                    last_skipped TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, skipped_user_id, game)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS reports (
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
                )
            ''')

            conn.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                reason TEXT DEFAULT 'нарушение правил',
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def _migrate_data(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT MAX(version) FROM schema_migrations")
                current_version = cursor.fetchone()[0] or 0

                migrations = [
                    (1, self._migration_001_separate_profiles),
                    (2, self._migration_002_add_region_column),
                ]

                for version, migration_func in migrations:
                    if version > current_version:
                        logger.info(f"Применение миграции версии {version}")
                        if migration_func(conn):
                            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
                            logger.info(f"Миграция версии {version} применена успешно")
                        else:
                            logger.error(f"Ошибка применения миграции версии {version}")
                            break

        except Exception as e:
            logger.error(f"Ошибка системы миграций: {e}")

    def _migration_001_separate_profiles(self, conn):
        try:
            cursor = conn.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]

            profile_columns = ['name', 'nickname', 'age', 'rating', 'positions', 'additional_info', 'photo_id']

            if any(col in columns for col in profile_columns):
                cursor = conn.execute(f'''
                    SELECT telegram_id, username, current_game,
                           {', '.join([col for col in profile_columns if col in columns])}
                    FROM users
                    WHERE current_game IS NOT NULL
                ''')

                for row in cursor.fetchall():
                    values = dict(zip(['telegram_id', 'username', 'current_game'] +
                                    [col for col in profile_columns if col in columns], row))

                    if values.get('name'):
                        conn.execute('''
                            INSERT OR REPLACE INTO profiles
                            (telegram_id, game, name, nickname, age, rating, region, positions, additional_info, photo_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            values['telegram_id'],
                            values['current_game'],
                            values.get('name', ''),
                            values.get('nickname', ''),
                            values.get('age', 18),
                            values.get('rating', 'any'),
                            'eeu',
                            values.get('positions', '[]'),
                            values.get('additional_info', ''),
                            values.get('photo_id')
                        ))

                conn.execute('''
                    CREATE TABLE users_new (
                        telegram_id INTEGER PRIMARY KEY,
                        username TEXT,
                        current_game TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    INSERT INTO users_new (telegram_id, username, current_game)
                    SELECT telegram_id, username, current_game FROM users
                ''')

                conn.execute('DROP TABLE users')
                conn.execute('ALTER TABLE users_new RENAME TO users')

            return True
        except Exception as e:
            logger.error(f"Ошибка в миграции 001: {e}")
            return False

    def _migration_002_add_region_column(self, conn):
        try:
            cursor = conn.execute("PRAGMA table_info(profiles)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'region' not in columns:
                conn.execute('ALTER TABLE profiles ADD COLUMN region TEXT DEFAULT "eeu"')
                conn.execute('UPDATE profiles SET region = "eeu" WHERE region IS NULL')

            return True
        except Exception as e:
            logger.error(f"Ошибка в миграции 002: {e}")
            return False

    def _verify_database_integrity(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                required_tables = ['users', 'profiles', 'likes', 'matches', 'reports', 'bans', 'schema_migrations']

                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = [row[0] for row in cursor.fetchall()]

                for table in required_tables:
                    if table not in existing_tables:
                        logger.error(f"Отсутствует обязательная таблица: {table}")
                        return False

                logger.info("Проверка целостности базы данных пройдена")
                return True

        except Exception as e:
            logger.error(f"Ошибка проверки целостности БД: {e}")
            return False

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def get_user_profile(self, telegram_id: int, game: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM profiles WHERE telegram_id = ? AND game = ?",
                (telegram_id, game)
            )
            row = cursor.fetchone()

            if row:
                profile = dict(row)
                if profile['positions']:
                    try:
                        profile['positions'] = json.loads(profile['positions'])
                    except:
                        profile['positions'] = []
                else:
                    profile['positions'] = []

                user = self.get_user(telegram_id)
                if user:
                    profile['username'] = user.get('username')
                    profile['current_game'] = game
                    profile['game'] = game

                return profile

            return None

    def has_profile(self, telegram_id: int, game: str) -> bool:
        profile = self.get_user_profile(telegram_id, game)
        return profile is not None

    def create_user(self, telegram_id: int, username: str, game: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO users (telegram_id, username, current_game)
                    VALUES (?, ?, ?)
                ''', (telegram_id, username, game))
            logger.info(f"Пользователь создан/обновлен: {telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания пользователя: {e}")
            return False

    def update_user_profile(self, telegram_id: int, game: str, name: str, nickname: str,
                          age: int, rating: str, region: str, positions: List[str],
                          additional_info: str, photo_id: str = None) -> bool:
        try:
            positions_json = json.dumps(positions)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO profiles
                    (telegram_id, game, name, nickname, age, rating, region, positions, additional_info, photo_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (telegram_id, game, name, nickname, age, rating, region, positions_json,
                     additional_info, photo_id))

            logger.info(f"Профиль обновлен: {telegram_id} для {game}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления профиля: {e}")
            return False

    def switch_game(self, telegram_id: int, game: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE users SET current_game = ? WHERE telegram_id = ?",
                    (game, telegram_id)
                )
            logger.info(f"Игра переключена: {telegram_id} -> {game}")
            return True
        except Exception as e:
            logger.error(f"Ошибка переключения игры: {e}")
            return False

    def get_potential_matches(self, user_id: int, game: str,
                        rating_filter: str = None,
                        position_filter: str = None,
                        region_filter: str = None,
                        limit: int = 10) -> List[Dict]:
        try:
            base_query = '''
                SELECT p.*, u.username
                FROM profiles p
                JOIN users u ON p.telegram_id = u.telegram_id
                WHERE p.telegram_id != ?
                AND p.game = ?
                AND p.telegram_id NOT IN (
                    SELECT to_user FROM likes
                    WHERE from_user = ? AND game = ?
                )
                AND p.telegram_id NOT IN (
                    SELECT reported_user_id FROM reports
                    WHERE reporter_id = ? AND game = ?
                )
            '''
            params = [user_id, game, user_id, game, user_id, game]

            if rating_filter:
                base_query += " AND (p.rating = ? OR p.rating = 'any')"
                params.append(rating_filter)

            if position_filter:
                base_query += " AND (p.positions LIKE ? OR p.positions LIKE '%\"any\"%')"
                params.append(f'%"{position_filter}"%')

            if region_filter:
                base_query += " AND (p.region = ? OR p.region = 'any')"
                params.append(region_filter)

            skip_query = '''
                SELECT skipped_user_id, skip_count, last_skipped
                FROM search_skipped
                WHERE user_id = ? AND game = ?
            '''

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute(base_query, params)
                all_profiles = cursor.fetchall()

                cursor = conn.execute(skip_query, [user_id, game])
                skips = {row['skipped_user_id']: row for row in cursor.fetchall()}

                priority_1 = []
                priority_2 = []
                priority_3 = []

                import random
                from datetime import datetime, timedelta

                now = datetime.now()

                for row in all_profiles:
                    profile = dict(row)
                    telegram_id = profile['telegram_id']

                    if telegram_id in skips:
                        skip_info = skips[telegram_id]
                        last_skipped = datetime.fromisoformat(skip_info['last_skipped'].replace('Z', '+00:00'))
                        days_since_skip = (now - last_skipped).days

                        if days_since_skip >= 3:
                            priority_2.append(profile)
                        else:
                            priority_3.append(profile)
                    else:
                        priority_1.append(profile)

                random.shuffle(priority_1)
                random.shuffle(priority_2)
                random.shuffle(priority_3)

                final_profiles = priority_1 + priority_2 + priority_3

                final_profiles = final_profiles[:limit]

                results = []
                for profile in final_profiles:
                    if profile['positions']:
                        try:
                            profile['positions'] = json.loads(profile['positions'])
                        except:
                            profile['positions'] = []
                    else:
                        profile['positions'] = []

                    profile['current_game'] = profile['game']
                    results.append(profile)

                return results

        except Exception as e:
            logger.error(f"Ошибка поиска совпадений: {e}")
            return []

    def add_search_skip(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO search_skipped (user_id, skipped_user_id, game, skip_count, last_skipped)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, skipped_user_id, game)
                    DO UPDATE SET
                        skip_count = skip_count + 1,
                        last_skipped = CURRENT_TIMESTAMP
                ''', (user_id, skipped_user_id, game))

            logger.info(f"Пропуск в поиске записан: {user_id} пропустил {skipped_user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка записи пропуска в поиске: {e}")
            return False

    def add_like(self, from_user: int, to_user: int, game: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT 1 FROM likes
                    WHERE from_user = ? AND to_user = ? AND game = ?
                ''', (from_user, to_user, game))
                if cursor.fetchone():
                    logger.info(f"Лайк уже существует: {from_user} -> {to_user}")
                    return False
                conn.execute('''
                    INSERT INTO likes (from_user, to_user, game)
                    VALUES (?, ?, ?)
                ''', (from_user, to_user, game))
                cursor = conn.execute('''
                    SELECT 1 FROM likes
                    WHERE from_user = ? AND to_user = ? AND game = ?
                ''', (to_user, from_user, game))
                if cursor.fetchone():
                    user1, user2 = min(from_user, to_user), max(from_user, to_user)
                    cursor = conn.execute('''
                        SELECT 1 FROM matches
                        WHERE user1 = ? AND user2 = ? AND game = ?
                    ''', (user1, user2, game))

                    if not cursor.fetchone():
                        conn.execute('''
                            INSERT INTO matches (user1, user2, game)
                            VALUES (?, ?, ?)
                        ''', (user1, user2, game))
                        logger.info(f"Матч создан: {from_user} <-> {to_user}")
                        return True

            logger.info(f"Лайк добавлен: {from_user} -> {to_user}")
            return False

        except Exception as e:
            logger.error(f"Ошибка добавления лайка: {e}")
            return False

    def get_likes_for_user(self, user_id: int, game: str) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT p.*, u.username FROM profiles p
                    JOIN users u ON p.telegram_id = u.telegram_id
                    JOIN likes l ON p.telegram_id = l.from_user
                    WHERE l.to_user = ? AND l.game = ? AND p.game = ?
                    AND NOT EXISTS (
                        -- Исключаем если уже есть матч
                        SELECT 1 FROM matches m
                        WHERE ((m.user1 = ? AND m.user2 = p.telegram_id) OR
                               (m.user1 = p.telegram_id AND m.user2 = ?))
                        AND m.game = ?
                    )
                    AND NOT EXISTS (
                        -- Исключаем если лайк уже пропущен
                        SELECT 1 FROM skipped_likes sl
                        WHERE sl.user_id = ? AND sl.skipped_user_id = p.telegram_id AND sl.game = ?
                    )
                    ORDER BY l.created_at DESC
                ''', (user_id, game, game, user_id, user_id, game, user_id, game))

                results = []
                for row in cursor.fetchall():
                    profile = dict(row)
                    if profile['positions']:
                        try:
                            profile['positions'] = json.loads(profile['positions'])
                        except:
                            profile['positions'] = []
                    else:
                        profile['positions'] = []

                    profile['current_game'] = profile['game']
                    results.append(profile)

                return results

        except Exception as e:
            logger.error(f"Ошибка получения лайков: {e}")
            return []

    def get_matches(self, user_id: int, game: str) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT p.*, u.username FROM profiles p
                    JOIN users u ON p.telegram_id = u.telegram_id
                    JOIN matches m ON (p.telegram_id = m.user1 OR p.telegram_id = m.user2)
                    WHERE (m.user1 = ? OR m.user2 = ?)
                    AND p.telegram_id != ?
                    AND m.game = ? AND p.game = ?
                    ORDER BY m.created_at DESC
                ''', (user_id, user_id, user_id, game, game))

                results = []
                for row in cursor.fetchall():
                    profile = dict(row)
                    if profile['positions']:
                        try:
                            profile['positions'] = json.loads(profile['positions'])
                        except:
                            profile['positions'] = []
                    else:
                        profile['positions'] = []

                    profile['current_game'] = profile['game']
                    results.append(profile)

                return results

        except Exception as e:
            logger.error(f"Ошибка получения матчей: {e}")
            return []

    def skip_like(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR IGNORE INTO skipped_likes (user_id, skipped_user_id, game)
                    VALUES (?, ?, ?)
                ''', (user_id, skipped_user_id, game))

            logger.info(f"Лайк пропущен: {user_id} пропустил {skipped_user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка пропуска лайка: {e}")
            return False

    def delete_profile(self, telegram_id: int, game: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM likes WHERE (from_user = ? OR to_user = ?) AND game = ?", 
                           (telegram_id, telegram_id, game))
                conn.execute("DELETE FROM matches WHERE (user1 = ? OR user2 = ?) AND game = ?", 
                           (telegram_id, telegram_id, game))

                conn.execute("DELETE FROM skipped_likes WHERE (user_id = ? OR skipped_user_id = ?) AND game = ?", 
                           (telegram_id, telegram_id, game))

                conn.execute('DELETE FROM profiles WHERE telegram_id = ? AND game = ?', 
                           (telegram_id, game))

                conn.execute("DELETE FROM reports WHERE reported_user_id = ? AND game = ?", 
           (telegram_id, game))

            logger.info(f"Профиль удален: {telegram_id} для {game}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления профиля: {e}")
            return False

    def add_report(self, reporter_id: int, reported_user_id: int, game: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR IGNORE INTO reports
                    (reporter_id, reported_user_id, game, report_reason, status)
                    VALUES (?, ?, ?, 'inappropriate_content', 'pending')
                ''', (reporter_id, reported_user_id, game))

            logger.info(f"Жалоба добавлена: {reporter_id} пожаловался на {reported_user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления жалобы: {e}")
            return False

    def get_pending_reports(self) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT r.*, p.name, p.nickname, p.photo_id, u.username
                    FROM reports r
                    JOIN profiles p ON r.reported_user_id = p.telegram_id AND r.game = p.game
                    LEFT JOIN users u ON p.telegram_id = u.telegram_id
                    WHERE r.status = 'pending'
                    ORDER BY r.created_at DESC
                ''')

                results = []
                for row in cursor.fetchall():
                    report = dict(row)
                    results.append(report)

                return results

        except Exception as e:
            logger.error(f"Ошибка получения жалоб: {e}")
            return []

    def process_report(self, report_id: int, action: str, admin_id: int) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT reported_user_id, game FROM reports WHERE id = ?
                ''', (report_id,))
                report = cursor.fetchone()

                if not report:
                    return False

                reported_user_id, game = report

                if action == 'approve':
                    self.delete_profile(reported_user_id, game)
                    status = 'approved'
                elif action == 'ban':
                    self.delete_profile(reported_user_id, game)
                    self.add_ban(reported_user_id, 'нарушение правил')
                    status = 'banned'
                elif action == 'dismiss':
                    status = 'dismissed'
                else:
                    return False

                conn.execute('''
                    UPDATE reports
                    SET status = ?, reviewed_at = CURRENT_TIMESTAMP, admin_id = ?
                    WHERE id = ?
                ''', (status, admin_id, report_id))

            logger.info(f"Жалоба {report_id} обработана админом {admin_id}: {action}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обработки жалобы: {e}")
            return False