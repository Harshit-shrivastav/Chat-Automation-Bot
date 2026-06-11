import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, BusinessConnection

import config
import admin
import database
from memory import MemoryManager
from openai_service import OpenAIService

logger = logging.getLogger(__name__)

router = Router()

chat_histories: dict[int, list[dict]] = {}
message_counts: dict[int, int] = {}
user_locks: dict[int, asyncio.Lock] = {}
sender_profiles: dict[int, str] = {}
processed_messages: dict[tuple[int, int], float] = {}

active_connections: dict[str, int] = {}
admin_ids: set[int] = set()
my_name: str = "User"
bot_name: str = "AI Assistant"

openai_service = OpenAIService()
memory_manager = MemoryManager()


def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


def get_history(key: int) -> list[dict]:
    if key not in chat_histories:
        chat_histories[key] = []
    return chat_histories[key]


def add_to_history(key: int, role: str, content: str):
    history = get_history(key)
    history.append({"role": role, "content": content})
    if len(history) > admin.get_max_history():
        chat_histories[key] = history[-admin.get_max_history():]


def build_sender_profile(message: Message) -> str:
    user = message.from_user
    if not user:
        return ""
    parts = []
    if user.first_name:
        name = user.first_name
        if user.last_name:
            name += f" {user.last_name}"
        parts.append(f"Name: {name}")
    if user.username:
        parts.append(f"Username: @{user.username}")
    parts.append(f"User ID: {user.id}")
    if user.language_code:
        parts.append(f"Language: {user.language_code}")
    return "\n".join(parts)


def handle_admin_chat_control(user_id: int, text: str, chat_id: int) -> str | None:
    if text == admin.get_chat_toggle_trigger():
        if database.is_chat_disabled(chat_id):
            database.set_chat_enabled(chat_id)
            return f"Chat {chat_id} enabled."
        else:
            database.set_chat_disabled(chat_id)
            return f"Chat {chat_id} disabled."
    return None


async def keep_typing(bot: Bot, chat_id: int, business_connection_id: str | None = None):
    try:
        await asyncio.sleep(1.0)
        while True:
            kwargs = {"chat_id": chat_id, "action": "typing"}
            if business_connection_id:
                kwargs["business_connection_id"] = business_connection_id
            await bot.send_chat_action(**kwargs)
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


async def send_reply(bot: Bot, message: Message, reply: str):
    bc_id = message.business_connection_id
    if bc_id:
        await bot.send_message(
            chat_id=message.chat.id,
            text=reply,
            business_connection_id=bc_id,
        )
    else:
        await message.answer(reply)


@router.business_connection()
async def handle_business_connection(bc: BusinessConnection, bot: Bot):
    active_connections[bc.id] = bc.user_chat_id
    admin_ids.add(bc.user_chat_id)
    database.add_admin_id(bc.user_chat_id)
    status = "connected" if bc.is_enabled else "disabled"
    logger.info("Business connection %s: %s (user %d)", bc.id, status, bc.user_chat_id)

    if bc.is_enabled:
        try:
            chat = await bot.get_chat(bc.user_chat_id)
            my_name = chat.first_name or "User"
            logger.info("Admin name set to: %s", my_name)
        except Exception:
            logger.exception("Failed to get admin name")


@router.business_message(F.text & F.business_connection_id)
async def handle_business_message(message: Message, bot: Bot):
    bc_id = message.business_connection_id
    if not bc_id:
        return

    msg_key = (message.chat.id, message.message_id)
    import time
    now = time.time()
    if msg_key in processed_messages:
        logger.info("Message %d from chat %d already processed, skipping", message.message_id, message.chat.id)
        return
    processed_messages[msg_key] = now
    if len(processed_messages) > 500:
        cutoff = now - 60
        processed_messages.copy()
        processed_messages.update({k: v for k, v in processed_messages.items() if v > cutoff})

    text = message.text
    if not text:
        return

    sender_id = message.chat.id

    if bc_id not in active_connections:
        try:
            bc_info = await bot.get_business_connection(bc_id)
            if bc_info.user_chat_id:
                active_connections[bc_id] = bc_info.user_chat_id
                admin_ids.add(bc_info.user_chat_id)
                database.add_admin_id(bc_info.user_chat_id)
                if not my_name:
                    chat = await bot.get_chat(bc_info.user_chat_id)
                    my_name = chat.first_name or "User"
                    logger.info("Admin name set to: %s", my_name)
        except Exception:
            logger.exception("Failed to get business connection info")

    if message.from_user and message.from_user.id in admin_ids:
        control_msg = handle_admin_chat_control(message.from_user.id, text, sender_id)
        if control_msg:
            await bot.send_message(chat_id=message.from_user.id, text=control_msg)
            return
        logger.info("Admin's own message, skipping AI reply")
        return

    if database.is_chat_disabled(sender_id):
        logger.info("Chat %d is disabled, skipping", sender_id)
        return

    from_id = message.from_user.id if message.from_user else sender_id
    sender_name = message.from_user.first_name if message.from_user else "Unknown"
    logger.info("Business msg from %s (id=%d): %s", sender_name, sender_id, text[:50])

    if admin.is_paused():
        fallback = admin.get_fallback_message()
        logger.info("Bot paused, sending fallback")
        await send_reply(bot, message, fallback)
        return

    history_key = sender_id

    profile = build_sender_profile(message)
    if profile:
        sender_profiles[sender_id] = profile

    add_to_history(history_key, "user", text)

    typing = asyncio.create_task(keep_typing(bot, message.chat.id, bc_id))
    try:
        lock = get_user_lock(sender_id)
        async with lock:
            memory = memory_manager.read_memory()
            sender_info = sender_profiles.get(sender_id, "")
            history = get_history(history_key)
            reply = await openai_service.chat(
                history, memory=memory, sender_info=sender_info
            )
    finally:
        typing.cancel()
        try:
            await typing
        except asyncio.CancelledError:
            pass

    if reply is None:
        logger.info("API returned None, not replying")
        return

    logger.info("Replying to %s: %s", sender_name, reply[:50])
    add_to_history(history_key, "assistant", reply)

    try:
        await send_reply(bot, message, reply)
        logger.info("Reply sent successfully")
    except Exception:
        logger.exception("Failed to send reply to %s", sender_name)

    message_counts[sender_id] = message_counts.get(sender_id, 0) + 1
    if message_counts[sender_id] % admin.get_memory_extract_interval() == 0:
        asyncio.create_task(run_memory_extraction(sender_id))


