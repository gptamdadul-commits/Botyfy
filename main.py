import asyncio
import os
from pyrogram import Client, filters
from flask import Flask

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

TARGET_BOT = "@Sami_bideshbot"

user_app = Client("user", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is alive"

async def process(chat, start_id, count):
    sent = 0
    status = await bot_app.send_message(ADMIN_ID, "শুরু...")
    try:
        async for msg in user_app.get_chat_history(chat, offset_id=int(start_id), limit=1000):
            if sent >= int(count): break
            if not msg.video: continue
            await user_app.forward_messages(TARGET_BOT, msg.chat.id, msg.id)
            sent += 1
            await status.edit(f"{sent}/{count}")
            await asyncio.sleep(3)
        await status.edit(f"সম্পন্ন! {sent}")
    except Exception as e:
        await bot_app.send_message(ADMIN_ID, str(e))

@bot_app.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job(_, msg):
    args = msg.text.split()
    if len(args) < 4:
        return await msg.reply("ফরম্যাট: /start_job চ্যানেল start_id count")
    asyncio.create_task(process(args[1], args[2], args[3]))
    await msg.reply("চলছে...")

async def main():
    # Flask সার্ভার আলাদা থ্রেডে
    from threading import Thread
    Thread(target=flask_app.run, kwargs=dict(host="0.0.0.0", port=8080)).start()

    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "চালু ✓")

    # লুপ চিরকাল চালু রাখা
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
