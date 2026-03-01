"""
SQL DDL statements for all tables.
"""

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    full_name   TEXT,
    role        TEXT DEFAULT 'user',
    agency_name TEXT,
    contact     TEXT,
    default_city TEXT,
    language    TEXT DEFAULT 'ru',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_LISTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS listings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id    TEXT NOT NULL,
    city        TEXT NOT NULL,
    data        TEXT NOT NULL,
    cached_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(offer_id, city)
)
"""

CREATE_CACHE_META_TABLE = """
CREATE TABLE IF NOT EXISTS cache_meta (
    city          TEXT PRIMARY KEY,
    last_updated  TIMESTAMP NOT NULL,
    total_count   INTEGER DEFAULT 0
)
"""

ALL_TABLES = [
    CREATE_USERS_TABLE,
    CREATE_LISTINGS_TABLE,
    CREATE_CACHE_META_TABLE,
]