@router.message(CommandStart())
async def handle_start(message: Message):
    if message.from_user.id in admin_ids:
        admin.pending_input.pop(message.from_user.id, None)
        status = "PAUSED" if admin.is_paused() else "RUNNING"
        await message.answer(
            f"Admin Panel — Bot: {status}",
            reply_markup=admin.panel_keyboard(),
        )
    else:
        await message.answer(
            "Hey! I'm your AI assistant.\n\n"
            "Talk to me in any language — I'll reply in the same style.\n"
            "I remember our chats to know you better over time.\n\n"
            "Send a message to start!"
        )


@router.message(F.text & F.chat.type == "private")
async def handle_direct_message(message: Message, bot: Bot):
    if message.business_connection_id:
        return

    msg_key = (message.chat.id, message.message_id)
    import time
    now = time.time()
    if msg_key in processed_messages:
        logger.info("Message %d from chat %d already processed, skipping", message.message_id, message.chat.id)
        return
    processed_messages[msg_key] = now
    if len(processed_messages) > 500:
        cutoff = now - 60
        processed_messages.update({k: v for k, v in processed_messages.items() if v > cutoff})

    text = message.text
    if not text:
        return

    logger.info("Direct msg: from_id=%d, admin_ids=%s, text=%s",
                message.from_user.id, admin_ids, text[:30])

    if message.from_user.id in admin_ids:
        if text.startswith("/"):
            logger.info("Admin / command, skipping")
            return
        control_msg = handle_admin_chat_control(message.from_user.id, text, message.from_user.id)
        if control_msg:
            await message.answer(control_msg)
            return
        if message.from_user.id in admin.pending_input:
            action = admin.pending_input.pop(message.from_user.id)
            if action == "edit_info":
                database.write_info(text.strip())
                await message.answer("Info updated.")
            elif action == "edit_memory":
                database.write_setting("memory", text.strip())
                await message.answer("Memory updated.")
            elif action == "set_fallback":
                database.write_setting("fallback_message", text.strip())
                await message.answer("Fallback message updated.")
            elif action == "edit_max_history":
                database.write_setting("max_history", str(int(text.strip())))
                await message.answer(f"Max history set to: {text.strip()}")
            elif action == "edit_max_tokens":
                database.write_setting("max_output_tokens", str(int(text.strip())))
                await message.answer(f"Max tokens set to: {text.strip()}")
            elif action == "edit_memory_chars":
                database.write_setting("max_memory_chars", str(int(text.strip())))
                await message.answer(f"Max memory chars set to: {text.strip()}")
            elif action == "edit_info_chars":
                database.write_setting("max_info_chars", str(int(text.strip())))
                await message.answer(f"Max info chars set to: {text.strip()}")
            elif action == "edit_extract_interval":
                database.write_setting("memory_extract_interval", str(int(text.strip())))
                await message.answer(f"Extract interval set to: {text.strip()}")
            elif action == "edit_trigger":
                database.write_setting("chat_toggle_trigger", text.strip())
                await message.answer(f"Trigger set to: {text.strip()}")
            return
        status = "PAUSED" if admin.is_paused() else "RUNNING"
        await message.answer(
            f"Admin Panel — Bot: {status}",
            reply_markup=admin.panel_keyboard(),
        )
        return

    if admin.is_paused():
        fallback = admin.get_fallback_message()
        await message.answer(fallback)
        return

    if database.is_chat_disabled(message.from_user.id):
        logger.info("Chat %d is disabled, skipping", message.from_user.id)
        return

    user_id = message.from_user.id
    add_to_history(user_id, "user", text)

    typing = asyncio.create_task(keep_typing(bot, message.chat.id))

    lock = get_user_lock(user_id)
    try:
        async with lock:
            memory = memory_manager.read_memory()
            history = get_history(user_id)
            reply = await openai_service.chat(history, memory=memory)
    finally:
        typing.cancel()
        try:
            await typing
        except asyncio.CancelledError:
            pass

    if reply is None:
        logger.info("API returned None, not replying")
        return

    add_to_history(user_id, "assistant", reply)
    await message.answer(reply)

    message_counts[user_id] = message_counts.get(user_id, 0) + 1
    if message_counts[user_id] % admin.get_memory_extract_interval() == 0:
        asyncio.create_task(run_memory_extraction(user_id))


async def run_memory_extraction(key: int):
    history = get_history(key)
    try:
        await memory_manager.extract(history)
    except Exception:
        logger.exception("Memory extraction failed for key %d", key)


async def start_bot():
    bot = Bot(token=config.BOT_TOKEN)

    me = await bot.get_me()
    bot_name = me.first_name
    logger.info("Bot name: %s", bot_name)

    admin_ids.update(database.get_admin_ids())
    logger.info("Loaded admin IDs: %s", admin_ids)

    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(router)

    logger.info("Bot starting...")
    await dp.start_polling(bot)
