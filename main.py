
import os
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from flask import Flask
from threading import Thread

# --- Configuration (Koyeb Environment Variables) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = os.environ.get("TARGET_BOT") # এখানে আইডি (8255730628) বা ইউজারনেম দিতে পারেন

# --- Flask Server for Koyeb Health Check ---
app = Flask(__name__)
@app.route('/')
def health(): return "Bot is Alive", 200
def run_flask(): app.run(host="0.0.0.0", port=8080)

# --- Bot Clients ---
bot = Client("admin_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

# --- Modern Progress Bar Logic ---
async def progress_bar(current, total, status_msg, start_time, action):
    now = time.time()
    diff = now - start_time
    if round(diff % 4.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        eta = round((total - current) / speed) if speed > 0 else 0
        
        filled_length = int(15 * current // total)
        bar = '▰' * filled_length + '▱' * (15 - filled_length)
        
        progress_text = (
            f"🚀 **{action}...**\n"
            f"┣ {bar}\n"
            f"┣ 🌀 **প্রগতি:** {percentage:.2f}%\n"
            f"┣ 📦 **সাইজ:** {current/1024/1024:.2f} MB / {total/1024/1024:.2f} MB\n"
            f"┣ ⚡ **গতি:** {speed/1024/1024:.2f} MB/s\n"
            f"┗ ⏳ **বাকি সময়:** {eta}s"
        )
        try:
            await status_msg.edit(progress_text)
        except:
            pass

# --- Core Job Function ---
@bot.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    try:
        # Command format: /start_job [Chat_ID] [Start_ID] [Count]
        args = message.text.split()
        if len(args) < 4:
            await message.reply("❌ **সঠিক ফরম্যাট ব্যবহার করুন:**\n`/start_job -100xxxx 1 10`")
            return

        chat_id = args[1]
        try:
            chat_id = int(chat_id)
        except:
            pass # ইউজারনেম হলে স্ট্রিং হিসেবেই থাকবে

        start_id = int(args[2])
        count = int(args[3])
        
        # Resolve Target Bot ID (ID বা Username উভয়ই কাজ করবে)
        status_msg = await message.reply("🔍 **টার্গেট আইডি চেক করা হচ্ছে...**")
        try:
            target_raw = TARGET_BOT
            if target_raw.startswith("@"):
                target_raw = target_raw.replace("@", "")
            
            # যদি আইডি দেওয়া থাকে তবে ইন্টিজারে রূপান্তর
            try:
                target_input = int(target_raw)
            except:
                target_input = target_raw
                
            target_info = await user.get_users(target_input)
            target_id = target_info.id
        except Exception as e:
            await status_msg.edit(f"❌ **টার্গেট বট খুঁজে পাওয়া যায়নি!**\nError: {e}")
            return

        await status_msg.edit("🛰 **টাস্ক শুরু হচ্ছে...**")

        for i in range(count):
            current_msg_id = start_id + i
            await status_msg.edit(f"🔄 **মেসেজ চেক করা হচ্ছে:** `{current_msg_id}`\n({i+1}/{count})")

            try:
                msg = await user.get_messages(chat_id, current_msg_id)
                
                if msg and (msg.video or msg.photo or msg.document):
                    start_time = time.time()
                    
                    # 1. Download Media
                    file_path = await user.download_media(
                        msg, 
                        progress=progress_bar, 
                        progress_args=(status_msg, start_time, "ডাউনলোড")
                    )

                    # 2. Upload to Target Bot
                    start_time = time.time()
                    caption = msg.caption or ""
                    
                    if msg.video:
                        await user.send_video(target_id, video=file_path, caption=caption, progress=progress_bar, progress_args=(status_msg, start_time, "আপলোড"))
                    elif msg.photo:
                        await user.send_photo(target_id, photo=file_path, caption=caption)
                    elif msg.document:
                        await user.send_document(target_id, document=file_path, caption=caption, progress=progress_bar, progress_args=(status_msg, start_time, "আপলোড"))

                    # 3. Clean up Storage
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    await status_msg.edit(f"✅ **সফলভাবে পাঠানো হয়েছে:** `{current_msg_id}`\n৫ সেকেন্ড বিরতি...")
                    await asyncio.sleep(5)
                else:
                    await status_msg.edit(f"⏩ **স্কিপ:** `{current_msg_id}` (কোনো মিডিয়া নেই)")

            except FloodWait as e:
                await status_msg.edit(f"⚠️ **FloodWait:** {e.value} সেকেন্ড অপেক্ষা করছি...")
                await asyncio.sleep(e.value)
            except Exception as e:
                print(f"Error at {current_msg_id}: {e}")
                continue

        await status_msg.edit("🏁 **মিশন কমপ্লিট!** সব ফাইল আপনার টার্গেট বটে পাঠানো হয়েছে।")

    except Exception as e:
        await message.reply(f"🚨 **ত্রুটি:** {str(e)}")

# --- Run the Bot ---
if __name__ == "__main__":
    # Start Flask server for Koyeb in a separate thread
    Thread(target=run_flask).start()
    
    # Start both clients
    print("Bot is starting...")
    user.start()
    bot.run()
