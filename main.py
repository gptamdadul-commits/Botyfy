import os, asyncio, shutil, json
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# --- কনফিগারেশন (Koyeb Env Variables) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = "@Sami_bideshbot"

# ক্লায়েন্ট সেটআপ
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# বিরতি ভাঙার জন্য ইভেন্ট সিস্টেম
force_event = asyncio.Event()
DB_FILE = "sent_videos.json"

# JSON ডাটাবেজ লোড
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r") as f:
            SENT_DATA = json.load(f)
    except: SENT_DATA = {}
else: SENT_DATA = {}

# ডাইনামিক ডাটাবেজ
db = {
    "CHANNELS": [],
    "CURRENT_INDEX": 0,
    "IS_PAUSED": False,
    "TOTAL_SENT": 0,
    "HOURLY_LIMIT": 10,
    "SLEEP_GAP": 3600,
    "VIDEO_DELAY": 60,
    "STATUS": "অপেক্ষা করছে ⏳"
}

DOWNLOAD_DIR = "downloads/"
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

def save_data():
    with open(DB_FILE, "w") as f:
        json.dump(SENT_DATA, f)

# --- মূল অটোমেশন লজিক (পুরাতন থেকে নতুন) ---
async def auto_worker():
    while True:
        if db["IS_PAUSED"] or not db["CHANNELS"]:
            db["STATUS"] = "বন্ধ অথবা কোনো চ্যানেল নেই ⏸"
            await asyncio.sleep(5)
            continue
            
        current_target = db["CHANNELS"][db["CURRENT_INDEX"]]
        db["STATUS"] = f"পুরাতন ভিডিও স্ক্যান করা হচ্ছে: {current_target} 🔍"
        
        if current_target not in SENT_DATA:
            SENT_DATA[current_target] = []
            save_data()

        sent_count = 0
        try:
            # offset_id=1 ব্যবহার করে প্রথম মেসেজ থেকে শুরু করা
            async for message in user_app.get_chat_history(current_target, offset_id=1, limit=500):
                if db["IS_PAUSED"] or sent_count >= db["HOURLY_LIMIT"]:
                    break
                
                # ডুপ্লিকেট চেক (একই ফাইল বারবার ডাওনলোড হবে না)
                if message.video and str(message.id) not in SENT_DATA[current_target]:
                    db["STATUS"] = f"ডাউনলোড হচ্ছে: {sent_count + 1}/{db['HOURLY_LIMIT']} 📥 (ID: {message.id})"
                    
                    file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                    # ইউজার সেশন ব্যবহার করে পাঠানো যাতে [400 USER_IS_BOT] না আসে
                    await user_app.send_video(TARGET_BOT, video=file_path, caption=f"✅ সফল\nউৎস: {current_target}\nআইডি: {message.id}")
                    
                    if os.path.exists(file_path): os.remove(file_path) # মেমোরি ক্লিয়ার
                    
                    SENT_DATA[current_target].append(str(message.id))
                    save_data()
                    
                    sent_count += 1
                    db["TOTAL_SENT"] += 1
                    await asyncio.sleep(db["VIDEO_DELAY"]) 

            db["CURRENT_INDEX"] = (db["CURRENT_INDEX"] + 1) % len(db["CHANNELS"])
            
        except Exception as e:
            await bot_app.send_message(ADMIN_ID, f"❌ ত্রুটি ({current_target}): {str(e)}")
            db["CURRENT_INDEX"] = (db["CURRENT_INDEX"] + 1) % len(db["CHANNELS"])

        db["STATUS"] = f"পরবর্তী রাউন্ডের জন্য অপেক্ষা করছে ({db['SLEEP_GAP']//60} মিনিট) ⏳"
        try:
            # ফোর্স স্টার্ট ইভেন্টের জন্য অপেক্ষা
            await asyncio.wait_for(force_event.wait(), timeout=db["SLEEP_GAP"])
        except asyncio.TimeoutError:
            pass
        finally:
            force_event.clear()

