import os, asyncio, random, shutil
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# --- কনফিগারেশন (Koyeb Env থেকে আসবে) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = "@Sami_bideshbot"

# ক্লায়েন্ট সেটআপ
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ডেটাবেস ও স্ট্যাটাস (রিস্টার্ট দিলে রিসেট হবে)
CHANNELS = []
CURRENT_CHANNEL_INDEX = 0
IS_PAUSED = False
TOTAL_SENT = 0

# মেমোরি খালি করার জন্য ডাউনলোড ফোল্ডার পরিষ্কার করা
if os.path.exists("downloads"):
    shutil.rmtree("downloads")
os.makedirs("downloads")

# --- ওয়েব সার্ভার (Health Check) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Active!"

def run_web(): app.run(host="0.0.0.0", port=8080)

# --- মূল লজিক (ডাউনলোড ও ফরোয়ার্ড) ---
async def auto_worker():
    global CURRENT_CHANNEL_INDEX, TOTAL_SENT, IS_PAUSED
    
    while True:
        if IS_PAUSED or not CHANNELS:
            await asyncio.sleep(30)
            continue
            
        current_target = CHANNELS[CURRENT_CHANNEL_INDEX]
        await bot_app.send_message(ADMIN_ID, f"🚀 কাজ শুরু: {current_target} থেকে ১০টি ভিডিও নেওয়া হচ্ছে...")
        
        sent_count = 0
        try:
            # শেষ থেকে শুরু করার জন্য get_chat_history
            async for message in user_app.get_chat_history(current_target, limit=100):
                if IS_PAUSED or sent_count >= 10:
                    break
                
                if message.video:
                    file_path = await user_app.download_media(message, file_name="downloads/")
                    await bot_app.send_video(TARGET_BOT, video=file_path, caption=f"From: {current_target}")
                    
                    # ফাইল ডিলিট করে মেমোরি খালি করা
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    sent_count += 1
                    TOTAL_SENT += 1
                    await asyncio.sleep(random.randint(60, 120)) # সেফটি ডিলে

            # পরবর্তী চ্যানেলে যাওয়ার লজিক
            CURRENT_CHANNEL_INDEX = (CURRENT_CHANNEL_INDEX + 1) % len(CHANNELS)
            
        except Exception as e:
            await bot_app.send_message(ADMIN_ID, f"❌ এরর ({current_target}): {str(e)}")
            CURRENT_CHANNEL_INDEX = (CURRENT_CHANNEL_INDEX + 1) % len(CHANNELS)

        await bot_app.send_message(ADMIN_ID, f"✅ ১০টি ভিডিও শেষ। পরবর্তী ১ ঘণ্টা বিরতি...")
        await asyncio.sleep(3600)

# --- অ্যাডমিন প্যানেল কমান্ডস ---
@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    buttons = [
        [InlineKeyboardButton("➕ চ্যানেল যোগ করুন", callback_data="add_ch"), InlineKeyboardButton("📜 চ্যানেল লিস্ট", callback_data="list_ch")],
        [InlineKeyboardButton("⏸ পজ", callback_data="pause"), InlineKeyboardButton("▶️ রিজুম", callback_data="resume")],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data="status"), InlineKeyboardButton("⚡ ফোর্স স্টার্ট", callback_data="force")]
    ]
    await message.reply("🛠 **এডমিন কন্ট্রোল প্যানেল**", reply_markup=InlineKeyboardMarkup(buttons))

@bot_app.on_callback_query()
async def handle_buttons(client, query):
    global IS_PAUSED, CHANNELS, TOTAL_SENT
    
    if query.data == "add_ch":
        await query.message.reply("চ্যানেল যোগ করতে লিখুন: `/add লিংক_বা_আইডি` \nউদাহরণ: `/add -10012345678` ")
    
    elif query.data == "list_ch":
        ch_list = "\n".join(CHANNELS) if CHANNELS else "কোনো চ্যানেল নেই।"
        await query.message.reply(f"📁 **আপনার চ্যানেলসমূহ:**\n{ch_list}")
    
    elif query.data == "status":
        status_text = "⏸ পজ করা" if IS_PAUSED else "▶️ চলছে"
        await query.answer(f"অবস্থা: {status_text}\nমোট পাঠানো হয়েছে: {TOTAL_SENT}টি", show_alert=True)
    
    elif query.data == "pause":
        IS_PAUSED = True
        await query.answer("বট পজ করা হয়েছে।")
    
    elif query.data == "resume":
        IS_PAUSED = False
        await query.answer("বট আবার চালু হয়েছে।")

@bot_app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_logic(client, message):
    try:
        new_ch = message.text.split(None, 1)[1]
        CHANNELS.append(new_ch)
        await message.reply(f"✅ {new_ch} লিস্টে যোগ করা হয়েছে।")
    except:
        await message.reply("ভুল ফরম্যাট! `/add link` এভাবে লিখুন।")

# --- বট স্টার্ট ---
async def start_all():
    Thread(target=run_web).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🤖 বট সচল হয়েছে! এখন /admin লিখে চ্যানেল যোগ করুন।")
    await auto_worker()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
