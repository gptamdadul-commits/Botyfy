import os, asyncio, shutil, json
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# --- কনফিগারেশন (Koyeb Env Variables থেকে আসবে) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = "@Sami_bideshbot"

# সেশন এবং বট ক্লায়েন্ট
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# বিরতি ভাঙার জন্য ইভেন্ট
force_event = asyncio.Event()
DB_FILE = "sent_videos.json"

# JSON ডাটাবেজ লোড
if os.path.exists(DB_FILE):
    try:
        with open(DB_FILE, "r") as f:
            SENT_DATA = json.load(f)
    except:
        SENT_DATA = {}
else:
    SENT_DATA = {}

db = {
    "CHANNELS": [],
    "CURRENT_INDEX": 0,
    "IS_PAUSED": False,
    "TOTAL_SENT": 0,
    "HOURLY_LIMIT": 10,
    "SLEEP_GAP": 3600,   # ১ ঘণ্টা বিরতি
    "VIDEO_DELAY": 60,   # ভিডিওর মাঝখানের গ্যাপ
    "STATUS": "অপেক্ষা করছে ⏳"
}

DOWNLOAD_DIR = "downloads/"
if not os.path.exists(DOWNLOAD_DIR): 
    os.makedirs(DOWNLOAD_DIR)

# ডাটা সেভ করার ফাংশন
def save_data():
    with open(DB_FILE, "w") as f:
        json.dump(SENT_DATA, f)

# --- মূল অটোমেশন লজিক (পুরাতন থেকে নতুন) ---
async def auto_worker():
    while True:
        if db["IS_PAUSED"] or not db["CHANNELS"]:
            db["STATUS"] = "বন্ধ অথবা কোনো চ্যানেল নেই ⏸"
            await asyncio.sleep(10)
            continue
            
        current_target = db["CHANNELS"][db["CURRENT_INDEX"]]
        db["STATUS"] = f"পুরাতন ভিডিও স্ক্যান করা হচ্ছে: {current_target} 🔍"
        
        if current_target not in SENT_DATA:
            SENT_DATA[current_target] = []
            save_data()

        sent_count = 0
        try:
            # এরর এড়াতে offset_id ব্যবহার করে আইডি ১ থেকে পড়া শুরু করবে
            # Pyrogram এর get_chat_history তে offset_id ১ দিলে এটি শুরু থেকে মেসেজ পায়
            async for message in user_app.get_chat_history(current_target, offset_id=1, limit=100):
                if db["IS_PAUSED"] or sent_count >= db["HOURLY_LIMIT"]:
                    break
                
                # ভিডিও চেক এবং JSON এ ডুপ্লিকেট চেক
                if message.video and str(message.id) not in SENT_DATA[current_target]:
                    db["STATUS"] = f"ডাউনলোড শুরু: {sent_count + 1}/{db['HOURLY_LIMIT']} 📥"
                    
                    file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                    
                    # ইউজার আইডি থেকে পাঠানো যাতে বট-টু-বট এরর না আসে
                    await user_app.send_video(
                        TARGET_BOT, 
                        video=file_path, 
                        caption=f"✅ সফলভাবে সংগৃহীত\nউৎস: {current_target}\nভিডিও আইডি: {message.id}"
                    )
                    
                    # মেমোরি খালি করতে ফাইল ডিলিট
                    if os.path.exists(file_path): 
                        os.remove(file_path)
                    
                    # আইডি সেভ করা
                    SENT_DATA[current_target].append(str(message.id))
                    save_data()
                    
                    sent_count += 1
                    db["TOTAL_SENT"] += 1
                    await asyncio.sleep(db["VIDEO_DELAY"]) # ভিডিওর মাঝখানের গ্যাপ

            db["CURRENT_INDEX"] = (db["CURRENT_INDEX"] + 1) % len(db["CHANNELS"])
            
        except Exception as e:
            await bot_app.send_message(ADMIN_ID, f"❌ ত্রুটি ({current_target}): {str(e)}")
            db["CURRENT_INDEX"] = (db["CURRENT_INDEX"] + 1) % len(db["CHANNELS"])

        db["STATUS"] = f"রাউন্ড শেষ। পরবর্তী কাজ {db['SLEEP_GAP']//60} মিনিট পর 😴"
        try:
            await asyncio.wait_for(force_event.wait(), timeout=db["SLEEP_GAP"])
        except asyncio.TimeoutError:
            pass
        finally:
            force_event.clear()

