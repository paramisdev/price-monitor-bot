from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

FORBIDDEN_TEXT = "Доступ запрещён. Бот предназначен только для администратора."


class AdminOnlyMiddleware(BaseMiddleware):
    def __init__(self, admin_id: int) -> None:
        self._admin_id = admin_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id != self._admin_id:
            if isinstance(event, Message):
                await event.answer(FORBIDDEN_TEXT)
            elif isinstance(event, CallbackQuery):
                await event.answer(FORBIDDEN_TEXT, show_alert=True)
            return None

        return await handler(event, data)
