from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from handlers.notifications import update_user_activity
import logging

logger = logging.getLogger(__name__)

class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, database_instance):
        self.database = database_instance

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data['db'] = self.database
        
        try:
            user_id = None
            if hasattr(event, 'from_user') and event.from_user:
                user_id = event.from_user.id
            elif hasattr(event, 'message') and event.message and hasattr(event.message, 'from_user'):
                user_id = event.message.from_user.id
            
            if user_id:
                await update_user_activity(user_id, db=self.database)
                
        except Exception as e:
            logger.warning(f"Ошибка отслеживания активности: {e}")
        
        return await handler(event, data)