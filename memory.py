import asyncio
import logging
import re

import httpx

import config
import database

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = (
    "From the chat below, extract ONLY important personal details about the user. "
    "Skip casual chat, greetings, jokes, general topics.\n\n"
    "Save to MEMORY: name, preferences, opinions, things they like/dislike, "
    "ongoing projects, important events.\n"
    "Save to INFO: who they are, what they care about, how to talk to them.\n\n"
    "Be very brief. Few words per point. Skip if nothing important.\n\n"
    "Format EXACTLY like this (leave section empty if nothing to save):\n\n"
    "MEMORY:\n- point 1\n- point 2\n\n"
    "INFO:\n- point 1\n- point 2\n\n"
    "If nothing worth saving, reply: NOTHING"
)


class MemoryManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.url = f"{config.BASE_URL}/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {config.API_KEY}",
            "Content-Type": "application/json",
        }
        self.client = httpx.AsyncClient(timeout=60.0)

    def read_memory(self) -> str:
        import admin as admin_module
        return database.read_memory()[:admin_module.get_max_memory_chars()]

    def read_info(self) -> str:
        import admin as admin_module
        return database.read_info()[:admin_module.get_max_info_chars()]

    def _append(self, key: str, content: str):
        existing = database.read_setting(key)
        existing_items = set()
        for line in existing.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                existing_items.add(stripped.lower())

        new_items = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("- ") and stripped.lower() not in existing_items:
                new_items.append(stripped)

        if new_items:
            updated = existing + "\n" + "\n".join(new_items)
            updated = updated.strip()
            import admin as admin_module
            if key == "memory" and len(updated) > admin_module.get_max_memory_chars():
                lines = updated.splitlines()
                updated = "\n".join(lines[-50:])
            elif key == "info" and len(updated) > admin_module.get_max_info_chars():
                lines = updated.splitlines()
                updated = "\n".join(lines[-30:])
            database.write_setting(key, updated)

    async def extract(self, messages: list[dict]):
        recent = messages[-10:]
        conversation = ""
        for m in recent:
            tag = "User" if m["role"] == "user" else "Bot"
            conversation += f"{tag}: {m['content']}\n"

        payload = {
            "model": config.MODEL,
            "messages": [
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": conversation},
            ],
            "max_tokens": 300,
        }

        try:
            resp = await self.client.post(
                self.url, headers=self.headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            message = data["choices"][0]["message"]
            text = message.get("content") or message.get("reasoning_content") or ""
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

            if "NOTHING" in text.upper() and len(text) < 20:
                return

            memory_part = ""
            info_part = ""
            current = None
            for line in text.splitlines():
                upper = line.strip().upper()
                if upper.startswith("MEMORY:"):
                    current = "memory"
                    continue
                elif upper.startswith("INFO:"):
                    current = "info"
                    continue
                if current == "memory":
                    memory_part += line + "\n"
                elif current == "info":
                    info_part += line + "\n"

            async with self._lock:
                if memory_part.strip():
                    self._append("memory", memory_part)
                if info_part.strip():
                    self._append("info", info_part)

            logger.info("Memory extracted")

        except Exception:
            logger.exception("Memory extraction failed")