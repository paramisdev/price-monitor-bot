from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Book(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    title: str = Field(min_length=1)
    price: Decimal = Field(gt=0)
    currency: str = Field(default="GBP", min_length=3, max_length=3)
    availability: str = Field(min_length=1)
    rating: int = Field(default=0, ge=0, le=5)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


@dataclass(frozen=True, slots=True)
class PriceChange:
    book: Book
    old_price: Decimal

    @property
    def delta(self) -> Decimal:
        return self.book.price - self.old_price

    @property
    def percent(self) -> Decimal:
        if self.old_price == 0:
            return Decimal(0)
        return self.delta / self.old_price * Decimal(100)


@dataclass(frozen=True, slots=True)
class MonitorResult:
    checked: int
    changes: tuple[PriceChange, ...]
    new_books: tuple[Book, ...]
    checked_at: datetime
