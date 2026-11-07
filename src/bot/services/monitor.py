import asyncio
from datetime import UTC, datetime
from typing import Protocol

from bot.services.models import Book, MonitorResult, PriceChange
from bot.services.repository import PriceRepository


class BookSource(Protocol):
    async def parse(self, max_pages: int) -> list[Book]: ...


class EmptyCatalogueError(RuntimeError):
    """Raised when the parser returns no books, so existing data is not wiped."""


class PriceMonitorService:
    def __init__(
        self,
        *,
        source: BookSource,
        repository: PriceRepository,
        max_pages: int,
    ) -> None:
        self._source = source
        self._repository = repository
        self._max_pages = max_pages
        self._lock = asyncio.Lock()

    async def run_once(self) -> MonitorResult:
        async with self._lock:
            books = await self._source.parse(self._max_pages)
            if not books:
                raise EmptyCatalogueError("parser returned no books")

            previous_prices = await self._repository.get_current_prices()
            changes = tuple(
                PriceChange(book=book, old_price=previous_prices[book.url])
                for book in books
                if book.url in previous_prices and previous_prices[book.url] != book.price
            )
            new_books = tuple(book for book in books if book.url not in previous_prices)
            checked_at = datetime.now(UTC)

            await self._repository.save_snapshot(books, checked_at)

            return MonitorResult(
                checked=len(books),
                changes=changes,
                new_books=new_books,
                checked_at=checked_at,
            )
