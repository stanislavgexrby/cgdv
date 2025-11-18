from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
import logging

logger = logging.getLogger(__name__)

class StateRecoveryMiddleware(BaseMiddleware):
    """Middleware для автоматического восстановления потерянного state"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        state = data.get("state")
        db = data.get("db")
        
        if state and db and hasattr(event, "from_user"):
            user_id = event.from_user.id
            state_data = await state.get_data()
            
            should_recover = (
                not state_data or 
                (
                    'game' not in state_data and 
                    'profiles_shown' not in state_data and 
                    'current_index' not in state_data
                )
            )
            
            if should_recover:
                try:
                    user = await db.get_user(user_id)
                    if user:
                        await state.update_data(
                            user_id=user_id,
                            game=user['current_game']
                        )
                        logger.info(f"Восстановлен state для пользователя {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка восстановления state: {e}")
        
        return await handler(event, data)