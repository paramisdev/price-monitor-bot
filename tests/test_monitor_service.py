from decimal import Decimal
from pathlib import Path

import pytest

from bot.services.models import Book
from bot.services.monitor import EmptyCatalogueError, PriceMonitorService
from bot.services.report import format_report
from bot.services.repository import PriceRepository


class StubSource:
    def __init__(self, batches: list[list[Book]]) -> None:
        self._batches = batches

    async def parse(self, max_pages: int) -> list[Book]:
        assert max_pages == 5
        return self._batches.pop(0)


def make_book(url: str, price: str, title: str = "Test book") -> Book:
    return Book(
        url=url,
        title=title,
        price=Decimal(price),
        currency="GBP",
        availability="In stock",
        rating=4,
    )


async def test_monitor_detects_new_and_changed_books(tmp_path: Path) -> None:
    repository = PriceRepository(tmp_path / "prices.db")
    await repository.initialize()
    book = make_book("http://example.com/book", "10.00")
    source = StubSource(
        [
            [book],
            [book.model_copy(update={"price": Decimal("9.00")})],
        ]
    )
    service = PriceMonitorService(source=source, repository=repository, max_pages=5)

    first_result = await service.run_once()
    assert first_result.checked == 1
    assert first_result.new_books == (book,)
    assert first_result.changes == ()

    second_result = await service.run_once()
    assert second_result.new_books == ()
    assert len(second_result.changes) == 1
    assert second_result.changes[0].old_price == Decimal("10.00")
    assert second_result.changes[0].percent == Decimal("-10")

    report = format_report(second_result)
    assert "Подешевело" in report
    assert "£10.00 → <b>£9.00</b>" in report
    assert "−10.0%" in report


async def test_monitor_rejects_empty_catalogue(tmp_path: Path) -> None:
    repository = PriceRepository(tmp_path / "prices.db")
    await repository.initialize()
    service = PriceMonitorService(
        source=StubSource([[]]),
        repository=repository,
        max_pages=5,
    )

    with pytest.raises(EmptyCatalogueError):
        await service.run_once()


async def test_report_escapes_book_titles(tmp_path: Path) -> None:
    repository = PriceRepository(tmp_path / "prices.db")
    await repository.initialize()
    book = make_book("http://example.com/book", "10.00", title="<b>Book</b>")
    service = PriceMonitorService(
        source=StubSource([[book]]),
        repository=repository,
        max_pages=5,
    )

    result = await service.run_once()

    assert "&lt;b&gt;Book&lt;/b&gt;" in format_report(result)
    assert "<b>Book</b>" not in format_report(result)
