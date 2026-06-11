import logging
import sys

import config


def validate_config():
    errors = []
    if not config.BOT_TOKEN:
        errors.append("BOT_TOKEN is not set")
    if not config.API_KEY:
        errors.append("API_KEY is not set")
    if errors:
        for e in errors:
            logging.error(e)
        sys.exit(1)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    validate_config()

    import database
    database.init_db()
    logging.info("Database initialized")

    import asyncio
    from bot import start_bot

    asyncio.run(start_bot())


if __name__ == "__main__":
    main()