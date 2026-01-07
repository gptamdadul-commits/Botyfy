import os
import asyncio
from pyrogram import Client, filters, errors
from flask import Flask
from threading import Thread

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
    try:
        status = await bot_app.send_message(ADMIN_ID, "শুরু হচ্ছে...")
        async for msg in user_app.get_chat_history(chat, offset_id=int(start_id), limit=1000):
            if sent >= int(count):
                break
            if not msg.video:
                continue
            await user_app.forward_messages(TARGET_BOT, msg.chat.id, msg.id)
            sent += 1
            await status.edit(f"পাঠানো: {sent}/{count}")
            await asyncio.sleep(3)
        await status.edit(f"সম্পন্ন! মোট: {sent}")
    except Exception as e:
        await bot_app.send_message(ADMIN_ID, f"ত্রুটি: {str(e)}")

@bot_app.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job(_, message):
    args = message.text.split()
    if len(args) < 4:
        await message.reply("ফরম্যাট: /start_job চ্যানেল start_id count")
        return
    asyncio.create_task(process(args[1], args[2], args[3]))
    await message.reply("চলছে...")

async def main():
    # Flask আলাদা থ্রেডে
    Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8080, debug=False)).start()
    
    await user_app.start()
    await bot_app.start()
    print("Bot started successfully")
    await bot_app.send_message(ADMIN_ID, "Bot চালু ✓")
    
    # মূল লুপ চালু রাখা
    await asyncio.Event().wait()  # চিরকাল অপেক্ষা (run_forever এর বিকল্প)

if __name__ == "__main__":
    asyncio.run(main())
