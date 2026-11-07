from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from bot.services.models import Book
from bot.services.parser import BookParser, parse_price

FIXTURES = Path(__file__).parent / "fixtures"
START_URL = "http://books.toscrape.com/catalogue/page-1.html"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


async def test_parser_reads_books_and_follows_pagination() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path.endswith("page-1.html"):
            return httpx.Response(200, text=_read_fixture("catalogue_page_1.html"))
        if request.url.path.endswith("page-2.html"):
            return httpx.Response(200, text=_read_fixture("catalogue_page_2.html"))
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = BookParser(client=client, start_url=START_URL)
        books = await parser.parse(max_pages=5)

    assert len(books) == 3
    assert requested_urls == [
        START_URL,
        "http://books.toscrape.com/catalogue/page-2.html",
    ]

    first = books[0]
    assert first.title == "A Light in the Attic"
    assert first.price == Decimal("51.77")
    assert first.currency == "GBP"
    assert first.rating == 3
    assert first.availability == "In stock"
    assert first.url == ("http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html")


async def test_parser_stops_at_max_pages() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, text=_read_fixture("catalogue_page_1.html"))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        parser = BookParser(client=client, start_url=START_URL)
        books = await parser.parse(max_pages=1)

    assert len(books) == 2
    assert requested_urls == [START_URL]


def test_parse_price_supports_common_formats() -> None:
    assert parse_price("£51.77") == (Decimal("51.77"), "GBP")
    assert parse_price("$1,234.50") == (Decimal("1234.50"), "USD")
    assert parse_price("€12,50") == (Decimal("12.50"), "EUR")


def test_parse_price_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        parse_price("free")


def test_book_rejects_invalid_url() -> None:
    with pytest.raises(ValidationError):
        Book(
            url="not-a-url",
            title="Book",
            price=Decimal("10.00"),
            availability="In stock",
        )
