import os
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from flask import Flask
from threading import Thread

# --- Configuration (Environment Variables) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = os.environ.get("TARGET_BOT")

# --- Flask Server ---
app = Flask(__name__)
@app.route('/')
def health(): return "Bot is Alive", 200
def run_flask(): app.run(host="0.0.0.0", port=8080)

# --- Bot Clients ---
bot = Client("admin_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

# --- Progress Bar Logic ---
async def progress_bar(current, total, status_msg, start_time, action):
    now = time.time()
    diff = now - start_time
    if round(diff % 4.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff)
        eta = round((total - current) / speed) if speed > 0 else 0
        
        filled_length = int(15 * current // total)
        bar = '▰' * filled_length + '▱' * (15 - filled_length)
        
        tmp = (
            f"🚀 **{action}...**\n"
            f"┣ {bar}\n"
            f"┣ 🌀 **প্রগতি:** {percentage:.2f}%\n"
            f"┣ 📦 **সাইজ:** {current/1024/1024:.2f} MB / {total/1024/1024:.2f} MB\n"
            f"┣ ⚡ **গতি:** {speed/1024/1024:.2f} MB/s\n"
            f"┗ ⏳ **বাকি সময়:** {eta}s"
        )
        try:
            await status_msg.edit(tmp)
        except:
            pass

# --- Core Job ---
@bot.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    try:
        args = message.text.split()
        if len(args) < 4:
            await message.reply("❌ ফরম্যাট: `/start_job [Chat_ID] [Start_ID] [Count]`")
            return

        chat_id = args[1]
        start_id = int(args[2])
        count = int(args[3])
        
        target_info = await user.get_users(TARGET_BOT)
        target_id = target_info.id

        status_msg = await message.reply("🛰 **টাস্ক প্রসেসিং শুরু হচ্ছে...**")

        for i in range(count):
            current_msg_id = start_id + i
            await status_msg.edit(f"🔍 চেক করা হচ্ছে মেসেজ আইডি: `{current_msg_id}` ({i+1}/{count})")

            try:
                msg = await user.get_messages(chat_id, current_msg_id)
                
                if msg.video or msg.photo or msg.document:
                    start_time = time.time()
                    media_type = "ডাউনলোড"
                    
                    # Download with Progress
                    file_path = await user.download_media(
                        msg, 
                        progress=progress_bar, 
                        progress_args=(status_msg, start_time, media_type)
                    )

                    # Send to Target Bot
                    start_time = time.time()
                    media_type = "আপলোড"
                    if msg.video:
                        await user.send_video(target_id, video=file_path, caption=msg.caption, progress=progress_bar, progress_args=(status_msg, start_time, media_type))
                    elif msg.photo:
                        await user.send_photo(target_id, photo=file_path, caption=msg.caption)
                    elif msg.document:
                        await user.send_document(target_id, document=file_path, caption=msg.caption)

                    # Cleanup
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    await status_msg.edit(f"✅ সফলভাবে পাঠানো হয়েছে: `{current_msg_id}`\nপরবর্তীতে যাওয়ার আগে ৫ সেকেন্ড বিরতি...")
                    await asyncio.sleep(5)
                else:
                    await status_msg.edit(f"⏩ স্কিপ করা হয়েছে: `{current_msg_id}` (কোনো মিডিয়া নেই)")

            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                await bot.send_message(ADMIN_ID, f"❌ ত্রুটি আইডি `{current_msg_id}`: {str(e)}")
                continue

        await status_msg.edit("🏁 **মিশন কমপ্লিট!** সব ফাইল পাঠানো হয়েছে।")

    except Exception as e:
        await message.reply(f"🚨 মারাত্মক ত্রুটি: {str(e)}")

if __name__ == "__main__":
    Thread(target=run_flask).start()
    user.start()
    bot.run()
