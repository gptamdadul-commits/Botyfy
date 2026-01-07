import os, asyncio, shutil, json
from pyrogram import Client, filters, errors
from flask import Flask
from threading import Thread

# --- কনফিগারেশন (Koyeb Env Variables) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT_USERNAME = "Sami_bideshbot" # এখানে @ ছাড়া ইউজারনেম ব্যবহার করা হয়েছে

# ক্লায়েন্ট সেটআপ
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DOWNLOAD_DIR = "downloads/"
if not os.path.exists(DOWNLOAD_DIR): 
    os.makedirs(DOWNLOAD_DIR)

# --- ভিডিও প্রসেসিং ফাংশন (সিরিয়াল ও স্টোরেজ সেফ) ---
async def process_videos(chat_input, start_id, count):
    sent = 0
    status_msg = None
    try:
        # চ্যানেল/গ্রুপ রিজলভ
        chat = await user_app.get_chat(chat_input)
        target_chat_id = chat.id
        
        # বটের সঠিক peer input ফরম্যাট (সবচেয়ে নিরাপদ উপায়)
        target_bot_input = f"@{TARGET_BOT_USERNAME}" if not TARGET_BOT_USERNAME.startswith('@') else TARGET_BOT_USERNAME
        
        # বটকে রিজলভ করা + সঠিক peer পাওয়া
        bot_chat = await user_app.get_chat(target_bot_input)
        target_peer = bot_chat.id   # এটাই সঠিক peer id হবে (negative হলেও pyrogram হ্যান্ডেল করে)

        status_msg = await bot_app.send_message(ADMIN_ID, "⏳ কাজ শুরু হচ্ছে... লাইভ আপডেট এখানে দেখুন।")
        
        # ২. পুরাতন আইডি থেকে স্ক্যানিং
        async for message in user_app.get_chat_history(target_chat_id, offset_id=int(start_id), limit=1000):
            if sent >= int(count):
                break
            
            if message.video:
                current_count = sent + 1
                # লাইভ স্ট্যাটাস আপডেট
                await status_msg.edit_text(f"📥 **প্রসেসিং: {current_count}/{count}**\n🆔 আইডি: `{message.id}`\n📦 অবস্থা: ডাউনলোড হচ্ছে...")
                
                # ৩. ভিডিও ডাউনলোড (স্টোরেজ সেফ)
                file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                
                await status_msg.edit_text(f"📤 **প্রসেসিং: {current_count}/{count}**\n🆔 আইডি: `{message.id}`\n📦 অবস্থা: আপলোড হচ্ছে...")
                
                # ৪. আপনার ইউজার আইডি হয়ে ভিডিও পাঠানো
                await user_app.send_video(target_peer, video=file_path, caption=f"উৎস: {chat_input}\nভিডিও আইডি: {message.id}")
                
                # ৫. প্রসেসিং শেষে সাথে সাথে ডিলিট
                if os.path.exists(file_path): 
                    os.remove(file_path)
                
                sent += 1
                # ৬. ফ্লাডওয়েট সুরক্ষা
                await asyncio.sleep(45) 

        await bot_app.send_message(ADMIN_ID, f"✅ **মিশন সম্পন্ন!**\nমোট পাঠানো হয়েছে: `{sent}`টি ভিডিও। স্টোরেজ সম্পূর্ণ খালি।")
        
    except errors.PeerIdInvalid:
        await bot_app.send_message(ADMIN_ID, "❌ PeerIdInvalid\nবটের ইউজারনেম ঠিক আছে কিনা আবার চেক করুন")
    except errors.FloodWait as e:
        await bot_app.send_message(ADMIN_ID, f"⚠️ ফ্লাডওয়েট: {e.value} সেকেন্ড পর নিজে থেকেই শুরু হবে।")
        await asyncio.sleep(e.value)
    except Exception as e:
        await bot_app.send_message(ADMIN_ID, f"❌ অপ্রত্যাশিত ত্রুটি:\n{type(e).__name__}\n{str(e)}")

# --- কমান্ড হ্যান্ডলার ---
@bot_app.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    try:
        # ফরম্যাট: /start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("সঠিক ফরম্যাট: `/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা` ")
        
        asyncio.create_task(process_videos(args[1], args[2], args[3]))
        await message.reply(f"⏳ প্রসেসিং রিকোয়েস্ট গ্রহণ করা হয়েছে।")
        
    except Exception as e:
        await message.reply(f"❌ ভুল: {str(e)}")

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    await message.reply("🛠 **ম্যানুয়াল কন্ট্রোল প্যানেল**\n\nকমান্ড ফরম্যাট:\n`/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা`")

# --- ওয়েব সার্ভার (Koyeb Health Check ফিক্স) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Healthy and Active!"

async def start_all():
    # Flask ওয়েব সার্ভার আলাদা থ্রেডে চালু করা
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট অনলাইন! নতুন সেশন সফলভাবে কাজ করছে।")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
    asyncio.get_event_loop().run_forever()
