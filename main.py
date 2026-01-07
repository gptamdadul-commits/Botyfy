import os, asyncio, shutil, json
from pyrogram import Client, filters, errors
from flask import Flask
from threading import Thread

# --- কনফিগারেশন ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = "@Sami_bideshbot"

user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DOWNLOAD_DIR = "downloads/"
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

# --- ভিডিও প্রসেসিং ফাংশন ---
async def process_videos(chat_id, start_id, count):
    sent = 0
    try:
        await bot_app.send_message(ADMIN_ID, f"🚀 কাজ শুরু! চ্যানেল: `{chat_id}` থেকে `{count}`টি ভিডিও নেওয়া হচ্ছে।")
        
        # offset_id ব্যবহার করে নির্দিষ্ট আইডি থেকে শুরু
        async for message in user_app.get_chat_history(chat_id, offset_id=int(start_id), limit=500):
            if sent >= int(count):
                break
            
            if message.video:
                file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                await user_app.send_video(TARGET_BOT, video=file_path, caption=f"উৎস: {chat_id}\nআইডি: {message.id}")
                
                if os.path.exists(file_path): os.remove(file_path) # মেমোরি ক্লিয়ার
                
                sent += 1
                await asyncio.sleep(30) # সেফটি ডিলে

        await bot_app.send_message(ADMIN_ID, f"✅ কাজ শেষ! মোট `{sent}`টি ভিডিও পাঠানো হয়েছে।")
        
    except errors.FloodWait as e:
        await bot_app.send_message(ADMIN_ID, f"⚠️ টেলিগ্রাম ব্লক করেছে! {e.value} সেকেন্ড অপেক্ষা করুন।")
    except Exception as e:
        await bot_app.send_message(ADMIN_ID, f"❌ ত্রুটি: {str(e)}")

# --- কমান্ড হ্যান্ডলার ---
@bot_app.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    try:
        # ইনপুট ফরম্যাট: /start_job -100123 1 50
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("সঠিকভাবে লিখুন: `/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা` \nউদা: `/start_job -1003219361602 1 50` ")
        
        chat_id = args[1]
        start_id = args[2]
        count = args[3]
        
        # ব্যাকগ্রাউন্ডে কাজ শুরু করা
        asyncio.create_task(process_videos(chat_id, start_id, count))
        await message.reply(f"⏳ প্রসেসিং শুরু হয়েছে। ভিডিও আইডি `{start_id}` থেকে `{count}`টি ভিডিও চেক করা হচ্ছে।")
        
    except Exception as e:
        await message.reply(f"❌ ভুল হয়েছে: {str(e)}")

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    await message.reply("🛠 **বট এখন ম্যানুয়াল মোডে সচল**\n\nভিডিও পাঠাতে লিখুন:\n`/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা`")

# --- ওয়েব সার্ভার (Koyeb Health Check) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Online (Manual Mode)!"

async def start_all():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট এখন ম্যানুয়াল মোডে অনলাইন!")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
    asyncio.get_event_loop().run_forever()
