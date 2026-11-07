from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bot.services.models import Book
from bot.services.repository import PriceRepository


def make_book(url: str, price: str, title: str = "Test book") -> Book:
    return Book(
        url=url,
        title=title,
        price=Decimal(price),
        currency="GBP",
        availability="In stock",
        rating=4,
    )


async def test_repository_saves_current_prices_and_history(tmp_path: Path) -> None:
    repository = PriceRepository(tmp_path / "data" / "prices.db")
    await repository.initialize()

    checked_at = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    book = make_book("http://example.com/book", "10.00")

    await repository.save_snapshot([book], checked_at)

    assert await repository.get_current_prices() == {book.url: Decimal("10.00")}
    assert await repository.get_current_books() == [book]
    assert await repository.get_history(book.url) == [(Decimal("10.00"), checked_at)]


async def test_repository_keeps_history_when_price_changes(tmp_path: Path) -> None:
    repository = PriceRepository(tmp_path / "prices.db")
    await repository.initialize()

    first_check = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    second_check = first_check + timedelta(hours=1)
    book = make_book("http://example.com/book", "10.00")

    await repository.save_snapshot([book], first_check)
    await repository.save_snapshot(
        [book.model_copy(update={"price": Decimal("8.50")})],
        second_check,
    )

    assert await repository.get_current_prices() == {book.url: Decimal("8.50")}
    assert await repository.get_history(book.url) == [
        (Decimal("8.50"), second_check),
        (Decimal("10.00"), first_check),
    ]


async def test_repository_rejects_invalid_history_limit(tmp_path: Path) -> None:
    repository = PriceRepository(tmp_path / "prices.db")
    await repository.initialize()

    with pytest.raises(ValueError):
        await repository.get_history("http://example.com/book", limit=0)
