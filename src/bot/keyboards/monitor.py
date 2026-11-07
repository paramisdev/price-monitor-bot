from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks.monitor import MonitorCallback


def report_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Проверить снова",
                    callback_data=MonitorCallback(action="check").pack(),
                )
            ]
        ]
    )
