"""
Парсер zametr.pl через официальный JSON API.

Основной эндпоинт: POST /api/search/map/offer
Документировано путём анализа реального трафика браузера.
"""

import asyncio
import logging
import time
from typing import Optional

import aiohttp

from config import config

logger = logging.getLogger(__name__)

# Заголовки, имитирующие браузер
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://zametr.pl",
    "Referer": "https://zametr.pl/oferty/mieszkania/warszawa",
}

# Глобальный rate limiter: не более 1 запроса в N секунд
_rate_lock = asyncio.Lock()
_last_request_time: float = 0.0


async def _rate_limited_sleep() -> None:
    """Выдерживает паузу между запросами."""
    global _last_request_time
    async with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        delay = config.REQUEST_DELAY
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        _last_request_time = time.monotonic()


def _build_request_body(
    city: str,
    page_index: int = 1,
    for_map: bool = False,
    offer_type: str = "flat",
) -> dict:
    """Формирует тело POST-запроса к API."""
    return {
        "city": city,
        "isActive": True,
        "appendFeatured": True,
        "discountComboMin": None,
        "reductionsOnly": False,
        "forMap": for_map,
        "showAllOffersForList": False,
        "pageIndex": page_index,
        "offerSearch": {
            "marketType": None,
            "minArea": None,
            "maxArea": None,
            "minFloor": None,
            "maxFloor": None,
            "minPricePerArea": None,
            "maxPricePerArea": None,
            "minPrice": None,
            "maxPrice": None,
            "minRooms": None,
            "maxRooms": None,
            "minScoreValue": None,
            "maxScoreValue": None,
            "olderThan": None,
            "newerThan": None,
            "minDiscount": None,
            "maxDiscount": None,
            "maxDiscountCombo": None,
            "minTotalFloor": None,
            "maxTotalFloor": None,
            "minYearBuilt": None,
            "maxYearBuilt": None,
            "offerType": offer_type,
        },
        "sortBy": "date_desc",
    }


