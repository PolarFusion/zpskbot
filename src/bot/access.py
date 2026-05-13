from __future__ import annotations

from aiogram.types import Message


def is_admin(user_id: int, admin_ids: set[int]) -> bool:
    return user_id in admin_ids


def should_respond_in_group(message: Message, bot_username: str) -> bool:
    if message.chat.type == "private":
        return True

    text = (message.text or "").strip()
    if text.startswith("/"):
        return True

    if message.reply_to_message:
        return True

    if bot_username and f"@{bot_username.lower()}" in text.lower():
        return True

    return False
