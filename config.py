import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    DB_PATH: str = field(default_factory=lambda: os.getenv("DB_PATH", "realty_bot.db"))
    CACHE_TTL_HOURS: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL_HOURS", "12")))
    SCHEDULER_INTERVAL_HOURS: int = field(default_factory=lambda: int(os.getenv("SCHEDULER_INTERVAL_HOURS", "6")))
    REQUEST_DELAY: float = field(default_factory=lambda: float(os.getenv("REQUEST_DELAY", "2.0")))
    MAX_RETRIES: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    PAGE_SIZE: int = 10  # Items per page in bot results
    API_BASE_URL: str = "https://zametr.pl"
    API_ENDPOINT: str = "https://zametr.pl/api/search/map/offer"


config = Config()
