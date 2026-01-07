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
TARGET_BOT_USERNAME = "@Sami_bideshbot"

# সেশন এবং বট ক্লায়েন্ট
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DOWNLOAD_DIR = "downloads/"
if not os.path.exists(DOWNLOAD_DIR): 
    os.makedirs(DOWNLOAD_DIR)

# --- ভিডিও প্রসেসিং ফাংশন (PEER_ID_INVALID ফিক্স সহ) ---
async def process_videos(chat_input, start_id, count):
    sent = 0
    try:
        # চ্যানেল রিজলভ করার চেষ্টা (এরর ফিক্স)
        try:
            chat = await user_app.get_chat(chat_input)
            target_chat_id = chat.id
        except Exception:
            # যদি আইডি সরাসরি কাজ না করে তবে পূর্ণ আইডি ফরম্যাট নিশ্চিত করা
            if isinstance(chat_input, str) and not chat_input.startswith("-100"):
                target_chat_id = int("-100" + chat_input.replace("-", ""))
            else:
                target_chat_id = chat_input

        # টার্গেট বটকে রিজলভ করা (USERNAME_INVALID ফিক্স)
        try:
            target_bot_chat = await user_app.get_chat(TARGET_BOT_USERNAME)
            target_bot_peer = target_bot_chat.id
        except:
            target_bot_peer = TARGET_BOT_USERNAME

        await bot_app.send_message(ADMIN_ID, f"🚀 কাজ শুরু!\nচ্যানেল: `{chat_input}`\nআইডি `{start_id}` থেকে `{count}`টি ভিডিও খোঁজা হচ্ছে।")
        
        # পুরাতন আইডি থেকে নির্দিষ্ট রেঞ্জ অনুযায়ী স্ক্যান
        async for message in user_app.get_chat_history(target_chat_id, offset_id=int(start_id), limit=500):
            if sent >= int(count):
                break
            
            if message.video:
                # আপনার ইউজার আইডি হয়ে ভিডিও পাঠানো
                file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                await user_app.send_video(target_bot_peer, video=file_path, caption=f"উৎস: {chat_input}\nআইডি: {message.id}")
                
                if os.path.exists(file_path): 
                    os.remove(file_path) # মেমোরি ক্লিয়ার
                
                sent += 1
                await asyncio.sleep(40) # FloodWait থেকে বাঁচতে ডিলে

        await bot_app.send_message(ADMIN_ID, f"✅ কাজ সম্পন্ন!\nমোট `{sent}`টি ভিডিও পাঠানো হয়েছে।")
        
    except errors.FloodWait as e:
        await bot_app.send_message(ADMIN_ID, f"⏳ টেলিগ্রাম ব্লক করেছে! {e.value} সেকেন্ড পর আবার ট্রাই করুন।")
    except Exception as e:
        await bot_app.send_message(ADMIN_ID, f"❌ ত্রুটি: {str(e)}")

# --- কমান্ড হ্যান্ডলার ---
@bot_app.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    try:
        # /start_job -1003219361602 1 50
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("সঠিকভাবে লিখুন: `/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা` \nউদা: `/start_job -1003219361602 1 50` ")
        
        asyncio.create_task(process_videos(args[1], args[2], args[3]))
        await message.reply(f"⏳ প্রসেসিং শুরু হয়েছে।")
        
    except Exception as e:
        await message.reply(f"❌ ভুল: {str(e)}")

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    await message.reply("🛠 **ম্যানুয়াল কন্ট্রোল প্যানেল**\n\nকমান্ড ফরম্যাট:\n`/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা`")

# --- ওয়েব সার্ভার ও হেলথ চেক (Koyeb Stop হওয়া রোধ করতে) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Healthy and Manual Mode Active!"

def run_web():
    app.run(host="0.0.0.0", port=8080) # পোরট ৮০৮০

async def start_all():
    Thread(target=run_web).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট অনলাইন! আইডি ১ থেকে ভিডিও স্ক্যান করতে /start_job কমান্ড দিন।")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
    asyncio.get_event_loop().run_forever()
