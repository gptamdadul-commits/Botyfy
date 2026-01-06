import os, asyncio, random, shutil, time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# --- কনফিগারেশন ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = "@Sami_bideshbot" # আপনার টার্গেট বট

# ক্লায়েন্ট সেটআপ
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# বিরতি ভাঙার জন্য ইভেন্ট
force_event = asyncio.Event()

# ডেটাবেস ও সেটিংস
db = {
    "CHANNELS": [],
    "CURRENT_INDEX": 0,
    "IS_PAUSED": False,
    "TOTAL_SENT": 0,
    "HOURLY_LIMIT": 10,
    "SLEEP_GAP": 3600,
    "VIDEO_DELAY": 60,
    "STATUS": "বিশ্রাম নিচ্ছে 😴"
}

DOWNLOAD_DIR = "downloads/"
if os.path.exists(DOWNLOAD_DIR):
    shutil.rmtree(DOWNLOAD_DIR)
os.makedirs(DOWNLOAD_DIR)

# --- ওয়েব সার্ভার ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Active!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

# --- মূল অটোমেশন লজিক ---
async def auto_worker():
    while True:
        if db["IS_PAUSED"] or not db["CHANNELS"]:
            db["STATUS"] = "বন্ধ আছে (Paused/No Channel) ⏸"
            await asyncio.sleep(10)
            continue
            
        current_target = db["CHANNELS"][db["CURRENT_INDEX"]]
        db["STATUS"] = f"ভিডিও পাঠানো হচ্ছে... (উৎস: {current_target}) 📥"
        await bot_app.send_message(ADMIN_ID, f"🚀 কাজ শুরু: {current_target} থেকে ভিডিও নেওয়া হচ্ছে...")
        
        sent_in_loop = 0
        try:
            # শেষ থেকে শুরু করার লজিক
            async for message in user_app.get_chat_history(current_target, limit=100):
                if db["IS_PAUSED"] or sent_in_loop >= db["HOURLY_LIMIT"]:
                    break
                
                if message.video:
                    db["STATUS"] = f"প্রসেসিং: {sent_in_loop + 1}/{db['HOURLY_LIMIT']} 📥"
                    
                    # ভিডিও ডাউনলোড
                    file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                    
                    # আপনার ইউজার আইডি ব্যবহার করে অন্য বটে পাঠানো (যাতে [400 USER_IS_BOT] এরর না আসে)
                    await user_app.send_video(TARGET_BOT, video=file_path, caption=f"উৎস: {current_target}")
                    
                    # ফাইল ডিলিট করে মেমোরি খালি করা
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    sent_in_loop += 1
                    db["TOTAL_SENT"] += 1
                    await asyncio.sleep(db["VIDEO_DELAY"]) 

            db["CURRENT_INDEX"] = (db["CURRENT_INDEX"] + 1) % len(db["CHANNELS"])
            
        except Exception as e:
            await bot_app.send_message(ADMIN_ID, f"❌ এরর ({current_target}): {str(e)}")
            db["CURRENT_INDEX"] = (db["CURRENT_INDEX"] + 1) % len(db["CHANNELS"])

        db["STATUS"] = f"পরবর্তী রাউন্ডের জন্য অপেক্ষা করছে ({db['SLEEP_GAP']//60} মিনিট) ⏳"
        
        try:
            await asyncio.wait_for(force_event.wait(), timeout=db["SLEEP_GAP"])
        except asyncio.TimeoutError:
            pass
        finally:
            force_event.clear()

# --- অ্যাডমিন প্যানেল বাটনসমূহ ---
def get_admin_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ চ্যানেল যোগ", callback_data="add_ch"), InlineKeyboardButton("🗑 চ্যানেল ডিলিট", callback_data="del_ch")],
        [InlineKeyboardButton("📊 লাইভ স্ট্যাটাস", callback_data="status"), InlineKeyboardButton("📜 লিস্ট", callback_data="list_ch")],
        [InlineKeyboardButton("⏸ পজ", callback_data="pause"), InlineKeyboardButton("▶️ রিজুম", callback_data="resume")],
        [InlineKeyboardButton("⚙️ সেটিংস এডিট", callback_data="settings")],
        [InlineKeyboardButton("⚡ ফোর্স স্টার্ট", callback_data="force")]
    ])

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_cmd(client, message):
    await message.reply("🛠 **অ্যাডভান্সড অ্যাডমিন প্যানেল**", reply_markup=get_admin_markup())

