"""
Фоновое обновление кеша через APScheduler.
"""

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import config
from database.db import get_all_cached_cities, save_listings
from parsers.zametr_parser import fetch_all_city_offers

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)

# Топ-10 городов для прогрева кеша при первом запуске
WARMUP_CITIES = [
    "warszawa",
    "krakow",
    "wroclaw",
    "poznan",
    "gdansk",
    "lodz",
    "katowice",
    "gdynia",
    "szczecin",
    "bialystok",
]


async def refresh_cached_cities() -> None:
    """Обновить кеш для всех городов, которые уже кешированы."""
    cities = await get_all_cached_cities()
    if not cities:
        logger.info("No cities cached yet, skipping refresh")
        return

    logger.info("Starting cache refresh for %d cities: %s", len(cities), cities)
    for city_slug in cities:
        try:
            offers = await fetch_all_city_offers(city_slug)
            if offers:
                await save_listings(city_slug, offers)
                logger.info("Refreshed cache: city=%s, count=%d", city_slug, len(offers))
        except Exception as e:
            logger.error("Failed to refresh cache for city=%s: %s", city_slug, e)


async def warmup_popular_cities() -> None:
    """Прогрев кеша для популярных городов при старте."""
    logger.info("Starting cache warmup for popular cities")
    for city_slug in WARMUP_CITIES:
        try:
            offers = await fetch_all_city_offers(city_slug)
            if offers:
                await save_listings(city_slug, offers)
                logger.info("Warmed up cache: city=%s, count=%d", city_slug, len(offers))
        except Exception as e:
            logger.warning("Warmup failed for city=%s: %s", city_slug, e)


def setup_scheduler(bot: "Bot") -> AsyncIOScheduler:
    """
    Настроить и вернуть планировщик.
    Вызвать scheduler.start() после.
    """
    scheduler = AsyncIOScheduler(timezone="Europe/Warsaw")

    scheduler.add_job(
        refresh_cached_cities,
        trigger=IntervalTrigger(hours=config.SCHEDULER_INTERVAL_HOURS),
        id="refresh_cache",
        name="Refresh cached cities",
        replace_existing=True,
        misfire_grace_time=300,
    )

    logger.info(
        "Scheduler configured: cache refresh every %dh",
        config.SCHEDULER_INTERVAL_HOURS,
    )
    return scheduler
