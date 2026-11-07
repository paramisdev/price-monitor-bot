import logging
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError

from bot.services.models import Book

logger = logging.getLogger(__name__)

DEFAULT_CATALOGUE_URL = "http://books.toscrape.com/catalogue/page-1.html"
CURRENCY_BY_SYMBOL = {"£": "GBP", "$": "USD", "€": "EUR"}
RATING_BY_WORD = {
    "Zero": 0,
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}
PRICE_PATTERN = re.compile(r"([£$€])\s*([0-9][0-9.,]*)")


def parse_price(raw: str) -> tuple[Decimal, str]:
    """Parse a listing price such as ``£51.77`` into a decimal and ISO currency."""
    match = PRICE_PATTERN.search(raw.replace("\xa0", " "))
    if match is None:
        raise ValueError(f"unsupported price: {raw!r}")

    symbol, amount = match.groups()
    normalized = amount.replace(",", "") if "." in amount else amount.replace(",", ".")

    try:
        price = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"invalid price: {raw!r}") from exc

    if price <= 0:
        raise ValueError(f"price must be positive: {raw!r}")
    return price, CURRENCY_BY_SYMBOL[symbol]


class BookParser:
    """Async parser for the books.toscrape.com catalogue."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        start_url: str = DEFAULT_CATALOGUE_URL,
    ) -> None:
        self._client = client
        self._start_url = start_url

    async def parse(self, max_pages: int) -> list[Book]:
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")

        books_by_url: dict[str, Book] = {}
        visited: set[str] = set()
        page_url: str | None = self._start_url
        pages_parsed = 0

        while page_url is not None and pages_parsed < max_pages and page_url not in visited:
            visited.add(page_url)
            response = await self._client.get(page_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            for card in soup.select("article.product_pod"):
                book = self._parse_card(card, page_url)
                if book is not None:
                    books_by_url.setdefault(book.url, book)

            pages_parsed += 1
            page_url = self._next_page(soup, page_url)

        logger.info("Parsed %d books from %d page(s)", len(books_by_url), pages_parsed)
        return list(books_by_url.values())

    def _parse_card(self, card: Tag, page_url: str) -> Book | None:
        link = card.select_one("h3 a")
        price_element = card.select_one(".price_color")
        availability_element = card.select_one(".availability")
        rating_element = card.select_one(".star-rating")

        if link is None or price_element is None or availability_element is None:
            logger.warning("Skipping malformed product card on %s", page_url)
            return None

        href = link.get("href")
        if not isinstance(href, str) or not href:
            logger.warning("Skipping product without link on %s", page_url)
            return None

        title_attribute = link.get("title")
        title = (
            title_attribute
            if isinstance(title_attribute, str) and title_attribute.strip()
            else link.get_text(" ", strip=True)
        )

        try:
            price, currency = parse_price(price_element.get_text(" ", strip=True))
            rating = self._parse_rating(rating_element)
            return Book(
                url=urljoin(page_url, href),
                title=title,
                price=price,
                currency=currency,
                availability=availability_element.get_text(" ", strip=True),
                rating=rating,
            )
        except (ValueError, ValidationError):
            logger.warning("Skipping invalid product card on %s", page_url, exc_info=True)
            return None

    @staticmethod
    def _parse_rating(rating_element: Tag | None) -> int:
        if rating_element is None:
            return 0

        classes = rating_element.get("class")
        if not isinstance(classes, list):
            return 0

        return next(
            (RATING_BY_WORD[value] for value in classes if value in RATING_BY_WORD),
            0,
        )

    @staticmethod
    def _next_page(soup: BeautifulSoup, current_url: str) -> str | None:
        next_link = soup.select_one("li.next a")
        if next_link is None:
            return None

        href = next_link.get("href")
        if not isinstance(href, str) or not href:
            return None
        return urljoin(current_url, href)