# --- অ্যাডমিন প্যানেল বাটনসমূহ ---
def admin_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ চ্যানেল যোগ", callback_data="add_ch"), InlineKeyboardButton("📜 লিস্ট ও ডিলিট", callback_data="list_ch")],
        [InlineKeyboardButton("📊 লাইভ স্ট্যাটাস", callback_data="status"), InlineKeyboardButton("⚡ ফোর্স স্টার্ট", callback_data="force")],
        [InlineKeyboardButton("⏸ পজ", callback_data="pause"), InlineKeyboardButton("▶️ রিজুম", callback_data="resume")]
    ])

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    await message.reply("🛠 **বট কন্ট্রোল প্যানেল**\n(Oldest First Mode সচল)", reply_markup=admin_markup())

@bot_app.on_callback_query()
async def cb_handler(client, query):
    if query.data == "status":
        txt = f"📈 **বট লাইভ রিপোর্ট:**\n\n🔹 অবস্থা: {db['STATUS']}\n🔹 মোট পাঠানো: {db['TOTAL_SENT']}টি\n🔹 ডাটাবেজে সেভড ভিডিও: {sum(len(v) for v in SENT_DATA.values())}টি"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))
    elif query.data == "force":
        force_event.set()
        await query.answer("⚡ ফোর্স স্টার্ট! বিরতি ভাঙা হয়েছে।", show_alert=True)
    elif query.data == "back":
        await query.message.edit_text("🛠 **বট কন্ট্রোল প্যানেল**", reply_markup=admin_markup())
    elif query.data == "pause": 
        db["IS_PAUSED"] = True
        await query.answer("পজ করা হয়েছে।")
    elif query.data == "resume": 
        db["IS_PAUSED"] = False
        await query.answer("রিজুম করা হয়েছে।")
    elif query.data == "add_ch":
        await query.message.reply("চ্যানেল আইডি যোগ করতে লিখুন: `/add -100xxxxxxx` ")
    elif query.data == "list_ch":
        res = "\n".join([f"• `{ch}`" for ch in db['CHANNELS']]) if db['CHANNELS'] else "কোনো চ্যানেল নেই।"
        await query.message.edit_text(f"📁 **চ্যানেল তালিকা:**\n{res}\n\nডিলিট করতে: `/del আইডি`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))

@bot_app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_ch_logic(client, message):
    try:
        ch = message.text.split(None, 1)[1]
        if ch not in db["CHANNELS"]:
            db["CHANNELS"].append(ch)
            if ch not in SENT_DATA:
                SENT_DATA[ch] = []
                save_data()
            await message.reply(f"✅ সফলভাবে যোগ হয়েছে: `{ch}`")
        else: await message.reply("⚠️ চ্যানেলটি আগে থেকেই আছে।")
    except: await message.reply("❌ ভুল হয়েছে। উদা: `/add -10012345678` ")

@bot_app.on_message(filters.command("del") & filters.user(ADMIN_ID))
async def del_ch_logic(client, message):
    try:
        ch = message.text.split(None, 1)[1]
        if ch in db["CHANNELS"]:
            db["CHANNELS"].remove(ch)
            await message.reply(f"🗑 মুছে ফেলা হয়েছে: `{ch}`")
    except: await message.reply("❌ সঠিক আইডি দিন।")

# --- ওয়েব সার্ভার ও রানার ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Online (Oldest First Mode)!"
def run_web(): app.run(host="0.0.0.0", port=8080)

async def start_all():
    Thread(target=run_web).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট অনলাইন! এটি পুরাতন ভিডিও থেকে ডাউনলোড শুরু করবে।")
    await auto_worker()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
