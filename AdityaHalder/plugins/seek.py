from pyrogram import filters
from .. import bot, call, cdx
from ..modules.helpers import AdminsOnlyWrapper


@bot.on_message(cdx("seek") & ~filters.private)
@AdminsOnlyWrapper
async def seek_command(client, message):
    chat_id = message.chat.id

    if len(message.command) < 2:
        return await message.reply_text(
            "⚠️ Usage:\n"
            "• `/seek 60` → jump to 60 seconds\n"
            "• `/seek 1:30` → jump to 1 minute 30 seconds"
        )

    arg = message.command[1]
    try:
        if ":" in arg:  # mm:ss format
            minutes, seconds = map(int, arg.split(":"))
            position = minutes * 60 + seconds
        else:  # seconds
            position = int(arg)
    except ValueError:
        return await message.reply_text(
            "❌ Invalid seek position.\nUse seconds (e.g. `/seek 90`) or mm:ss (e.g. `/seek 1:30`)."
        )

    success, msg = await call.seek_stream(chat_id, position)
    await message.reply_text(msg)
