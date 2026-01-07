import os, asyncio, shutil, json
from pyrogram import Client, filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# --- কনফিগারেশন ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = "@Sami_bideshbot"

# ক্লায়েন্ট সেটআপ
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
    except: SENT_DATA = {}
else: SENT_DATA = {}

db = {
    "CHANNELS": [],
    "CURRENT_INDEX": 0,
    "IS_PAUSED": False,
    "TOTAL_SENT": 0,
    "HOURLY_LIMIT": 10,
    "SLEEP_GAP": 3600,
    "VIDEO_DELAY": 30, # FloodWait এড়াতে ডিলে বাড়ানো হয়েছে
    "STATUS": "চালু হচ্ছে... 🚀"
}

DOWNLOAD_DIR = "downloads/"
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

def save_data():
    with open(DB_FILE, "w") as f:
        json.dump(SENT_DATA, f)

# --- মূল অটোমেশন লজিক (Error-Proof) ---
async def auto_worker():
    while True:
        if db["IS_PAUSED"] or not db["CHANNELS"]:
            db["STATUS"] = "বন্ধ অথবা কোনো চ্যানেল নেই ⏸"
            await asyncio.sleep(10)
            continue
            
        current_target = db["CHANNELS"][db["CURRENT_INDEX"]]
        db["STATUS"] = f"পুরাতন ভিডিও স্ক্যান করছে: {current_target} 🔍"
        
        if current_target not in SENT_DATA:
            SENT_DATA[current_target] = []
            save_data()

        sent_count = 0
        try:
            # PEER_ID_INVALID সমাধান করতে আগে জয়েন চেক করা
            try:
                await user_app.join_chat(current_target)
            except: pass 

            # আইডি ১ থেকে স্ক্যান শুরু (পুরাতন থেকে নতুন)
            async for message in user_app.get_chat_history(current_target, offset_id=1, limit=500):
                if db["IS_PAUSED"] or sent_count >= db["HOURLY_LIMIT"]:
                    break
                
                if message.video and str(message.id) not in SENT_DATA[current_target]:
                    db["STATUS"] = f"ডাউনলোড: {sent_count + 1}/{db['HOURLY_LIMIT']} 📥 (ID: {message.id})"
                    
                    file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                    await user_app.send_video(TARGET_BOT, video=file_path, caption=f"✅ সফল\nউৎস: {current_target}")
                    
                    if os.path.exists(file_path): os.remove(file_path)
                    
                    SENT_DATA[current_target].append(str(message.id))
                    save_data()
                    
                    sent_count += 1
                    db["TOTAL_SENT"] += 1
                    await asyncio.sleep(db["VIDEO_DELAY"]) 

            db["CURRENT_INDEX"] = (db["CURRENT_INDEX"] + 1) % len(db["CHANNELS"])
            
        except errors.FloodWait as e:
            db["STATUS"] = f"টেলিগ্রাম ব্লক করেছে! {e.value}s অপেক্ষা করুন ⏳"
            await asyncio.sleep(e.value) # FloodWait হ্যান্ডলিং
        except Exception as e:
            db["STATUS"] = f"ত্রুটি: {str(e)[:50]}"
            await bot_app.send_message(ADMIN_ID, f"❌ ত্রুটি ({current_target}): {str(e)}")
            db["CURRENT_INDEX"] = (db["CURRENT_INDEX"] + 1) % len(db["CHANNELS"])

        db["STATUS"] = f"অপেক্ষা করছে ({db['SLEEP_GAP']//60} মিনিট) ⏳"
        try:
            await asyncio.wait_for(force_event.wait(), timeout=db["SLEEP_GAP"])
        except asyncio.TimeoutError: pass
        finally: force_event.clear()

# --- অ্যাডমিন প্যানেল ---
def main_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ যোগ", callback_data="add_ch"), InlineKeyboardButton("🗑 ডিলিট", callback_data="del_ch")],
        [InlineKeyboardButton("📊 স্ট্যাটাস", callback_data="status"), InlineKeyboardButton("⚡ ফোর্স স্টার্ট", callback_data="force")],
        [InlineKeyboardButton("⚙️ সেটিংস", callback_data="settings"), InlineKeyboardButton("📜 লিস্ট", callback_data="list_ch")],
        [InlineKeyboardButton("⏸ পজ", callback_data="pause"), InlineKeyboardButton("▶️ রিজুম", callback_data="resume")]
    ])

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    await message.reply("🛠 **অ্যাডভান্সড বট কন্ট্রোল প্যানেল**", reply_markup=main_markup())

@bot_app.on_callback_query()
async def cb_handler(client, query):
    if query.data == "status":
        txt = f"📊 **বট স্ট্যাটাস:**\n\n🔹 অবস্থা: {db['STATUS']}\n🔹 মোট পাঠানো: {db['TOTAL_SENT']}টি\n🔹 গ্যাপ: {db['VIDEO_DELAY']}s"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))
    elif query.data == "force":
        force_event.set()
        await query.answer("⚡ ফোর্স স্টার্ট সচল!", show_alert=True)
    elif query.data == "settings":
        txt = "⚙️ **কমান্ড:**\n\n`/limit 10` (ঘণ্টায় ভিডিও)\n`/delay 60` (ভিডিও গ্যাপ)\n`/gap 60` (বিরতি মিনিটে)"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))
    elif query.data == "back":
        await query.message.edit_text("🛠 **বট কন্ট্রোল প্যানেল**", reply_markup=main_markup())
    elif query.data == "pause": db["IS_PAUSED"] = True; await query.answer("বন্ধ।")
    elif query.data == "resume": db["IS_PAUSED"] = False; await query.answer("চালু।")
    elif query.data == "add_ch": await query.message.reply("লিখুন: `/add -100xxxxxx` ")
    elif query.data == "del_ch": await query.message.reply("লিখুন: `/del -100xxxxxx` ")
    elif query.data == "list_ch":
        res = "\n".join([f"• `{ch}`" for ch in db['CHANNELS']]) if db['CHANNELS'] else "খালি।"
        await query.message.edit_text(f"📁 **লিস্ট:**\n{res}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))

@bot_app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_logic(client, message):
    try:
        ch = message.text.split()[1]
        if ch not in db["CHANNELS"]: db["CHANNELS"].append(ch); await message.reply("✅ যোগ হয়েছে।")
    except: await message.reply("ভুল ফরম্যাট।")

@bot_app.on_message(filters.command("del") & filters.user(ADMIN_ID))
async def del_logic(client, message):
    try:
        ch = message.text.split()[1]
        if ch in db["CHANNELS"]: db["CHANNELS"].remove(ch); await message.reply("🗑 মুছে ফেলা হয়েছে।")
    except: await message.reply("ভুল ফরম্যাট।")

@bot_app.on_message(filters.command(["limit", "delay", "gap"]) & filters.user(ADMIN_ID))
async def settings_update(client, message):
    try:
        val = int(message.text.split()[1])
        if "limit" in message.text: db["HOURLY_LIMIT"] = val
        elif "delay" in message.text: db["VIDEO_DELAY"] = val
        elif "gap" in message.text: db["SLEEP_GAP"] = val * 60
        await message.reply(f"⚙️ আপডেট হয়েছে: {val}")
    except: await message.reply("সঠিক সংখ্যা দিন।")

# --- ওয়েব সার্ভার ও হেলথ চেক ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Healthy!"

async def start_all():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট সচল হয়েছে! সব এরর হ্যান্ডলিং যোগ করা হয়েছে।")
    await auto_worker()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
