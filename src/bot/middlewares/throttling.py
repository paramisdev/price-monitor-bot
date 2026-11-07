import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 1.0) -> None:
        self._rate_limit = rate_limit
        self._last_seen: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None:
            now = time.monotonic()
            last_seen = self._last_seen.get(user.id, 0.0)
            if now - last_seen < self._rate_limit:
                if isinstance(event, Message):
                    await event.answer("Слишком часто. Подождите немного.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("Слишком часто. Подождите немного.", show_alert=True)
                return None
            self._last_seen[user.id] = now

        return await handler(event, data)
