import asyncio
import logging
from contextlib import suppress

import httpx
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import Settings
from bot.handlers import common, monitor
from bot.keyboards.monitor import report_keyboard
from bot.middlewares.admin import AdminOnlyMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.services.monitor import PriceMonitorService
from bot.services.parser import BookParser
from bot.services.report import format_report
from bot.services.repository import PriceRepository

logger = logging.getLogger(__name__)


async def _monitor_loop(
    *,
    service: PriceMonitorService,
    bot: Bot,
    admin_chat_id: int,
    interval_seconds: int,
) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            result = await service.run_once()
        except Exception:
            logger.exception("Scheduled price check failed")
            with suppress(Exception):
                await bot.send_message(
                    chat_id=admin_chat_id,
                    text="Не удалось выполнить плановую проверку цен. Подробности в логах.",
                )
            continue

        if not result.changes and not result.new_books:
            logger.info("Scheduled check finished without changes")
            continue

        try:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=format_report(result),
                reply_markup=report_keyboard(),
            )
        except Exception:
            logger.exception("Failed to send scheduled report")


async def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    repository = PriceRepository(settings.database_path)
    await repository.initialize()

    client = httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
    )
    parser = BookParser(client=client, start_url=settings.books_url)
    monitor_service = PriceMonitorService(
        source=parser,
        repository=repository,
        max_pages=settings.max_pages,
    )

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher["monitor_service"] = monitor_service

    dispatcher.message.middleware(AdminOnlyMiddleware(settings.admin_chat_id))
    dispatcher.callback_query.middleware(AdminOnlyMiddleware(settings.admin_chat_id))
    dispatcher.message.middleware(ThrottlingMiddleware())
    dispatcher.callback_query.middleware(ThrottlingMiddleware())

    dispatcher.include_router(common.router)
    dispatcher.include_router(monitor.router)

    background_task = asyncio.create_task(
        _monitor_loop(
            service=monitor_service,
            bot=bot,
            admin_chat_id=settings.admin_chat_id,
            interval_seconds=settings.check_interval_minutes * 60,
        )
    )

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        background_task.cancel()
        with suppress(asyncio.CancelledError):
            await background_task
        await client.aclose()
        await bot.session.close()


def run() -> None:
    asyncio.run(main())
