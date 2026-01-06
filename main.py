import os
import shutil
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from flask import Flask
from threading import Thread

# --- Flask Server (UptimeRobot এর মাধ্যমে ২৪/৭ সচল রাখার জন্য) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- কনফিগারেশন (Koyeb এর Environment Variables থেকে তথ্য নিবে) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0")) # আপনার নিজের আইডি

DOWNLOAD_DIR = "./downloads/"
STATE_FILE = "bot_state.txt" 

# ক্লায়েন্ট সেটআপ
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION, in_memory=True)
bot_app = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

def clear_storage():
    """পুরো ডাউনলোড ফোল্ডার পরিষ্কার করা"""
    if os.path.exists(DOWNLOAD_DIR):
        try:
            shutil.rmtree(DOWNLOAD_DIR)
        except:
            pass
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def save_state(link, current_count, end_num):
    """বট বন্ধ হলে কোন ফাইল পর্যন্ত প্রসেস হয়েছে তা সেভ রাখা"""
    with open(STATE_FILE, "w") as f:
        f.write(f"{link}|{current_count}|{end_num}")

def load_state():
    """পুরানো অসমাপ্ত কাজ চেক করা"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = f.read().split("|")
                return data[0], int(data[1]), int(data[2])
        except:
            return None
    return None

# --- হ্যান্ডলার (শুধুমাত্র আপনি ব্যবহার করতে পারবেন) ---

@bot_app.on_message(filters.command("start") & filters.user(ADMIN_ID))
async def start(client, message):
    clear_storage()
    btn = None
    state = load_state()
    if state:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Resume Last Task", callback_data="resume")]])
    
    await message.reply(
        "বট রেডি! আমি র্যান্ডম ডিলে (১-২ মিনিট) নিয়ে কাজ করব যাতে আপনার আইডি নিরাপদ থাকে।\n\n"
        "নিয়ম: `লিঙ্ক` `শুরু` `শেষ` লিখে পাঠান।\n"
        "উদাহরণ: `https://t.me/channel 1 50`", 
        reply_markup=btn
    )

@bot_app.on_callback_query(filters.regex("resume") & filters.user(ADMIN_ID))
async def resume_task(client, callback):
    state = load_state()
    if state:
        link, current, end = state
        await callback.message.edit_text(f"রিসিউম করা হচ্ছে: {link}\n{current} নম্বর ফাইল থেকে শুরু হচ্ছে...")
        await start_processing(callback.message, link, current, end)
    else:
        await callback.answer("কোনো পুরানো টাস্ক পাওয়া যায়নি।", show_alert=True)

@bot_app.on_message(filters.text & filters.private & filters.user(ADMIN_ID))
async def handle_input(client, message):
    input_data = message.text.split()
    if len(input_data) < 3:
        return await message.reply("সঠিক নিয়ম: `লিঙ্ক` `শুরু` `শেষ` দিন।")

    link, start_num, end_num = input_data[0], int(input_data[1]), int(input_data[2])
    await start_processing(message, link, start_num, end_num)

async def start_processing(message, link, start_num, end_num):
    target_bot = "Sami_bideshbot"
    status_msg = await message.reply("কাজ শুরু হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন।")
    
    # চ্যাট আইডি বের করা
    if "t.me/c/" in link:
        parts = link.split('/')
        chat_id = int("-100" + parts[parts.index("c") + 1])
    else:
        chat_id = link.split('/')[-1]
    
    processed_now = 0
    current_media_index = 0

    try:
        async for msg in user_app.get_chat_history(chat_id):
            if msg.video or msg.document or msg.photo or msg.animation:
                current_media_index += 1
                
                if current_media_index < start_num:
                    continue
                if current_media_index > end_num:
                    break

                processed_now += 1
                save_state(link, current_media_index, end_num)

                await status_msg.edit(f"প্রসেস হচ্ছে: {current_media_index} নং ফাইল।\nএই সেশনে পাঠানো হয়েছে: {processed_now} টি।")

                try:
                    # ১. ডাউনলোড
                    file_path = await user_app.download_media(msg, file_name=DOWNLOAD_DIR)
                    if file_path and os.path.exists(file_path):
                        caption = msg.caption or ""
                        
                        # ২. আপনাকে পাঠানো
                        if msg.video: await bot_app.send_video(ADMIN_ID, video=file_path, caption=caption)
                        elif msg.document: await bot_app.send_document(ADMIN_ID, document=file_path, caption=caption)
                        elif msg.photo: await bot_app.send_photo(ADMIN_ID, photo=file_path, caption=caption)
                        elif msg.animation: await bot_app.send_animation(ADMIN_ID, animation=file_path, caption=caption)

                        # ৩. অন্য বটে পাঠানো
                        try:
                            if msg.video: await user_app.send_video(target_bot, video=file_path, caption=caption)
                            elif msg.document: await user_app.send_document(target_bot, document=file_path, caption=caption)
                            elif msg.photo: await user_app.send_photo(target_bot, photo=file_path, caption=caption)
                            elif msg.animation: await user_app.send_animation(target_bot, animation=file_path, caption=caption)
                        except: pass
                        
                        # ৪. সাথে সাথে ডিলিট
                        os.remove(file_path)
                    
                    # র্যান্ডম ডিলে (৬০ থেকে ১২০ সেকেন্ড) যাতে আইডি নিরাপদ থাকে
                    delay = random.randint(60, 120)
                    await asyncio.sleep(delay)

                except FloodWait as e:
                    await status_msg.edit(f"টেলিগ্রাম লিমিট দিয়েছে। {e.value} সেকেন্ড অপেক্ষা করছি...")
                    await asyncio.sleep(e.value)
                except Exception as e:
                    print(f"Error processing file: {e}")

        await status_msg.edit(f"সফলভাবে শেষ হয়েছে! মোট {processed_now}টি ফাইল পাঠানো হয়েছে।")
        if os.path.exists(STATE_FILE): os.remove(STATE_FILE)

    except Exception as e:
        await status_msg.edit(f"মারাত্মক ত্রুটি: {str(e)}")

if __name__ == "__main__":
    keep_alive() # ওয়েব সার্ভার চালু
    user_app.start()
    bot_app.run()