@bot_app.on_callback_query()
async def cb_handler(client, query):
    data = query.data
    if data == "status":
        txt = f"📈 **বট লাইভ স্ট্যাটাস:**\n\n🔹 অবস্থা: {db['STATUS']}\n🔹 মোট পাঠানো: {db['TOTAL_SENT']}টি\n🔹 লিমিট: ঘণ্টায় {db['HOURLY_LIMIT']}টি\n🔹 বিরতি: {db['VIDEO_DELAY']} সেকেন্ড"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))
    
    elif data == "list_ch":
        res = "\n".join([f"{i+1}. {ch}" for i, ch in enumerate(db['CHANNELS'])]) if db['CHANNELS'] else "কোনো চ্যানেল নেই।"
        await query.message.edit_text(f"📁 **চ্যানেল তালিকা:**\n{res}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))

    elif data == "settings":
        txt = "সেটিংস পরিবর্তন করতে কমান্ড দিন:\n\n" \
              "1️⃣ `/limit 10` (ঘণ্টায় ভিডিও সংখ্যা)\n" \
              "2️⃣ `/gap 3600` (পরবর্তী রাউন্ডের বিরতি - সেকেন্ড)\n" \
              "3️⃣ `/delay 60` (ভিডিওর মাঝখানের গ্যাপ)"
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ব্যাক", callback_data="back")]]))

    elif data == "force":
        if not db["CHANNELS"]:
            await query.answer("❌ আগে চ্যানেল যোগ করুন!", show_alert=True)
        else:
            db["IS_PAUSED"] = False
            force_event.set()
            await query.answer("⚡ ফোর্স স্টার্ট সচল! সাথে সাথে ডাউনলোড শুরু হচ্ছে...", show_alert=True)
            db["STATUS"] = "ফোর্স স্টার্ট প্রসেসিং... 🚀"

    elif data == "pause": db["IS_PAUSED"] = True; await query.answer("বন্ধ করা হয়েছে।")
    elif data == "resume": db["IS_PAUSED"] = False; await query.answer("চালু করা হয়েছে।")
    elif data == "back": await query.message.edit_text("🛠 **অ্যাডভান্সড অ্যাডমিন প্যানেল**", reply_markup=get_admin_markup())
    elif data == "add_ch": await query.message.reply("চ্যানেল যোগ করতে লিখুন: `/add লিঙ্ক` ")
    elif data == "del_ch": await query.message.reply("চ্যানেল ডিলিট করতে লিখুন: `/del লিঙ্ক` ")

# --- কমান্ড হ্যান্ডলারস ---
@bot_app.on_message(filters.command("add") & filters.user(ADMIN_ID))
async def add_ch_logic(client, message):
    try:
        new_ch = message.text.split(None, 1)[1]
        db["CHANNELS"].append(new_ch)
        await message.reply(f"✅ যোগ করা হয়েছে: {new_ch}")
    except: await message.reply("ভুল ফরম্যাট! `/add link` লিখুন।")

@bot_app.on_message(filters.command("del") & filters.user(ADMIN_ID))
async def del_ch_logic(client, message):
    try:
        ch = message.text.split(None, 1)[1]
        if ch in db["CHANNELS"]:
            db["CHANNELS"].remove(ch)
            await message.reply(f"🗑 ডিলিট করা হয়েছে: {ch}")
        else: await message.reply("চ্যানেলটি লিস্টে নেই।")
    except: await message.reply("ভুল ফরম্যাট! `/del link` লিখুন।")

@bot_app.on_message(filters.command(["limit", "gap", "delay"]) & filters.user(ADMIN_ID))
async def settings_update(client, message):
    try:
        val = int(message.text.split(None, 1)[1])
        if "limit" in message.text: db["HOURLY_LIMIT"] = val
        elif "gap" in message.text: db["SLEEP_GAP"] = val
        elif "delay" in message.text: db["VIDEO_DELAY"] = val
        await message.reply(f"⚙️ সেটিংস আপডেট করা হয়েছে: {val}")
    except: await message.reply("সঠিক সংখ্যা দিন। যেমন: `/limit 10`")

# --- রানার ---
async def start_everything():
    Thread(target=run_web).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট অনলাইন! কন্ট্রোল করতে /admin লিখুন।")
    await auto_worker()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_everything())
