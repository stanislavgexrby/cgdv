import redis.asyncio as redis
import json
import os
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self):
        self._redis = None
        
    async def init(self):
        """Инициализация Redis"""
        redis_url = f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}/{os.getenv('REDIS_DB', 0)}"
        
        self._redis = redis.from_url(redis_url, decode_responses=True)
        await self._redis.ping()
        logger.info("✅ Redis подключен")

    async def close(self):
        """Закрытие соединения"""
        if self._redis:
            await self._redis.close()

    # === КЭШИРОВАНИЕ ПРОФИЛЕЙ ===
    
    async def get_profile(self, user_id: int, game: str) -> Optional[Dict]:
        """Получение профиля из кэша"""
        try:
            key = f"profile:{user_id}:{game}"
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Ошибка чтения профиля из кэша: {e}")
        return None

    async def set_profile(self, user_id: int, game: str, profile: Dict, ttl: int = 600):
        """Сохранение профиля в кэш на 10 минут"""
        try:
            key = f"profile:{user_id}:{game}"
            await self._redis.setex(key, ttl, json.dumps(profile, default=str))
        except Exception as e:
            logger.error(f"Ошибка сохранения профиля в кэш: {e}")

    async def delete_profile(self, user_id: int, game: str):
        """Удаление профиля из кэша"""
        try:
            key = f"profile:{user_id}:{game}"
            await self._redis.delete(key)
        except Exception as e:
            logger.error(f"Ошибка удаления профиля из кэша: {e}")

    # === КЭШИРОВАНИЕ ПОИСКА ===
    
    async def get_search_results(self, user_id: int, game: str, filters_hash: str) -> Optional[List[Dict]]:
        """Получение результатов поиска из кэша"""
        try:
            key = f"search:{user_id}:{game}:{filters_hash}"
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Ошибка чтения поиска из кэша: {e}")
        return None

    async def set_search_results(self, user_id: int, game: str, filters_hash: str, results: List[Dict], ttl: int = 300):
        """Сохранение результатов поиска в кэш на 5 минут"""
        try:
            key = f"search:{user_id}:{game}:{filters_hash}"
            await self._redis.setex(key, ttl, json.dumps(results, default=str))
        except Exception as e:
            logger.error(f"Ошибка сохранения поиска в кэш: {e}")

    # === КЭШИРОВАНИЕ ПРОВЕРОК ПОДПИСКИ ===
    
    async def get_subscription(self, user_id: int, game: str) -> Optional[bool]:
        """Получение статуса подписки из кэша"""
        try:
            key = f"subscription:{user_id}:{game}"
            data = await self._redis.get(key)
            if data is not None:
                return data == "1"
        except Exception as e:
            logger.error(f"Ошибка чтения подписки из кэша: {e}")
        return None

    async def set_subscription(self, user_id: int, game: str, is_subscribed: bool, ttl: int = 300):
        """Сохранение статуса подписки в кэш на 5 минут"""
        try:
            key = f"subscription:{user_id}:{game}"
            await self._redis.setex(key, ttl, "1" if is_subscribed else "0")
        except Exception as e:
            logger.error(f"Ошибка сохранения подписки в кэш: {e}")

    # === ОЧИСТКА КЭША ===
    
    async def clear_user_cache(self, user_id: int):
        """Очистка всего кэша пользователя"""
        try:
            patterns = [
                f"profile:{user_id}:*",
                f"subscription:{user_id}:*", 
                f"search:{user_id}:*"
            ]
            
            for pattern in patterns:
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"Ошибка очистки кэша пользователя: {e}")

    # === FSM STORAGE ДЛЯ AIOGRAM ===
    
    async def get_state(self, chat_id: int, user_id: int) -> Optional[str]:
        """Получение FSM состояния"""
        try:
            key = f"fsm:state:{chat_id}:{user_id}"
            return await self._redis.get(key)
        except Exception as e:
            logger.error(f"Ошибка чтения FSM состояния: {e}")
            return None

    async def set_state(self, chat_id: int, user_id: int, state: str, ttl: int = 3600):
        """Установка FSM состояния"""
        try:
            key = f"fsm:state:{chat_id}:{user_id}"
            if state:
                await self._redis.setex(key, ttl, state)
            else:
                await self._redis.delete(key)
        except Exception as e:
            logger.error(f"Ошибка установки FSM состояния: {e}")

    async def get_data(self, chat_id: int, user_id: int) -> Dict:
        """Получение FSM данных"""
        try:
            key = f"fsm:data:{chat_id}:{user_id}"
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
            return {}
        except Exception as e:
            logger.error(f"Ошибка чтения FSM данных: {e}")
            return {}

    async def set_data(self, chat_id: int, user_id: int, data: Dict, ttl: int = 3600):
        """Установка FSM данных"""
        try:
            key = f"fsm:data:{chat_id}:{user_id}"
            if data:
                await self._redis.setex(key, ttl, json.dumps(data, default=str))
            else:
                await self._redis.delete(key)
        except Exception as e:
            logger.error(f"Ошибка установки FSM данных: {e}")

    async def update_data(self, chat_id: int, user_id: int, data: Dict) -> Dict:
        """Обновление FSM данных"""
        try:
            current_data = await self.get_data(chat_id, user_id)
            current_data.update(data)
            await self.set_data(chat_id, user_id, current_data)
            return current_data.copy()
        except Exception as e:
            logger.error(f"Ошибка обновления FSM данных: {e}")
            return {}

    async def clear_state(self, chat_id: int, user_id: int):
        """Очистка FSM состояния и данных"""
        try:
            keys = [
                f"fsm:state:{chat_id}:{user_id}",
                f"fsm:data:{chat_id}:{user_id}"
            ]
            await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"Ошибка очистки FSM: {e}")