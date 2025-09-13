import hashlib
import logging
from typing import List, Dict, Optional
from database.pg_database import PostgreSQLDatabase
from cache.redis_cache import RedisCache

logger = logging.getLogger(__name__)

class Database:
    """Основной класс для работы с базой данных (PostgreSQL + Redis)"""
    
    def __init__(self):
        self._pg = PostgreSQLDatabase()
        self._cache = RedisCache()
        logger.info("Database инициализирована")
    
    async def init(self):
        """Инициализация подключений"""
        await self._pg.init()
        await self._cache.init()
        logger.info("✅ Database (PostgreSQL + Redis) готова")
    
    async def close(self):
        """Закрытие подключений"""
        await self._pg.close()
        await self._cache.close()
        logger.info("Database закрыта")
    
    def _generate_filters_hash(self, rating_filter, position_filter, region_filter) -> str:
        """Генерация хэша для фильтров поиска"""
        filters_str = f"{rating_filter or 'any'}_{position_filter or 'any'}_{region_filter or 'any'}"
        return hashlib.md5(filters_str.encode()).hexdigest()[:8]

    # === ПОЛЬЗОВАТЕЛИ (без кэша) ===
    
    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        return await self._pg.get_user(telegram_id)

    async def create_user(self, telegram_id: int, username: str, game: str) -> bool:
        result = await self._pg.create_user(telegram_id, username, game)
        if result:
            # Очищаем кэш пользователя
            await self._cache.clear_user_cache(telegram_id)
        return result

    async def switch_game(self, telegram_id: int, game: str) -> bool:
        result = await self._pg.switch_game(telegram_id, game)
        if result:
            # Очищаем кэш пользователя при переключении игры
            await self._cache.clear_user_cache(telegram_id)
        return result

    # === ПРОФИЛИ (с кэшем) ===
    
    async def get_user_profile(self, telegram_id: int, game: str) -> Optional[Dict]:
        # Сначала пробуем кэш
        cached_profile = await self._cache.get_profile(telegram_id, game)
        if cached_profile:
            return cached_profile
        
        # Если нет в кэше, берем из БД
        profile = await self._pg.get_user_profile(telegram_id, game)
        
        # Кэшируем результат
        if profile:
            await self._cache.set_profile(telegram_id, game, profile)
        
        return profile

    async def has_profile(self, telegram_id: int, game: str) -> bool:
        profile = await self.get_user_profile(telegram_id, game)
        return profile is not None

    async def update_user_profile(self, telegram_id: int, game: str, name: str, nickname: str,
                          age: int, rating: str, region: str, positions: List[str],
                          additional_info: str, photo_id: str = None) -> bool:
        
        result = await self._pg.update_user_profile(
            telegram_id, game, name, nickname, age, rating, region, 
            positions, additional_info, photo_id
        )
        
        if result:
            # Удаляем из кэша профиль, чтобы при следующем запросе загрузился обновленный
            await self._cache.delete_profile(telegram_id, game)
        
        return result

    async def delete_profile(self, telegram_id: int, game: str) -> bool:
        result = await self._pg.delete_profile(telegram_id, game)
        if result:
            # Очищаем весь кэш пользователя
            await self._cache.clear_user_cache(telegram_id)
        return result

    # === ПОИСК (с кэшем) ===
    
    async def get_potential_matches(self, user_id: int, game: str,
                            rating_filter: str = None,
                            position_filter: str = None,
                            region_filter: str = None,
                            limit: int = 10) -> List[Dict]:
        
        # Генерируем хэш фильтров для кэша
        filters_hash = self._generate_filters_hash(rating_filter, position_filter, region_filter)
        
        # Проверяем кэш
        cached_results = await self._cache.get_search_results(user_id, game, filters_hash)
        if cached_results:
            return cached_results
        
        # Если нет в кэше, ищем в БД
        results = await self._pg.get_potential_matches(
            user_id, game, rating_filter, position_filter, region_filter, limit
        )
        
        # Кэшируем результат
        if results:
            await self._cache.set_search_results(user_id, game, filters_hash, results)
        
        return results

    async def add_search_skip(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        return await self._pg.add_search_skip(user_id, skipped_user_id, game)

    # === ЛАЙКИ И МАТЧИ (без кэша - должны быть актуальными) ===
    
    async def add_like(self, from_user: int, to_user: int, game: str) -> bool:
        """Возвращает True если это матч"""
        result = await self._pg.add_like(from_user, to_user, game)
        
        if result:  # Если создался матч
            # Очищаем кэш обоих пользователей
            await self._cache.clear_user_cache(from_user)
            await self._cache.clear_user_cache(to_user)
        
        return result

    async def get_likes_for_user(self, user_id: int, game: str) -> List[Dict]:
        return await self._pg.get_likes_for_user(user_id, game)

    async def get_matches(self, user_id: int, game: str) -> List[Dict]:
        return await self._pg.get_matches(user_id, game)

    async def skip_like(self, user_id: int, skipped_user_id: int, game: str) -> bool:
        return await self._pg.skip_like(user_id, skipped_user_id, game)

    # === БАНЫ (без кэша) ===
    
    async def is_user_banned(self, user_id: int) -> bool:
        return await self._pg.is_user_banned(user_id)

    async def get_user_ban(self, user_id: int) -> Optional[Dict]:
        return await self._pg.get_user_ban(user_id)

    async def get_all_bans(self) -> List[Dict]:
        return await self._pg.get_all_bans()

    async def add_ban(self, user_id: int, reason: str, duration_days: int = 7) -> bool:
        result = await self._pg.add_ban(user_id, reason, duration_days)
        if result:
            # Очищаем кэш забаненного пользователя
            await self._cache.clear_user_cache(user_id)
        return result

    async def unban_user(self, user_id: int) -> bool:
        result = await self._pg.unban_user(user_id)
        if result:
            # Очищаем кэш разбаненного пользователя
            await self._cache.clear_user_cache(user_id)
        return result

    # === ЖАЛОБЫ (без кэша) ===
    
    async def add_report(self, reporter_id: int, reported_user_id: int, game: str) -> bool:
        return await self._pg.add_report(reporter_id, reported_user_id, game)

    async def get_pending_reports(self) -> List[Dict]:
        return await self._pg.get_pending_reports()

    async def get_report_info(self, report_id: int) -> Optional[Dict]:
        return await self._pg.get_report_info(report_id)

    async def process_report(self, report_id: int, action: str, admin_id: int) -> bool:
        return await self._pg.process_report(report_id, action, admin_id)

    # === ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ ===
    
    async def check_subscription_cached(self, user_id: int, game: str, is_subscribed: bool) -> bool:
        """Кэширование проверки подписки"""
        # Сначала проверяем кэш
        cached_result = await self._cache.get_subscription(user_id, game)
        if cached_result is not None:
            return cached_result
        
        # Если нет в кэше, кэшируем переданный результат
        await self._cache.set_subscription(user_id, game, is_subscribed)
        return is_subscribed