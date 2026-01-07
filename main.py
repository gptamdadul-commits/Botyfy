import os, asyncio
from pyrogram import Client, filters, errors
from flask import Flask
from threading import Thread

# --- Environment Variables ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

# Target bot ID (positive user id of the bot)
TARGET_BOT_ID = 8255730628

# Clients
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DOWNLOAD_DIR = "downloads/"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- Core processing function ---
async def process_videos(chat_input, start_id, count):
    sent = 0
    status_msg = None
    
    try:
        chat = await user_app.get_chat(chat_input)
        target_chat_id = chat.id
        
        status_msg = await bot_app.send_message(ADMIN_ID, "⏳ কাজ শুরু হচ্ছে...")

        async for message in user_app.get_chat_history(
            target_chat_id, 
            offset_id=int(start_id), 
            limit=1000
        ):
            if sent >= int(count):
                break
                
            if not message.video:
                continue

            current = sent + 1
            await status_msg.edit_text(
                f"📥 {current}/{count}\n"
                f"🆔 {message.id}\n"
                f"ডাউনলোড হচ্ছে..."
            )

            file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)

            await status_msg.edit_text(
                f"📤 {current}/{count}\n"
                f"🆔 {message.id}\n"
                f"আপলোড হচ্ছে..."
            )

            await user_app.send_video(
                TARGET_BOT_ID,
                video=file_path,
                caption=f"উৎস: {chat_input}\nভিডিও আইডি: {message.id}"
            )

            if os.path.exists(file_path):
                os.remove(file_path)

            sent += 1
            await asyncio.sleep(45)

        await status_msg.edit_text(f"✅ সম্পন্ন!\nমোট: {sent} টি")

    except errors.FloodWait as e:
        await bot_app.send_message(ADMIN_ID, f"FloodWait: {e.value}s")
        await asyncio.sleep(e.value)
    except Exception as e:
        await bot_app.send_message(ADMIN_ID, f"ত্রুটি: {type(e).__name__}\n{str(e)}")

# --- Commands ---
@bot_app.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(_, message):
    args = message.text.split()
    if len(args) < 4:
        return await message.reply("`/start_job চ্যানেল শুরু_আইডি সংখ্যা`")
    
    asyncio.create_task(process_videos(args[1], args[2], args[3]))
    await message.reply("প্রসেসিং শুরু হয়েছে।")

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(_, message):
    await message.reply("`/start_job চ্যানেল শুরু_আইডি সংখ্যা`")

# --- Web server for platform health check ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Healthy"

async def start_all():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "Bot চালু ✓")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
    asyncio.get_event_loop().run_forever()
