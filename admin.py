import logging

from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
)

import database

logger = logging.getLogger(__name__)

router = Router()

pending_input: dict[int, str] = {}

bot_paused = False

MAX_HISTORY = 15
MAX_OUTPUT_TOKENS = 800
MAX_MEMORY_CHARS = 1500
MAX_INFO_CHARS = 1000
MEMORY_EXTRACT_INTERVAL = 15
DEFAULT_FALLBACK_MESSAGE = "Hey, I'm a bit busy right now. Will get back to you soon."
CHAT_TOGGLE_TRIGGER = "*"


def get_max_history() -> int:
    return int(database.read_setting("max_history") or MAX_HISTORY)


def get_max_output_tokens() -> int:
    return int(database.read_setting("max_output_tokens") or MAX_OUTPUT_TOKENS)


def get_max_memory_chars() -> int:
    return int(database.read_setting("max_memory_chars") or MAX_MEMORY_CHARS)


def get_max_info_chars() -> int:
    return int(database.read_setting("max_info_chars") or MAX_INFO_CHARS)


def get_memory_extract_interval() -> int:
    return int(database.read_setting("memory_extract_interval") or MEMORY_EXTRACT_INTERVAL)


def get_fallback_message() -> str:
    return database.read_setting("fallback_message") or DEFAULT_FALLBACK_MESSAGE


def get_chat_toggle_trigger() -> str:
    return database.read_setting("chat_toggle_trigger") or CHAT_TOGGLE_TRIGGER


def set_fallback_message(text: str):
    database.write_setting("fallback_message", text)


def is_paused() -> bool:
    return bot_paused


def panel_keyboard() -> InlineKeyboardMarkup:
    pause_label = "Resume Bot" if bot_paused else "Pause Bot"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Read Info", callback_data="admin_read_info"),
            InlineKeyboardButton(text="Read Memory", callback_data="admin_read_memory"),
        ],
        [
            InlineKeyboardButton(text="Edit Info", callback_data="admin_edit_info"),
            InlineKeyboardButton(text="Edit Memory", callback_data="admin_edit_memory"),
        ],
        [
            InlineKeyboardButton(text="Read Fallback", callback_data="admin_read_fallback"),
            InlineKeyboardButton(text="Edit Settings", callback_data="admin_settings"),
        ],
        [
            InlineKeyboardButton(text=pause_label, callback_data="admin_pause_toggle"),
            InlineKeyboardButton(text="Stop Bot", callback_data="admin_stop"),
        ],
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"Max History ({get_max_history()})", callback_data="admin_edit_max_history"),
            InlineKeyboardButton(text=f"Max Tokens ({get_max_output_tokens()})", callback_data="admin_edit_max_tokens"),
        ],
        [
            InlineKeyboardButton(text=f"Memory Chars ({get_max_memory_chars()})", callback_data="admin_edit_memory_chars"),
            InlineKeyboardButton(text=f"Info Chars ({get_max_info_chars()})", callback_data="admin_edit_info_chars"),
        ],
        [
            InlineKeyboardButton(text=f"Extract Interval ({get_memory_extract_interval()})", callback_data="admin_edit_extract_interval"),
            InlineKeyboardButton(text=f"Trigger ({get_chat_toggle_trigger()})", callback_data="admin_edit_trigger"),
        ],
        [
            InlineKeyboardButton(text="Back", callback_data="admin_back"),
        ],
    ])


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in database.get_admin_ids():
        return
    pending_input.pop(message.from_user.id, None)
    status = "PAUSED" if bot_paused else "RUNNING"
    await message.answer(
        f"Admin Panel — Bot: {status}",
        reply_markup=panel_keyboard(),
    )


@router.callback_query(F.data.startswith("admin_"))
async def handle_admin_callback(callback: CallbackQuery, bot: Bot):
    global bot_paused
    if callback.from_user.id not in database.get_admin_ids():
        await callback.answer("Not authorized")
        return

    data = callback.data

    if data == "admin_read_info":
        content = database.read_info()
        text = content if content else "(empty)"
        await callback.message.answer(f"Info:\n\n{text}")
        await callback.answer()

    elif data == "admin_read_memory":
        content = database.read_setting("memory")
        text = content if content else "(empty)"
        await callback.message.answer(f"Memory:\n\n{text}")
        await callback.answer()

    elif data == "admin_edit_info":
        pending_input[callback.from_user.id] = "edit_info"
        from openai_service import get_variables
        vars = get_variables()
        var_list = "\n".join(f"  {{{k}}} = {v}" for k, v in vars.items())
        await callback.message.answer(
            "Send new system prompt for info.\n\n"
            f"Available variables:\n{var_list}\n\n"
            "Use them like: You are {{my_name}}."
        )
        await callback.answer()

    elif data == "admin_edit_memory":
        pending_input[callback.from_user.id] = "edit_memory"
        await callback.message.answer("Send new content for memory (will replace entire file):")
        await callback.answer()

    elif data == "admin_read_fallback":
        msg = get_fallback_message()
        await callback.message.answer(f"Fallback message:\n\n{msg}")
        await callback.answer()

    elif data == "admin_settings":
        await callback.message.edit_text(
            "Bot Settings:",
            reply_markup=settings_keyboard(),
        )
        await callback.answer()

    elif data == "admin_back":
        status = "PAUSED" if bot_paused else "RUNNING"
        await callback.message.edit_text(
            f"Admin Panel — Bot: {status}",
            reply_markup=panel_keyboard(),
        )
        await callback.answer()

    elif data == "admin_edit_max_history":
        pending_input[callback.from_user.id] = "edit_max_history"
        await callback.message.answer(f"Current: {get_max_history()}\nSend new value (number):")
        await callback.answer()

    elif data == "admin_edit_max_tokens":
        pending_input[callback.from_user.id] = "edit_max_tokens"
        await callback.message.answer(f"Current: {get_max_output_tokens()}\nSend new value (number):")
        await callback.answer()

    elif data == "admin_edit_memory_chars":
        pending_input[callback.from_user.id] = "edit_memory_chars"
        await callback.message.answer(f"Current: {get_max_memory_chars()}\nSend new value (number):")
        await callback.answer()

    elif data == "admin_edit_info_chars":
        pending_input[callback.from_user.id] = "edit_info_chars"
        await callback.message.answer(f"Current: {get_max_info_chars()}\nSend new value (number):")
        await callback.answer()

    elif data == "admin_edit_extract_interval":
        pending_input[callback.from_user.id] = "edit_extract_interval"
        await callback.message.answer(f"Current: {get_memory_extract_interval()}\nSend new value (number):")
        await callback.answer()

    elif data == "admin_edit_trigger":
        pending_input[callback.from_user.id] = "edit_trigger"
        await callback.message.answer(f"Current: {get_chat_toggle_trigger()}\nSend new trigger text:")
        await callback.answer()

    elif data == "admin_pause_toggle":
        if bot_paused:
            bot_paused = False
            status = "RUNNING"
        else:
            bot_paused = True
            status = "PAUSED"
        await callback.message.edit_text(
            f"Admin Panel — Bot: {status}",
            reply_markup=panel_keyboard(),
        )
        await callback.answer(f"Bot {status}")

    elif data == "admin_stop":
        await callback.message.answer("Bot stopping...")
        await callback.answer("Bye")
        await bot.session.close()
