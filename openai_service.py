import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

import config
import database
import bot as bot_module

logger = logging.getLogger(__name__)


def get_variables() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "my_name": bot_module.my_name,
        "bot_name": bot_module.bot_name,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M UTC"),
        "day": now.strftime("%A"),
    }


def load_system_prompt() -> str:
    content = database.read_info()
    if content:
        return content.format(**get_variables())
    return "You are a helpful assistant."


class OpenAIService:
    def __init__(self):
        self.url = f"{config.BASE_URL}/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {config.API_KEY}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=60.0)

    async def chat(
        self,
        messages: list[dict],
        memory: str = "",
        sender_info: str = "",
    ) -> Optional[str]:
        import admin
        system = load_system_prompt()
        if sender_info:
            system += f"\n\nYou are talking to:\n{sender_info}"
        if memory:
            system += f"\n\nMemory:\n{memory}"

        full = [{"role": "system", "content": system}] + messages

        payload = {
            "model": config.MODEL,
            "messages": full,
            "max_tokens": admin.get_max_output_tokens(),
            "temperature": 0.7,
        }

        try:
            resp = await self.client.post(
                self.url, headers=self.headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            message = data["choices"][0]["message"]
            content = message.get("content") or message.get("reasoning_content")
            if not content:
                return None
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content or None
        except Exception:
            logger.warning("AI API unreachable")
            return None