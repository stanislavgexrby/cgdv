import sqlite3
import json
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "data/teammates.db"):
        self.db_path = db_path

        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self._init_db()
        self._migrate_data()
        logger.info(f"Database инициализирована: {db_path}")

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Таблица пользователей (основная информация)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    current_game TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица профилей для каждой игры
            conn.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER,
                    game TEXT,
                    name TEXT,
                    nickname TEXT,
                    age INTEGER,
                    rating TEXT,
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

            # Новая таблица для отслеживания пропущенных лайков
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
            # Новая таблица для жалоб (добавить после таблицы search_skipped)
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

    def _migrate_data(self):
        """Миграция существующих данных из старой структуры в новую"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Проверяем, есть ли старые данные для миграции
                cursor = conn.execute("PRAGMA table_info(users)")
                columns = [column[1] for column in cursor.fetchall()]
                
                if 'name' in columns:
                    # Мигрируем данные из старой структуры
                    cursor = conn.execute('''
                        SELECT telegram_id, current_game, name, nickname, age, rating, 
                               positions, additional_info, photo_id 
                        FROM users 
                        WHERE name IS NOT NULL
                    ''')
                    
                    for row in cursor.fetchall():
                        telegram_id, game, name, nickname, age, rating, positions, additional_info, photo_id = row
                        
                        # Создаем профиль для игры пользователя
                        conn.execute('''
                            INSERT OR REPLACE INTO profiles 
                            (telegram_id, game, name, nickname, age, rating, positions, additional_info, photo_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (telegram_id, game, name, nickname, age, rating, positions, additional_info, photo_id))
                    
                    # Удаляем старые колонки из таблицы users
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
                    
                    logger.info("Миграция данных завершена")
        except Exception as e:
            logger.error(f"Ошибка миграции данных: {e}")

    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Получить основную информацию о пользователе"""
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
        """Получить профиль пользователя для конкретной игры"""
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

                # Добавляем username из основной таблицы
                user = self.get_user(telegram_id)
                if user:
                    profile['username'] = user.get('username')
                    profile['current_game'] = game
                    profile['game'] = game

                return profile

            return None

    def has_profile(self, telegram_id: int, game: str) -> bool:
        """Проверить, есть ли у пользователя профиль для конкретной игры"""
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
                          age: int, rating: str, positions: List[str],
                          additional_info: str, photo_id: str = None) -> bool:
        try:
            positions_json = json.dumps(positions)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO profiles 
                    (telegram_id, game, name, nickname, age, rating, positions, additional_info, photo_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (telegram_id, game, name, nickname, age, rating, positions_json,
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
                            limit: int = 10) -> List[Dict]:
        try:
            # Сначала получаем всех подходящих пользователей
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
            '''
            params = [user_id, game, user_id, game]

            if rating_filter:
                base_query += " AND p.rating = ?"
                params.append(rating_filter)

            if position_filter:
                base_query += " AND p.positions LIKE ?"
                params.append(f'%"{position_filter}"%')

            # Получаем информацию о пропусках отдельным запросом
            skip_query = '''
                SELECT skipped_user_id, skip_count, last_skipped
                FROM search_skipped
                WHERE user_id = ? AND game = ?
            '''

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Получаем всех потенциальных кандидатов
                cursor = conn.execute(base_query, params)
                all_profiles = cursor.fetchall()

                # Получаем информацию о пропусках
                cursor = conn.execute(skip_query, [user_id, game])
                skips = {row['skipped_user_id']: row for row in cursor.fetchall()}

                # Разделяем профили по приоритетам в Python
                priority_1 = []  # Новые (никогда не пропускались)
                priority_2 = []  # Пропущенные давно  
                priority_3 = []  # Пропущенные недавно

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

                        if days_since_skip >= 3:  # Давно пропускали
                            priority_2.append(profile)
                        else:  # Недавно пропускали  
                            priority_3.append(profile)
                    else:
                        # Никогда не пропускали
                        priority_1.append(profile)

                # Перемешиваем каждую группу
                random.shuffle(priority_1)
                random.shuffle(priority_2) 
                random.shuffle(priority_3)

                # Объединяем в порядке приоритета
                final_profiles = priority_1 + priority_2 + priority_3

                # Ограничиваем результат
                final_profiles = final_profiles[:limit]

                # Обрабатываем результаты
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
        """Запомнить, что пользователь пропустил анкету в поиске"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Увеличиваем счетчик пропусков или создаем запись
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
        """Добавить лайк и проверить на матч"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Проверяем, нет ли уже такого лайка
                cursor = conn.execute('''
                    SELECT 1 FROM likes 
                    WHERE from_user = ? AND to_user = ? AND game = ?
                ''', (from_user, to_user, game))
                if cursor.fetchone():
                    # Лайк уже существует
                    logger.info(f"Лайк уже существует: {from_user} -> {to_user}")
                    return False
                # Добавляем лайк
                conn.execute('''
                    INSERT INTO likes (from_user, to_user, game)
                    VALUES (?, ?, ?)
                ''', (from_user, to_user, game))
                # Проверяем взаимный лайк
                cursor = conn.execute('''
                    SELECT 1 FROM likes 
                    WHERE from_user = ? AND to_user = ? AND game = ?
                ''', (to_user, from_user, game))
                if cursor.fetchone():
                    # Есть взаимный лайк - создаем матч
                    user1, user2 = min(from_user, to_user), max(from_user, to_user)
                    # Проверяем, нет ли уже матча
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
        """Получить лайки для пользователя (исключая уже обработанные)"""
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
        """Получить матчи пользователя"""
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
        """Отметить лайк как пропущенный"""
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
        """Удалить профиль для конкретной игры"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Удаляем лайки и матчи для этой игры
                conn.execute("DELETE FROM likes WHERE (from_user = ? OR to_user = ?) AND game = ?", 
                           (telegram_id, telegram_id, game))
                conn.execute("DELETE FROM matches WHERE (user1 = ? OR user2 = ?) AND game = ?", 
                           (telegram_id, telegram_id, game))

                # Удаляем пропущенные лайки для этой игры
                conn.execute("DELETE FROM skipped_likes WHERE (user_id = ? OR skipped_user_id = ?) AND game = ?", 
                           (telegram_id, telegram_id, game))

                # Удаляем профиль для этой игры
                conn.execute('DELETE FROM profiles WHERE telegram_id = ? AND game = ?', 
                           (telegram_id, game))

                # Удаляем жалобы связанные с этой анкетой
                conn.execute("DELETE FROM reports WHERE reported_user_id = ? AND game = ?", 
           (telegram_id, game))

            logger.info(f"Профиль удален: {telegram_id} для {game}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления профиля: {e}")
            return False

    def add_report(self, reporter_id: int, reported_user_id: int, game: str) -> bool:
        """Добавить жалобу на пользователя"""
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
        """Получить все необработанные жалобы"""
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
        """Обработать жалобу (approve - удалить профиль, dismiss - отклонить)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Получаем информацию о жалобе
                cursor = conn.execute('''
                    SELECT reported_user_id, game FROM reports WHERE id = ?
                ''', (report_id,))
                report = cursor.fetchone()

                if not report:
                    return False

                reported_user_id, game = report

                if action == 'approve':
                    # Удаляем профиль пользователя
                    self.delete_profile(reported_user_id, game)
                    status = 'approved'
                elif action == 'dismiss':
                    status = 'dismissed'
                else:
                    return False

                # Обновляем статус жалобы
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