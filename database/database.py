# database/database.py
"""
Простая база данных для TeammateBot
"""

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
        
        # Создаем папку для БД
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Инициализируем БД
        self._init_db()
        logger.info(f"Database инициализирована: {db_path}")
    
    def _init_db(self):
        """Создание таблиц"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    current_game TEXT,
                    name TEXT,
                    nickname TEXT,
                    age INTEGER,
                    rating TEXT,
                    positions TEXT,
                    additional_info TEXT,
                    photo_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
    def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Получить пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", 
                (telegram_id,)
            )
            row = cursor.fetchone()
            
            if row:
                user = dict(row)
                # Парсим позиции
                if user['positions']:
                    try:
                        user['positions'] = json.loads(user['positions'])
                    except:
                        user['positions'] = []
                else:
                    user['positions'] = []
                
                # Добавляем game для совместимости
                user['game'] = user['current_game']
                return user
            
            return None
    
    def create_user(self, telegram_id: int, username: str, game: str) -> bool:
        """Создать/обновить пользователя"""
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
    
    def update_user_profile(self, telegram_id: int, name: str, nickname: str, 
                          age: int, rating: str, positions: List[str], 
                          additional_info: str, photo_id: str = None) -> bool:
        """Обновить профиль пользователя"""
        try:
            positions_json = json.dumps(positions)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE users SET 
                    name = ?, nickname = ?, age = ?, rating = ?, 
                    positions = ?, additional_info = ?, photo_id = ?
                    WHERE telegram_id = ?
                ''', (name, nickname, age, rating, positions_json, 
                     additional_info, photo_id, telegram_id))
            
            logger.info(f"Профиль обновлен: {telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления профиля: {e}")
            return False
    
    def switch_game(self, telegram_id: int, game: str) -> bool:
        """Переключить игру"""
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
        """Получить потенциальные совпадения"""
        try:
            query = '''
                SELECT * FROM users 
                WHERE telegram_id != ? 
                AND current_game = ?
                AND name IS NOT NULL
                AND telegram_id NOT IN (
                    SELECT to_user FROM likes 
                    WHERE from_user = ? AND game = ?
                )
            '''
            params = [user_id, game, user_id, game]
            
            # Добавляем фильтры
            if rating_filter:
                query += " AND rating = ?"
                params.append(rating_filter)
            
            if position_filter:
                query += " AND positions LIKE ?"
                params.append(f'%"{position_filter}"%')
            
            query += " ORDER BY RANDOM() LIMIT ?"
            params.append(limit)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    user = dict(row)
                    # Парсим позиции
                    if user['positions']:
                        try:
                            user['positions'] = json.loads(user['positions'])
                        except:
                            user['positions'] = []
                    else:
                        user['positions'] = []
                    
                    # Добавляем game для совместимости
                    user['game'] = user['current_game']
                    results.append(user)
                
                return results
                
        except Exception as e:
            logger.error(f"Ошибка поиска совпадений: {e}")
            return []
    
    def add_like(self, from_user: int, to_user: int, game: str) -> bool:
        """Добавить лайк, возвращает True если это матч"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Добавляем лайк
                conn.execute('''
                    INSERT OR IGNORE INTO likes (from_user, to_user, game)
                    VALUES (?, ?, ?)
                ''', (from_user, to_user, game))
                
                # Проверяем взаимный лайк
                cursor = conn.execute('''
                    SELECT 1 FROM likes 
                    WHERE from_user = ? AND to_user = ? AND game = ?
                ''', (to_user, from_user, game))
                
                if cursor.fetchone():
                    # Создаем матч
                    user1, user2 = min(from_user, to_user), max(from_user, to_user)
                    conn.execute('''
                        INSERT OR IGNORE INTO matches (user1, user2, game)
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
        """Получить лайки для пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT u.* FROM users u
                    JOIN likes l ON u.telegram_id = l.from_user
                    WHERE l.to_user = ? AND l.game = ?
                    AND NOT EXISTS (
                        SELECT 1 FROM likes l2 
                        WHERE l2.from_user = ? AND l2.to_user = u.telegram_id AND l2.game = ?
                    )
                    ORDER BY l.created_at DESC
                ''', (user_id, game, user_id, game))
                
                results = []
                for row in cursor.fetchall():
                    user = dict(row)
                    # Парсим позиции
                    if user['positions']:
                        try:
                            user['positions'] = json.loads(user['positions'])
                        except:
                            user['positions'] = []
                    else:
                        user['positions'] = []
                    
                    # Добавляем game для совместимости
                    user['game'] = user['current_game']
                    results.append(user)
                
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
                    SELECT u.* FROM users u 
                    JOIN matches m ON (u.telegram_id = m.user1 OR u.telegram_id = m.user2)
                    WHERE (m.user1 = ? OR m.user2 = ?) 
                    AND u.telegram_id != ?
                    AND m.game = ?
                    ORDER BY m.created_at DESC
                ''', (user_id, user_id, user_id, game))
                
                results = []
                for row in cursor.fetchall():
                    user = dict(row)
                    # Парсим позиции
                    if user['positions']:
                        try:
                            user['positions'] = json.loads(user['positions'])
                        except:
                            user['positions'] = []
                    else:
                        user['positions'] = []
                    
                    # Добавляем game для совместимости
                    user['game'] = user['current_game']
                    results.append(user)
                
                return results
                
        except Exception as e:
            logger.error(f"Ошибка получения матчей: {e}")
            return []
    
    def delete_profile(self, telegram_id: int) -> bool:
        """Удалить профиль"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Удаляем лайки и матчи
                conn.execute("DELETE FROM likes WHERE from_user = ? OR to_user = ?", 
                           (telegram_id, telegram_id))
                conn.execute("DELETE FROM matches WHERE user1 = ? OR user2 = ?", 
                           (telegram_id, telegram_id))
                
                # Очищаем профиль но оставляем пользователя
                conn.execute('''
                    UPDATE users SET 
                    name = NULL, nickname = NULL, age = NULL, 
                    rating = NULL, positions = NULL, additional_info = NULL, photo_id = NULL
                    WHERE telegram_id = ?
                ''', (telegram_id,))
            
            logger.info(f"Профиль удален: {telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления профиля: {e}")
            return False