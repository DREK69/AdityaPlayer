import asyncio, os, pyrogram, sys

from . import app, bot, call, console
from .modules.database import adb_cli
from .plugins import import_all_plugins


async def main():
    for file in os.listdir():
        if file.endswith(".session"):
            os.remove(file)
    for file in os.listdir():
        if file.endswith(".session-journal"):
            os.remove(file)
    if "cache" not in os.listdir():
        os.mkdir("cache")
    if "downloads" not in os.listdir():
        os.mkdir("downloads")
    try:
        await adb_cli.admin.command("ping")
    except Exception:
        console.logs(__name__).error(
            "❌ 'MONGO_URL' - is not valid❗"
        )
        sys.exit()
    await console.sudo_users()
    try:
        await bot.start()
    except Exception as e:
        console.logs(__name__).error(
            f"❌ Failed to start bot❗\n⚠️ Reason: {e}"
        )
        sys.exit()
    try:
        await app.start()
    except Exception as e:
        console.logs(__name__).error(
            f"❌ Failed to start assistant❗\n⚠️ Reason: {e}"
        )
        sys.exit()
    try:
        await call.start()
    except Exception as e:
        console.logs(__name__).error(
            f"❌ Failed to start PyTgCalls❗\n⚠️ Reason: {e}"
        )
        sys.exit()
    await call.decorators()
    await import_all_plugins()
    console.logs(__name__).info("✅ Now Do Visit: @DEPSTEY.")
    await pyrogram.idle()
    
    
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    console.logs(__name__).info("✅ All Clients are stopped, Goodbye.")
