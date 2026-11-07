from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import aiosqlite

from bot.services.models import Book

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    currency TEXT NOT NULL,
    current_price TEXT NOT NULL,
    availability TEXT NOT NULL,
    rating INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_url TEXT NOT NULL,
    price TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (book_url) REFERENCES books(url) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_price_history_book
    ON price_history (book_url, recorded_at DESC);
"""

UPSERT_BOOK = """
INSERT INTO books (url, title, currency, current_price, availability, rating, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(url) DO UPDATE SET
    title = excluded.title,
    currency = excluded.currency,
    current_price = excluded.current_price,
    availability = excluded.availability,
    rating = excluded.rating,
    updated_at = excluded.updated_at
"""

INSERT_HISTORY = """
INSERT INTO price_history (book_url, price, recorded_at)
VALUES (?, ?, ?)
"""


class PriceRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._connect() as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def get_current_prices(self) -> dict[str, Decimal]:
        async with self._connect() as db:
            cursor = await db.execute("SELECT url, current_price FROM books")
            rows = await cursor.fetchall()
            return {str(row[0]): Decimal(str(row[1])) for row in rows}

    async def get_current_books(self) -> list[Book]:
        async with self._connect() as db:
            cursor = await db.execute(
                "SELECT url, title, current_price, currency, availability, rating FROM books"
            )
            rows = await cursor.fetchall()

        return [
            Book(
                url=str(row[0]),
                title=str(row[1]),
                price=Decimal(str(row[2])),
                currency=str(row[3]),
                availability=str(row[4]),
                rating=int(row[5]),
            )
            for row in rows
        ]

    async def save_snapshot(self, books: Sequence[Book], checked_at: datetime) -> None:
        if not books:
            return

        timestamp = checked_at.isoformat()
        book_rows = [
            (
                book.url,
                book.title,
                book.currency,
                str(book.price),
                book.availability,
                book.rating,
                timestamp,
            )
            for book in books
        ]
        history_rows = [(book.url, str(book.price), timestamp) for book in books]

        async with self._connect() as db:
            await db.executemany(UPSERT_BOOK, book_rows)
            await db.executemany(INSERT_HISTORY, history_rows)
            await db.commit()

    async def get_history(
        self,
        book_url: str,
        *,
        limit: int = 50,
    ) -> list[tuple[Decimal, datetime]]:
        if limit < 1:
            raise ValueError("limit must be at least 1")

        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT price, recorded_at
                FROM price_history
                WHERE book_url = ?
                ORDER BY recorded_at DESC, id DESC
                LIMIT ?
                """,
                (book_url, limit),
            )
            rows = await cursor.fetchall()

        return [(Decimal(str(row[0])), datetime.fromisoformat(str(row[1]))) for row in rows]

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        db = await aiosqlite.connect(self._db_path)
        try:
            await db.execute("PRAGMA foreign_keys = ON")
            yield db
        finally:
            await db.close()
