import html
from decimal import Decimal

from bot.services.models import Book, MonitorResult, PriceChange

CURRENCY_SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}
MAX_NEW_BOOKS_IN_REPORT = 5


def format_report(result: MonitorResult) -> str:
    decreased = [change for change in result.changes if change.delta < 0]
    increased = [change for change in result.changes if change.delta > 0]

    lines = [
        "📊 <b>Мониторинг цен</b>",
        f"Проверено книг: <b>{result.checked}</b>",
        f"Изменений: <b>{len(result.changes)}</b>",
        f"Новых позиций: <b>{len(result.new_books)}</b>",
        f"Время проверки: {result.checked_at:%d.%m.%Y %H:%M} UTC",
        "",
    ]

    if decreased:
        lines.append("<b>🔻 Подешевело</b>")
        lines.extend(_format_change(change) for change in decreased)
        lines.append("")

    if increased:
        lines.append("<b>🔺 Подорожало</b>")
        lines.extend(_format_change(change) for change in increased)
        lines.append("")

    if not result.changes:
        lines.append("Цены не изменились.")

    if result.new_books:
        lines.append("")
        lines.append("<b>🆕 Новые позиции</b>")
        lines.extend(_format_book(book) for book in result.new_books[:MAX_NEW_BOOKS_IN_REPORT])
        remaining = len(result.new_books) - MAX_NEW_BOOKS_IN_REPORT
        if remaining > 0:
            lines.append(f"…и ещё {remaining}.")

    return "\n".join(lines).strip()


def _format_change(change: PriceChange) -> str:
    book = change.book
    return (
        f'• <a href="{html.escape(book.url, quote=True)}">{html.escape(book.title)}</a>\n'
        f"  {_money(change.old_price, book.currency)} → "
        f"<b>{_money(book.price, book.currency)}</b> "
        f"({_signed_percent(change.percent)})"
    )


def _format_book(book: Book) -> str:
    return (
        f'• <a href="{html.escape(book.url, quote=True)}">{html.escape(book.title)}</a> — '
        f"{_money(book.price, book.currency)}"
    )


def _money(amount: Decimal, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    return f"{symbol}{amount:.2f}"


def _signed_percent(percent: Decimal) -> str:
    sign = "+" if percent > 0 else "−"
    return f"{sign}{abs(percent):.1f}%"
