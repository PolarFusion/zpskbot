from aiogram.types import Chat, Message, User

from bot.access import should_respond_in_group


def _message(text: str, chat_type: str = "group", reply=False):
    reply_to = Message(message_id=99, date=0, chat=Chat(id=1, type=chat_type), from_user=User(id=1, is_bot=False, first_name="U"), text="x") if reply else None
    return Message(
        message_id=1,
        date=0,
        chat=Chat(id=1, type=chat_type),
        from_user=User(id=2, is_bot=False, first_name="Tester"),
        text=text,
        reply_to_message=reply_to,
    )


def test_group_trigger_by_mention():
    msg = _message("Привет @mybot")
    assert should_respond_in_group(msg, "mybot") is True


def test_group_trigger_by_reply():
    msg = _message("ok", reply=True)
    assert should_respond_in_group(msg, "mybot") is True


def test_group_silent_without_trigger():
    msg = _message("просто сообщение")
    assert should_respond_in_group(msg, "mybot") is False


def test_private_always_true():
    msg = _message("привет", chat_type="private")
    assert should_respond_in_group(msg, "mybot") is True
