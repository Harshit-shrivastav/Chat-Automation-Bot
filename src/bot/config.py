"""Configuration management for the bot."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    API_KEY: str = os.getenv("API_KEY", "")
    BASE_URL: str = os.getenv("BASE_URL", "https://api.openai.com/v1")
    MODEL: str = os.getenv("MODEL", "gpt-4o-mini")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")


config = Settings()