async def fetch_all_city_offers(
    city_slug: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> list[dict]:
    """
    Загрузить ВСЕ объявления города одним запросом (forMap=True).
    Возвращает список offer-словарей.
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession(headers=HEADERS)

    try:
        body = _build_request_body(city_slug, for_map=True)
        return await _post_with_retry(session, body, city_slug)
    finally:
        if own_session:
            await session.close()


async def fetch_city_offers_paged(
    city_slug: str,
    page_index: int = 1,
    session: Optional[aiohttp.ClientSession] = None,
) -> tuple[list[dict], int]:
    """
    Загрузить одну страницу объявлений (20 штук).
    Возвращает (offers, total_count).
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession(headers=HEADERS)

    try:
        body = _build_request_body(city_slug, page_index=page_index, for_map=False)
        offers = await _post_with_retry(session, body, city_slug)
        # total_count получим из первого запроса через другой метод
        return offers, len(offers)
    finally:
        if own_session:
            await session.close()


async def _post_with_retry(
    session: aiohttp.ClientSession,
    body: dict,
    city_slug: str,
) -> list[dict]:
    """POST с retry-логикой и rate limiting."""
    last_error: Exception | None = None

    for attempt in range(1, config.MAX_RETRIES + 1):
        await _rate_limited_sleep()
        try:
            async with session.post(
                config.API_ENDPOINT,
                json=body,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 429:
                    logger.warning(
                        "Rate limited (429) on city=%s attempt=%d", city_slug, attempt
                    )
                    await asyncio.sleep(5 * attempt)
                    continue

                if resp.status != 200:
                    logger.warning(
                        "Unexpected status %d on city=%s attempt=%d",
                        resp.status, city_slug, attempt,
                    )
                    await asyncio.sleep(2 * attempt)
                    continue

                data = await resp.json(content_type=None)
                offers = data.get("offers", [])
                total = data.get("totalCount", len(offers))
                logger.info(
                    "Fetched %d/%d offers for city=%s (attempt=%d)",
                    len(offers), total, city_slug, attempt,
                )
                return offers

        except aiohttp.ClientError as e:
            last_error = e
            logger.warning("Request error city=%s attempt=%d: %s", city_slug, attempt, e)
            await asyncio.sleep(2 * attempt)
        except Exception as e:
            last_error = e
            logger.error("Unexpected error city=%s attempt=%d: %s", city_slug, attempt, e)
            await asyncio.sleep(2 * attempt)

    raise RuntimeError(
        f"Не удалось получить данные для города '{city_slug}' "
        f"после {config.MAX_RETRIES} попыток. Последняя ошибка: {last_error}"
    )


def filter_by_street(
    offers: list[dict],
    street: str,
    building: Optional[str] = None,
) -> list[dict]:
    """
    Фильтрация списка объявлений по улице (и номеру дома).
    Поиск нечёткий: поиск подстроки без учёта регистра.
    """
    street_lower = street.strip().lower()
    result = []

    for offer in offers:
        location = offer.get("location", {})
        offer_street = (location.get("street") or "").lower()

        if not offer_street:
            continue

        # Нечёткий поиск: ищем ключевое слово улицы
        # Убираем общие слова-префиксы
        street_key = _strip_street_prefix(street_lower)
        offer_street_key = _strip_street_prefix(offer_street)

        if street_key not in offer_street_key and offer_street_key not in street_key:
            continue

        # Если задан номер дома — фильтруем по нему
        if building:
            # Номер дома может быть в path (slug) или в street
            offer_path = offer.get("path", "").lower()
            building_lower = building.strip().lower()
            if building_lower not in offer_path and building_lower not in offer_street:
                continue

        result.append(offer)

    return result


def _strip_street_prefix(name: str) -> str:
    """Убрать типовые префиксы улиц для нечёткого сравнения."""
    prefixes = ["ul.", "ul ", "ulica ", "aleja ", "al.", "al ", "os.", "os ", "plac ", "pl."]
    lower = name.lower().strip()
    for prefix in prefixes:
        if lower.startswith(prefix):
            return lower[len(prefix):].strip()
    return lower


def compute_street_analytics(offers: list[dict]) -> dict:
    """
    Вычислить аналитику по отфильтрованному списку объявлений (одна улица).
    """
    if not offers:
        return {}

    prices_per_area = [
        o["pricePerArea"]
        for o in offers
        if o.get("pricePerArea") and o["pricePerArea"] > 0
    ]
    total_prices = []
    for o in offers:
        discount = o.get("discount") or {}
        price = discount.get("newPrice") or discount.get("oldPrice")
        if price:
            total_prices.append(price)

    if not prices_per_area:
        return {}

    prices_per_area.sort()
    n = len(prices_per_area)
    median = prices_per_area[n // 2] if n % 2 else (prices_per_area[n // 2 - 1] + prices_per_area[n // 2]) / 2
    avg = sum(prices_per_area) / n

    # Тренд: сравниваем стартовую цену vs текущую
    price_changes = []
    for o in offers:
        discount = o.get("discount") or {}
        delta_pct = discount.get("priceDeltaPercentageFromStart")
        if delta_pct is not None:
            price_changes.append(delta_pct)

    if price_changes:
        avg_change = sum(price_changes) / len(price_changes)
        if avg_change > 2:
            trend = "📈 Растёт"
        elif avg_change < -2:
            trend = "📉 Падает"
        else:
            trend = "➡️ Стабильно"
    else:
        trend = "➡️ Стабильно"
        avg_change = 0

    return {
        "count": n,
        "min_price_per_area": round(min(prices_per_area)),
        "max_price_per_area": round(max(prices_per_area)),
        "avg_price_per_area": round(avg),
        "median_price_per_area": round(median),
        "avg_change_pct": round(avg_change, 1),
        "trend": trend,
        "total_prices": total_prices,
    }


def format_offer(offer: dict, is_realtor: bool = False) -> str:
    """
    Форматировать одно объявление в читаемый текст для Telegram.
    """
    location = offer.get("location") or {}
    discount = offer.get("discount") or {}
    history = offer.get("historyPrices") or []

    city = location.get("city") or "—"
    district = location.get("district") or ""
    street = location.get("street") or ""
    area = offer.get("area") or 0
    rooms = offer.get("numberOfRooms") or 0
    year_built = offer.get("yearBuilt")
    floor = offer.get("floor")
    floor_total = offer.get("floorTotal")
    price_per_area = offer.get("pricePerArea") or 0
    is_archived = offer.get("isArchived", False)

    current_price = discount.get("newPrice") or discount.get("oldPrice")
    old_price = discount.get("oldPrice")
    delta_pct = discount.get("priceDeltaPercentageFromStart")

    offer_id = offer.get("offerId", "")
    path = offer.get("path", "")
    link = f"https://zametr.pl/oferta/{offer_id}"

    # Адрес
    address_parts = [p for p in [city, district, street] if p]
    address = ", ".join(address_parts)

    status = "📦 Архив (продано/снято)" if is_archived else "🔄 Активное объявление"

    lines = [
        f"🏠 <b>{address or '—'}</b>",
        f"📍 {city}" + (f", {district}" if district else "") + (f", {street}" if street else ""),
    ]

    if current_price:
        lines.append(f"💰 Цена: <b>{current_price:,} PLN</b>" + (f" ({round(price_per_area):,} PLN/m²)" if price_per_area else ""))
        if old_price and old_price != current_price:
            lines.append(f"   ↘️ Старая цена: {old_price:,} PLN")

    if area:
        lines.append(f"📐 Площадь: {area} m²")
    if rooms:
        lines.append(f"🛏 Комнат: {rooms}")
    if year_built:
        lines.append(f"🏗 Год постройки: {year_built}")
    if floor is not None and floor_total:
        lines.append(f"🏢 Этаж: {floor} из {floor_total}")

    lines.append(f"📅 Статус: {status}")

    # Динамика цен
    if delta_pct is not None or history:
        lines.append("📈 <b>Динамика цен:</b>")
        if current_price:
            lines.append(f"   • Текущая цена: {current_price:,} PLN")
        if delta_pct is not None:
            sign = "+" if delta_pct > 0 else ""
            lines.append(f"   • Изменение с публикации: {sign}{delta_pct}%")
        if history:
            first = history[-1]  # самый старый
            first_price = first.get("oldPrice") or first.get("price")
            if first_price:
                lines.append(f"   • Стартовая цена: {first_price:,} PLN")

    lines.append(f"🔗 <a href='{link}'>Подробнее на zametr.pl</a>")

    if is_realtor:
        lines.append("\n📋 <b>Аналитика для риэлтора:</b>")
        construction_type = offer.get("constructionType") or "—"
        market = offer.get("market") or "—"
        lines.append(f"   • Тип рынка: {market}")
        lines.append(f"   • Тип строения: {construction_type}")
        if offer.get("isHot"):
            lines.append("   • 🔥 Горячая цена (несколько снижений подряд)")
        discount_combo = offer.get("discountCombo", 0)
        if discount_combo:
            lines.append(f"   • Снижений цены: {discount_combo}")

    return "\n".join(lines)
