import logging

import aiosqlite
import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.callbacks.monitor import MonitorCallback
from bot.keyboards.monitor import report_keyboard
from bot.services.monitor import EmptyCatalogueError, PriceMonitorService
from bot.services.report import format_report

logger = logging.getLogger(__name__)

router = Router(name="monitor")


async def _run_check(message: Message, service: PriceMonitorService) -> None:
    status_message = await message.answer("Проверяю цены…")

    try:
        result = await service.run_once()
    except (EmptyCatalogueError, httpx.HTTPError, aiosqlite.Error, ValueError):
        logger.exception("Price check failed")
        await status_message.edit_text(
            "Не удалось получить цены. Проверьте логи и попробуйте ещё раз."
        )
        return

    await status_message.edit_text(
        format_report(result),
        reply_markup=report_keyboard(),
    )


@router.message(Command("check"))
async def cmd_check(message: Message, monitor_service: PriceMonitorService) -> None:
    await _run_check(message, monitor_service)


@router.callback_query(MonitorCallback.filter(F.action == "check"))
async def callback_check(
    callback: CallbackQuery,
    monitor_service: PriceMonitorService,
) -> None:
    await callback.answer("Запускаю проверку…")
    if isinstance(callback.message, Message):
        await _run_check(callback.message, monitor_service)
