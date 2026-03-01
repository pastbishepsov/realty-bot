# ZametrBot — Telegram-бот для поиска недвижимости в Польше

Бот для риэлторов и покупателей, который ищет и анализирует недвижимость по данным [zametr.pl](https://zametr.pl).

## Возможности

- 🔍 Поиск объявлений по городу и улице (с опциональным номером дома)
- 💰 История цен и динамика по каждому объявлению
- 📊 Аналитика улицы для риэлторов (медиана, диапазон, тренд, гистограмма)
- 🏙 60 городов Польши с пагинацией
- 💾 Кеш SQLite на 12 часов + автообновление раз в 6 часов
- 👤 Профили пользователей (риэлтор / частное лицо)
- 🏢 Для риэлторов: расширенная аналитика и детали по каждой сделке

## Технический стек

- **Python 3.11–3.13** (Python 3.14 пока не поддерживается pydantic-core)
- **aiogram 3.x** — async Telegram bot framework
- **aiohttp** — HTTP-клиент для парсинга API
- **aiosqlite** — асинхронный SQLite
- **APScheduler** — планировщик фоновых задач
- **zametr.pl JSON API** — `POST /api/search/map/offer` (без Cloudflare, открытый)

## Установка

### 1. Клонировать / скачать проект

```bash
cd realty_bot
```

### 2. Создать виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```env
BOT_TOKEN=1234567890:ABCDEFghijklmnop...   # токен от @BotFather
DB_PATH=realty_bot.db
CACHE_TTL_HOURS=12
SCHEDULER_INTERVAL_HOURS=6
REQUEST_DELAY=2.0
MAX_RETRIES=3
```

### 5. Получить токен бота

1. Откройте Telegram, найдите [@BotFather](https://t.me/BotFather)
2. Выполните команду `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен в `.env`

### 6. Запустить бота

```bash
python bot.py
```

## Структура проекта

```
realty_bot/
├── bot.py                  # Точка входа
├── config.py               # Конфигурация из .env
├── scheduler.py            # Фоновое обновление кеша (APScheduler)
├── database/
│   ├── db.py               # Функции работы с БД
│   └── models.py           # SQL DDL (CREATE TABLE)
├── parsers/
│   ├── zametr_parser.py    # API-клиент zametr.pl + фильтрация + форматирование
│   └── cities.py           # 60 городов Польши со slug-ами
├── handlers/
│   ├── start.py            # /start, онбординг, профиль
│   ├── filters.py          # /filters — выбор города по умолчанию
│   ├── search.py           # FSM-поиск: город → улица → дом
│   └── results.py          # Отображение результатов + аналитика улицы
├── keyboards/
│   └── inline.py           # Все inline-клавиатуры
├── requirements.txt
├── .env.example
└── README.md
```

## Как работает парсинг

Сайт zametr.pl использует Next.js с открытым JSON API:

```
POST https://zametr.pl/api/search/map/offer
Content-Type: application/json

{
  "city": "warszawa",
  "forMap": true,        // вернуть ВСЕ объявления за один запрос
  "isActive": true,
  ...
}
```

- **Нет Cloudflare / CAPTCHA** — `robots.txt` полностью открыт
- Фильтрация по улице выполняется на стороне клиента (API не поддерживает)
- `forMap: true` — весь каталог города в одном запросе (~3000–4000 объявлений для Варшавы)
- Rate limiting: 1 запрос в 2 секунды

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Регистрация и онбординг |
| `/filters` | Выбор города по умолчанию |

Все остальные действия — через inline-кнопки.

## Логи

Логи пишутся в файл `bot.log` и в консоль.

## Troubleshooting

**Бот не отвечает**: проверьте `BOT_TOKEN` в `.env`

**Ошибка при парсинге**: сайт может быть временно недоступен — бот сообщит об этом пользователю

**Нет результатов по улице**: попробуйте часть названия улицы (без "ul.", "aleja" и т.д.)

**Кеш устарел**: через 12 часов кеш обновится автоматически, или перезапустите бота
