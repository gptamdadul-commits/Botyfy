import os
import shutil
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, PeerIdInvalid, RPCError, UserNotParticipant, UsernameInvalid
from flask import Flask
from threading import Thread

# --- ১. কনফিগারেশন (Koyeb Environment Variables) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = os.environ.get("TARGET_BOT")

DOWNLOAD_DIR = "./downloads/"

# আপনার পুরনো কোডের স্টাইলে স্টোরেজ ক্লিনআপ
def clear_storage():
    if os.path.exists(DOWNLOAD_DIR):
        try: shutil.rmtree(DOWNLOAD_DIR)
        except: pass
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

clear_storage()

# --- ২. ক্লায়েন্ট সেটআপ ---
# in_memory=True ব্যবহার করা হয়েছে যাতে সেশন ডাটাবেজ ফাইল ক্র্যাশ না করে
user = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION, in_memory=True)
bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- ৩. হেল্পার (Flask Server) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is alive!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- ৪. আধুনিক প্রগ্রেস বার লজিক ---
async def progress_bar(current, total, status_msg, start_time, action):
    now = time.time()
    diff = now - start_time
    if round(diff % 4.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        eta = round((total - current) / speed) if speed > 0 else 0
        filled_length = int(15 * current // total)
        bar = '▰' * filled_length + '▱' * (15 - filled_length)
        tmp = (f"🚀 **{action}...**\n┣ {bar}\n┣ 🌀 **প্রগতি:** {percentage:.2f}%\n"
               f"┣ 📦 **সাইজ:** {current/1024/1024:.2f} MB\n┗ ⏳ **বাকি সময়:** {eta}s")
        try: await status_msg.edit(tmp)
        except: pass

# --- ৫. মেইন টাস্ক হ্যান্ডলার ---
@bot.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    status_msg = await message.reply("📡 **আইডি ভেরিফাই করা হচ্ছে...**")
    
    try:
        # ইনপুট চেক
        args = message.text.split()
        if len(args) < 4:
            await status_msg.edit("❌ **ভুল ফরম্যাট!**\nব্যবহার করুন: `/start_job [Chat_ID] [Start_ID] [Count]`")
            return

        chat_id = args[1]
        try: chat_id = int(chat_id)
        except: pass # ইউজারনেম হলে স্ট্রিং হিসেবে থাকবে
        
        start_id = int(args[2])
        count = int(args[3])

        # --- আইডি কানেকশন নিশ্চিত করা (Error Handling) ---
        try:
            # সোর্স চ্যাট চেক
            source_chat = await user.get_chat(chat_id)
            
            # টার্গেট আইডি চেক (Environment Variable থেকে)
            t_input = int(TARGET_BOT) if TARGET_BOT.replace("-","").isdigit() else TARGET_BOT.replace("@","")
            target_user = await user.get_users(t_input)
            target_id = target_user.id
            
            # সেশনের সাথে টার্গেট বটের সংযোগ তৈরির চেষ্টা
            await user.send_chat_action(target_id, "typing")
            
        except (PeerIdInvalid, UsernameInvalid):
            await status_msg.edit(f"❌ **Invalid ID/Username!**\n\n**সমাধান:**\n১. সেশন একাউন্ট দিয়ে চ্যানেলে জয়েন করুন।\n২. সেশন একাউন্ট দিয়ে টার্গেট বটকে একটি মেসেজ দিন।")
            return
        except UserNotParticipant:
            await status_msg.edit(f"❌ **সেশন একাউন্ট জয়েন নেই!**\nচ্যানেল আইডি: `{chat_id}`")
            return
        except Exception as e:
            await status_msg.edit(f"⚠️ **কানেকশন এরর:** `{str(e)}` \nসঠিক আইডি দিন।")
            return

        await status_msg.edit(f"✅ **চ্যানেল:** {source_chat.title}\n🚀 সিরিয়াল ডাউনলোড শুরু হচ্ছে...")

        for i in range(count):
            current_msg_id = start_id + i
            try:
                msg = await user.get_messages(chat_id, current_msg_id)
                
                if msg and (msg.video or msg.photo or msg.document):
                    start_time = time.time()
                    # ১. ডাউনলোড
                    file_path = await user.download_media(msg, progress=progress_bar, progress_args=(status_msg, start_time, "ডাউনলোড"))
                    
                    # ২. আপলোড (টার্গেট বটে)
                    start_time = time.time()
                    caption = msg.caption or ""
                    if msg.video:
                        await user.send_video(target_id, video=file_path, caption=caption, progress=progress_bar, progress_args=(status_msg, start_time, "আপলোড"))
                    elif msg.photo:
                        await user.send_photo(target_id, photo=file_path, caption=caption)
                    elif msg.document:
                        await user.send_document(target_id, document=file_path, caption=caption, progress=progress_bar, progress_args=(status_msg, start_time, "আপলোড"))

                    # ৩. ফাইল ডিলিট (স্টোরেজ সুরক্ষা)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    await asyncio.sleep(2) # FloodWait এড়াতে গ্যাপ
                else:
                    await status_msg.edit(f"⏩ স্কিপ: `{current_msg_id}` (মিডিয়া নেই)")
            except Exception:
                continue # কোনো মেসেজ এরর হলে বট থামবে না, পরের মেসেজে যাবে

        await status_msg.edit("🏁 **মিশন সম্পূর্ণ!** সব ফাইল পাঠানো হয়েছে।")

    except Exception as e:
        await bot.send_message(ADMIN_ID, f"🚨 **মারাত্মক ত্রুটি:** {str(e)}")

# --- ৬. রান ---
if __name__ == "__main__":
    Thread(target=run_flask).start()
    user.start()
    bot.run()
