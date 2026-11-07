from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router(name="common")

HELP_TEXT = (
    "<b>Мониторинг цен книг</b>\n\n"
    "Бот периодически проверяет каталог books.toscrape.com и присылает отчёт, "
    "если цены изменились.\n\n"
    "<b>Команды:</b>\n"
    "/check — проверить цены прямо сейчас\n"
    "/help — показать это сообщение"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
