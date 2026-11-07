from aiogram.filters.callback_data import CallbackData


class MonitorCallback(CallbackData, prefix="monitor"):
    action: str