# --- অ্যাডমিন প্যানেল ---
def main_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ চ্যানেল যোগ", callback_data="add_ch"), InlineKeyboardButton("🗑 চ্যানেল ডিলিট", callback_data="del_ch")],
        [InlineKeyboardButton("📊 লাইভ স্ট্যাটাস", callback_data="status"), InlineKeyboardButton("⚡ ফোর্স স্টার্ট", callback_data="force")],
        [InlineKeyboardButton("⚙️ সেটিংস এডিট", callback_data="settings"), InlineKeyboardButton("📜 লিস্ট", callback_data="list_ch")],
        [InlineKeyboardButton("⏸ পজ", callback_data="pause"), InlineKeyboardButton("▶️ রিজুম", callback_data="resume")]
    ])

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    await message.reply("🛠 **বট কন্ট্রোল প্যানেল (ফিক্সড ভার্সন)**", reply_markup=main_markup())

@bot_app.on_callback_query()
async def cb_handler(client, query):
    if query.data == "status":
        txt = f"📈 **বট রিপোর্ট:**\n\n🔹 অবস্থা: {db['STATUS']}\n🔹 মোট পাঠানো: {db['TOTAL_SENT']}টি\n🔹 লিমিট: ঘণ্টায় {db['HOURLY_LIMIT']}টি\n🔹 গ্যাপ: {db['VIDEO_DELAY']} সেকেন্ড"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))
    
    elif query.data == "force":
        force_event.set() # স্লিপ ভেঙে কাজ শুরু
        await query.answer("⚡ ফোর্স স্টার্ট! বিরতি ভাঙা হয়েছে।", show_alert=True)
    
    elif query.data == "settings":
        txt = "⚙️ **সেটিংস কমান্ডসমূহ:**\n\n• `/limit 10` (ঘণ্টায় ভিডিও সংখ্যা)\n• `/delay 60` (ভিডিওর মাঝের গ্যাপ)\n• `/gap 60` (পরবর্তী রাউন্ডের বিরতি মিনিটে)"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))

    elif query.data == "list_ch":
        res = "\n".join([f"• `{ch}`" for ch in db['CHANNELS']]) if db['CHANNELS'] else "কোনো চ্যানেল নেই।"
        await query.message.edit_text(f"📁 **চ্যানেল তালিকা:**\n{res}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))
    
    elif query.data == "add_ch":
        await query.message.reply("চ্যানেল আইডি যোগ করতে লিখুন: `/add -100xxxxxxx` ")
    
    elif query.data == "del_ch":
        await query.message.reply("চ্যানেল ডিলিট করতে লিখুন: `/del -100xxxxxxx` ")

    elif query.data == "back":
        await query.message.edit_text("🛠 **বট কন্ট্রোল প্যানেল (ফিক্সড ভার্সন)**", reply_markup=main_markup())
    
    elif query.data == "pause": db["IS_PAUSED"] = True; await query.answer("কাজ বন্ধ।")
    elif query.data == "resume": db["IS_PAUSED"] = False; await query.answer("কাজ চালু।")

# --- কমান্ড হ্যান্ডলারস (চ্যানেল যোগ/ডিলিট ও সেটিংস) ---
@bot_app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_logic(client, message):
    try:
        ch = message.text.split()[1]
        if ch not in db["CHANNELS"]:
            db["CHANNELS"].append(ch)
            await message.reply(f"✅ চ্যানেল যোগ হয়েছে: `{ch}`")
        else: await message.reply("⚠️ এই চ্যানেল আগে থেকেই আছে।")
    except: await message.reply("উদা: `/add -100xxxxxx` ")

@bot_app.on_message(filters.command("del") & filters.user(ADMIN_ID))
async def del_logic(client, message):
    try:
        ch = message.text.split()[1]
        if ch in db["CHANNELS"]:
            db["CHANNELS"].remove(ch)
            await message.reply(f"🗑 ডিলিট করা হয়েছে: `{ch}`")
    except: await message.reply("উদা: `/del -100xxxxxx` ")

@bot_app.on_message(filters.command(["limit", "delay", "gap"]) & filters.user(ADMIN_ID))
async def update_settings(client, message):
    try:
        val = int(message.text.split()[1])
        if "limit" in message.text: db["HOURLY_LIMIT"] = val
        elif "delay" in message.text: db["VIDEO_DELAY"] = val
        elif "gap" in message.text: db["SLEEP_GAP"] = val * 60
        await message.reply(f"⚙️ সেটিংস আপডেট হয়েছে: {val}")
    except: await message.reply("সঠিক সংখ্যা দিন।")

# --- ওয়েব সার্ভার ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Online and Healthy!"

async def start_all():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট অনলাইন! সব ফিচার ফিক্স করা হয়েছে।")
    await auto_worker()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
