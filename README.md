# price-monitor-bot

Telegram-бот на aiogram 3 для мониторинга цен в каталоге
[books.toscrape.com](http://books.toscrape.com/). Бот собирает карточки книг,
сохраняет историю цен в SQLite и присылает администратору отчёт об изменениях.

Проект сделан как портфолио-демонстрация: парсинг, валидация данных, асинхронная
БД, фоновая задача и аккуратный Telegram-отчёт.

## Что умеет

- Обходит каталог с пагинацией и ограничением `MAX_PAGES`.
- Парсит название, цену, валюту, рейтинг и наличие через `httpx` + `BeautifulSoup`.
- Валидирует каждую карточку Pydantic-моделью `Book`.
- Хранит текущее состояние и полную историю наблюдений в SQLite (`aiosqlite`).
- Сравнивает новую цену с предыдущей и формирует HTML-отчёт:
  - подешевевшие книги;
  - подорожавшие книги;
  - новые позиции;
  - процент изменения.
- Присылает отчёт по расписанию, если есть изменения или новые книги.
- Позволяет запустить проверку вручную командой `/check`.
- Ограничивает доступ администратором и защищает от частых запросов.

## Стек

- Python 3.11+
- aiogram 3.x
- httpx
- BeautifulSoup4
- Pydantic 2 + pydantic-settings
- aiosqlite
- uv, ruff, mypy, pytest

## Структура

```text
src/bot/
├── __main__.py          # python -m bot
├── main.py              # Bot, Dispatcher, polling, фоновая проверка
├── config.py            # настройки из .env, SecretStr
├── callbacks/           # typed CallbackData
├── handlers/            # команды и обработка кнопки
├── keyboards/           # inline-клавиатура отчёта
├── middlewares/         # admin-only и throttling
└── services/
    ├── models.py        # Book, PriceChange, MonitorResult
    ├── parser.py        # httpx + BeautifulSoup + Pydantic
    ├── repository.py    # SQLite: текущие цены и история
    ├── monitor.py       # сценарий проверки и сравнение цен
    └── report.py        # формирование HTML-отчёта
tests/
├── fixtures/            # HTML-страницы каталога
├── test_parser.py
├── test_repository.py
└── test_monitor_service.py
```

## Как работает парсинг

1. `BookParser` загружает `http://books.toscrape.com/catalogue/page-1.html`.
2. Ищет карточки `article.product_pod`.
3. Для каждой карточки достаёт ссылку, название, цену, наличие и рейтинг.
4. `parse_price()` превращает строку вида `£51.77` в `Decimal("51.77")` и ISO-код валюты.
5. Pydantic проверяет URL, положительную цену, валюту и рейтинг.
6. Если на странице есть `li.next a`, парсер переходит на следующую страницу,
   пока не достигнет `MAX_PAGES`.
7. Битые карточки пропускаются с записью в лог, а не роняют всю проверку.

Сайт используется как стабильный учебный каталог. Логика парсера легко переносится
на другой интернет-магазин заменой CSS-селекторов.

## Хранение данных

SQLite-файл по умолчанию: `data/prices.db`.

```sql
books (
    url TEXT PRIMARY KEY,
    title TEXT,
    currency TEXT,
    current_price TEXT,
    availability TEXT,
    rating INTEGER,
    updated_at TEXT
)

price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_url TEXT REFERENCES books(url),
    price TEXT,
    recorded_at TEXT
)
```

Цены хранятся в `TEXT` и преобразуются в `Decimal`, чтобы не терять точность.
При каждом наблюдении добавляется запись в `price_history`; текущая цена
обновляется через `UPSERT`.

## Запуск

```bash
git clone https://github.com/paramisdev/price-monitor-bot.git
cd price-monitor-bot
uv sync --locked
```

Создайте `.env`:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Заполните `BOT_TOKEN` и `ADMIN_CHAT_ID`, затем запустите:

```bash
uv run python -m bot
```

`ADMIN_CHAT_ID` — это ID пользователя, которому разрешён доступ к боту и который
получает отчёты. Узнать свой ID можно через [@userinfobot](https://t.me/userinfobot).

## Настройки

| Переменная | Обязательна | По умолчанию | Описание |
| --- | --- | --- | --- |
| `BOT_TOKEN` | да | — | Токен от [@BotFather](https://t.me/BotFather) |
| `ADMIN_CHAT_ID` | да | — | ID администратора |
| `DATABASE_PATH` | нет | `data/prices.db` | Путь к SQLite-файлу |
| `BOOKS_URL` | нет | `http://books.toscrape.com/catalogue/page-1.html` | Стартовая страница каталога |
| `MAX_PAGES` | нет | `5` | Максимум страниц за одну проверку |
| `CHECK_INTERVAL_MINUTES` | нет | `60` | Интервал фоновой проверки |
| `REQUEST_TIMEOUT_SECONDS` | нет | `20` | Таймаут HTTP-запроса |
| `LOG_LEVEL` | нет | `INFO` | Уровень логирования |

## Команды

- `/start` — краткая инструкция.
- `/help` — помощь.
- `/check` — проверить цены прямо сейчас.

После отчёта доступна кнопка «Проверить снова» (typed `CallbackData`).

## Quality Gates

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src/bot
uv run pytest -q
```

Тесты не ходят в сеть: парсер проверяется на локальных HTML-фикстурах через
`httpx.MockTransport`, база — на временном SQLite-файле.

## Ограничения

- Каталог books.toscrape.com статический, поэтому в реальной эксплуатации
  селекторы нужно адаптировать под конкретный магазин.
- Расписание работает внутри процесса бота; при нескольких репликах нужен
  внешний планировщик.
- SQLite подходит для одного процесса. Для нескольких воркеров лучше PostgreSQL.
