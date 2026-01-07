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

# ক্লায়েন্ট সেটআপ
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DOWNLOAD_DIR = "downloads/"
if not os.path.exists(DOWNLOAD_DIR): 
    os.makedirs(DOWNLOAD_DIR)

# --- ভিডিও প্রসেসিং ফাংশন (সিরিয়াল ও স্টোরেজ সেফ মেথড) ---
async def process_videos(chat_input, start_id, count):
    sent = 0
    status_msg = None
    try:
        # ১. চ্যানেল ও টার্গেট বট রিজলভ করা (PEER_ID_INVALID ফিক্স)
        try:
            chat = await user_app.get_chat(chat_input)
            target_chat_id = chat.id
            target_bot = await user_app.get_chat(TARGET_BOT_USERNAME)
            target_bot_peer = target_bot.id
        except Exception as e:
            return await bot_app.send_message(ADMIN_ID, f"❌ আইডি রিজলভ এরর: {str(e)}\nনিশ্চিত হোন আপনার ইউজার আইডি ওই চ্যানেলে জয়েন করা আছে।")

        status_msg = await bot_app.send_message(ADMIN_ID, "⏳ কাজ শুরু হচ্ছে... আপনার জন্য লাইভ আপডেট এখানে দেওয়া হবে।")
        
        # ২. পুরাতন থেকে স্ক্যানিং লজিক
        async for message in user_app.get_chat_history(target_chat_id, offset_id=int(start_id), limit=1000):
            if sent >= int(count):
                break
            
            if message.video:
                current_count = sent + 1
                # লাইভ স্ট্যাটাস আপডেট
                await status_msg.edit_text(f"📥 **লাইভ স্ট্যাটাস:**\n🔢 প্রসেসিং: `{current_count}/{count}`\n🆔 ভিডিও আইডি: `{message.id}`\n📦 অবস্থা: ডাউনলোড হচ্ছে...")
                
                # ৩. ডাউনলোড (একবারে একটি ফাইল)
                file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                
                await status_msg.edit_text(f"📤 **লাইভ স্ট্যাটাস:**\n🔢 প্রসেসিং: `{current_count}/{count}`\n🆔 ভিডিও আইডি: `{message.id}`\n📦 অবস্থা: আপলোড হচ্ছে...")
                
                # ৪. আপনার আইডি হয়ে পাঠানো
                await user_app.send_video(target_bot_peer, video=file_path, caption=f"উৎস: {chat_input}\nভিডিও আইডি: {message.id}")
                
                # ৫. স্টোরেজ ক্লিয়ার (যাতে ফুল না হয়)
                if os.path.exists(file_path): 
                    os.remove(file_path)
                
                sent += 1
                # ৬. ফ্লাডওয়েট সুরক্ষা বিরতি
                await asyncio.sleep(40) 

        await bot_app.send_message(ADMIN_ID, f"✅ **মিশন সফল!**\nমোট `{sent}`টি ভিডিও পাঠানো হয়েছে। স্টোরেজ এখন সম্পূর্ণ খালি।")
        
    except errors.FloodWait as e:
        await bot_app.send_message(ADMIN_ID, f"⚠️ টেলিগ্রাম ব্লক করেছে! {e.value} সেকেন্ড পর নিজে থেকেই কাজ শুরু হবে।")
        await asyncio.sleep(e.value)
    except Exception as e:
        await bot_app.send_message(ADMIN_ID, f"❌ বড় ত্রুটি: {str(e)}")

# --- কমান্ড হ্যান্ডলার ---
@bot_app.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    try:
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("সঠিকভাবে লিখুন: `/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা` \n\nউদা: `/start_job -1003219361602 1 50` ")
        
        asyncio.create_task(process_videos(args[1], args[2], args[3]))
        await message.reply(f"⏳ প্রসেসিং রিকোয়েস্ট গ্রহণ করা হয়েছে।")
        
    except Exception as e:
        await message.reply(f"❌ ভুল ইনপুট: {str(e)}")

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    await message.reply("🛠 **ম্যানুয়াল কন্ট্রোল প্যানেল সচল**\n\nভিডিও পাঠাতে কমান্ড দিন:\n`/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা`")

# --- ওয়েব সার্ভার (Koyeb Health Check ফিক্স) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Health Check Passed! Storage Safe Serial Processing Active."

def run_web():
    app.run(host="0.0.0.0", port=8080) # ৮০৮০ পোরট নিশ্চিত করা

async def start_all():
    Thread(target=run_web).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট অনলাইন! আইডি ১ থেকে ভিডিও স্ক্যান করতে /start_job কমান্ড দিন।")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
    asyncio.get_event_loop().run_forever()
