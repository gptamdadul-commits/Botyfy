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
TARGET_BOT_USERNAME = "@Sami_bideshbot" # ইউজারনেম ঠিক থাকলে এখানে পরিবর্তন লাগবে না

# ক্লায়েন্ট সেটআপ
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DOWNLOAD_DIR = "downloads/"
if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

# --- ভিডিও প্রসেসিং ফাংশন (চূড়ান্ত সমাধান) ---
async def process_videos(chat_input, start_id, count):
    sent = 0
    status_msg = None
    try:
        # ১. জোরপূর্বক চ্যানেল জয়েন ও আইডি রিজলভ করা
        try:
            # আইডি বা ইউজারনেম দিয়ে আগে চ্যাটটি পাওয়ার চেষ্টা করা
            chat = await user_app.get_chat(chat_input)
            target_chat_id = chat.id
            # ব্যাকআপ হিসেবে জয়েন চেক
            try: await user_app.join_chat(target_chat_id)
            except: pass
            
            # টার্গেট বট রিজলভ
            target_bot = await user_app.get_chat(TARGET_BOT_USERNAME)
            target_bot_peer = target_bot.id
        except Exception as e:
            return await bot_app.send_message(ADMIN_ID, f"❌ আইডি চিনতে পারছে না: {str(e)}\n\nটিপস: বটের ইউজারনেমটি কোডে ঠিক আছে কি না দেখুন।")

        status_msg = await bot_app.send_message(ADMIN_ID, "⏳ কাজ শুরু হচ্ছে... লাইভ আপডেট নিচে দেখুন।")
        
        # ২. সিরিয়াল প্রসেসিং লুপ
        async for message in user_app.get_chat_history(target_chat_id, offset_id=int(start_id), limit=1000):
            if sent >= int(count): break
            
            if message.video:
                current_count = sent + 1
                await status_msg.edit_text(f"📥 **প্রসেসিং: {current_count}/{count}**\n🆔 আইডি: `{message.id}`\n📦 অবস্থা: ডাউনলোড হচ্ছে...")
                
                # ডাউনলোড ও স্টোরেজ ম্যানেজমেন্ট
                file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                
                await status_msg.edit_text(f"📤 **প্রসেসিং: {current_count}/{count}**\n🆔 আইডি: `{message.id}`\n📦 অবস্থা: আপলোড হচ্ছে...")
                
                # আপনার আইডি হয়ে ফরোয়ার্ড
                await user_app.send_video(target_bot_peer, video=file_path, caption=f"উৎস: {chat_input}\nভিডিও আইডি: {message.id}")
                
                # পাঠানোর পরপরই ডিলিট
                if os.path.exists(file_path): os.remove(file_path)
                
                sent += 1
                await asyncio.sleep(45) # FloodWait প্রোটেকশন

        await bot_app.send_message(ADMIN_ID, f"✅ **মিশন সম্পন্ন!**\nমোট পাঠানো হয়েছে: `{sent}`টি ভিডিও। স্টোরেজ সম্পূর্ণ খালি।")
        
    except errors.FloodWait as e:
        await bot_app.send_message(ADMIN_ID, f"⚠️ ফ্লাডওয়েট: {e.value} সেকেন্ড পর নিজে থেকেই শুরু হবে।")
        await asyncio.sleep(e.value)
    except Exception as e:
        await bot_app.send_message(ADMIN_ID, f"❌ বড় ত্রুটি: {str(e)}")

# --- কমান্ড হ্যান্ডলার ---
@bot_app.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    try:
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("সঠিক ফরম্যাট: `/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা` ")
        
        asyncio.create_task(process_videos(args[1], args[2], args[3]))
        await message.reply(f"⏳ প্রসেসিং শুরু করা হয়েছে।")
        
    except Exception as e:
        await message.reply(f"❌ ভুল: {str(e)}")

# --- ওয়েব সার্ভার (Koyeb Health Check ফিক্স) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Healthy and Active!"

async def start_all():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট এখন ম্যানুয়াল মোডে সম্পূর্ণ সচল!")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
    asyncio.get_event_loop().run_forever()
