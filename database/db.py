import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite

from config import config
from database.models import ALL_TABLES

logger = logging.getLogger(__name__)

_db_path = config.DB_PATH


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        for ddl in ALL_TABLES:
            await db.execute(ddl)
        await db.commit()
    logger.info("Database initialized at %s", _db_path)


# ─── Users ────────────────────────────────────────────────────────────────────

async def upsert_user(
    user_id: int,
    username: Optional[str],
    full_name: Optional[str],
    role: str = "user",
    agency_name: Optional[str] = None,
    contact: Optional[str] = None,
    default_city: Optional[str] = None,
) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name, role, agency_name, contact, default_city, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username     = excluded.username,
                full_name    = excluded.full_name,
                role         = COALESCE(excluded.role, role),
                agency_name  = COALESCE(excluded.agency_name, agency_name),
                contact      = COALESCE(excluded.contact, contact),
                default_city = COALESCE(excluded.default_city, default_city),
                updated_at   = CURRENT_TIMESTAMP
            """,
            (user_id, username, full_name, role, agency_name, contact, default_city),
        )
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def set_user_city(user_id: int, city: str) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE users SET default_city = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (city, user_id),
        )
        await db.commit()


async def set_user_role(user_id: int, role: str) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (role, user_id),
        )
        await db.commit()


async def set_user_agency(user_id: int, agency_name: str, contact: Optional[str]) -> None:
    async with aiosqlite.connect(_db_path) as db:
        await db.execute(
            """UPDATE users SET agency_name = ?, contact = ?, updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ?""",
            (agency_name, contact, user_id),
        )
        await db.commit()


# ─── Listings Cache ────────────────────────────────────────────────────────────

async def save_listings(city: str, offers: list[dict]) -> None:
    """Replace all cached listings for a city."""
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("DELETE FROM listings WHERE city = ?", (city,))
        await db.executemany(
            "INSERT OR REPLACE INTO listings (offer_id, city, data) VALUES (?, ?, ?)",
            [(o["offerId"], city, json.dumps(o, ensure_ascii=False)) for o in offers],
        )
        await db.execute(
            """
            INSERT INTO cache_meta (city, last_updated, total_count)
            VALUES (?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(city) DO UPDATE SET
                last_updated = CURRENT_TIMESTAMP,
                total_count  = excluded.total_count
            """,
            (city, len(offers)),
        )
        await db.commit()
    logger.info("Cached %d listings for city=%s", len(offers), city)


async def get_cached_listings(city: str) -> Optional[list[dict]]:
    """Return cached listings if fresh, else None."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT last_updated FROM cache_meta WHERE city = ?", (city,)
        ) as cursor:
            meta = await cursor.fetchone()

        if meta is None:
            return None

        last_updated = datetime.fromisoformat(meta["last_updated"])
        if datetime.utcnow() - last_updated > timedelta(hours=config.CACHE_TTL_HOURS):
            logger.info("Cache expired for city=%s", city)
            return None

        async with db.execute(
            "SELECT data FROM listings WHERE city = ?", (city,)
        ) as cursor:
            rows = await cursor.fetchall()

    return [json.loads(r["data"]) for r in rows]


async def get_all_cached_cities() -> list[str]:
    """Return list of cities that have cached data."""
    async with aiosqlite.connect(_db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT city FROM cache_meta") as cursor:
            rows = await cursor.fetchall()
    return [r["city"] for r in rows]
