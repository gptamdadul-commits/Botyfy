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
TARGET_BOT_USERNAME = "Sami_bideshbot" # @ চিহ্ন ছাড়া শুধু ইউজারনেম

# ক্লায়েন্ট সেটআপ
user_app = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
bot_app = Client("bot_manager", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

DOWNLOAD_DIR = "downloads/"
if not os.path.exists(DOWNLOAD_DIR): 
    os.makedirs(DOWNLOAD_DIR) # স্টোরেজ ম্যানেজমেন্ট

# --- ভিডিও প্রসেসিং ফাংশন (সিরিয়াল ও পিয়ার ফিক্সড) ---
async def process_videos(chat_input, start_id, count):
    sent = 0
    status_msg = None
    try:
        # ১. পিয়ার আইডি রিজলভ করা (সঠিক ফরম্যাট নিশ্চিতকরণ)
        try:
            # টার্গেট বটের সঠিক পিয়ার অবজেক্ট গেট করা
            target_bot_info = await user_app.get_users(TARGET_BOT_USERNAME)
            target_bot_peer = target_bot_info.id # বটের পজিটিভ আইডি নিশ্চিত করা
            
            # টার্গেট চ্যানেলের সঠিক পিয়ার গেট করা
            chat_info = await user_app.get_chat(chat_input)
            target_chat_id = chat_info.id
        except Exception as e:
            return await bot_app.send_message(ADMIN_ID, f"❌ পিয়ার রিজলভ এরর: {str(e)}\nনিশ্চিত করুন বটের ইউজারনেম সঠিক।")

        status_msg = await bot_app.send_message(ADMIN_ID, "⏳ কাজ শুরু হচ্ছে... স্ট্যাটাস আপডেট নিচে দেখুন।")
        
        # ২. ভিডিও স্ক্যানিং লুপ (পুরাতন থেকে নতুন)
        async for message in user_app.get_chat_history(target_chat_id, offset_id=int(start_id), limit=1000):
            if sent >= int(count):
                break
            
            if message.video:
                current_count = sent + 1
                # লাইভ আপডেট
                await status_msg.edit_text(f"📥 **প্রসেসিং: {current_count}/{count}**\n🔢 ভিডিও আইডি: `{message.id}`\n📦 স্ট্যাটাস: ডাউনলোড হচ্ছে...")
                
                # ৩. সিরিয়াল ডাউনলোড ও আপলোড (স্টোরেজ সেফ)
                file_path = await user_app.download_media(message, file_name=DOWNLOAD_DIR)
                
                await status_msg.edit_text(f"📤 **প্রসেসিং: {current_count}/{count}**\n🔢 ভিডিও আইডি: `{message.id}`\n📦 স্ট্যাটাস: আপনার আইডি হয়ে পাঠানো হচ্ছে...")
                
                # ৪. সঠিক পিয়ার আইডিতে ভিডিও পাঠানো
                await user_app.send_video(target_bot_peer, video=file_path, caption=f"উৎস: {chat_input}\nভিডিও আইডি: {message.id}")
                
                # ৫. মেমোরি ক্লিয়ার (সাথে সাথে ডিলিট)
                if os.path.exists(file_path): 
                    os.remove(file_path)
                
                sent += 1
                # ৬. ফ্লাডওয়েট সুরক্ষা বিরতি
                await asyncio.sleep(45) 

        await bot_app.send_message(ADMIN_ID, f"✅ **মিশন সফল!**\nমোট `{sent}`টি ভিডিও পাঠানো হয়েছে। স্টোরেজ সম্পূর্ণ খালি।")
        
    except errors.FloodWait as e:
        await bot_app.send_message(ADMIN_ID, f"⚠️ টেলিগ্রাম ব্লক করেছে! {e.value} সেকেন্ড অপেক্ষা করুন।")
        await asyncio.sleep(e.value)
    except Exception as e:
        await bot_app.send_message(ADMIN_ID, f"❌ বড় ত্রুটি: {str(e)}")

# --- কমান্ড হ্যান্ডলার ---
@bot_app.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    try:
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("সঠিক ফরম্যাট: `/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা` \n\nউদা: `/start_job -1003219361602 1 50` ")
        
        asyncio.create_task(process_videos(args[1], args[2], args[3]))
        await message.reply(f"⏳ প্রসেসিং রিকোয়েস্ট গ্রহণ করা হয়েছে। আপডেট দেওয়া হবে।")
        
    except Exception as e:
        await message.reply(f"❌ ভুল ইনপুট: {str(e)}")

@bot_app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    await message.reply("🛠 **ম্যানুয়াল কন্ট্রোল প্যানেল**\n\nকমান্ড দিন:\n`/start_job চ্যানেল_আইডি শুরু_আইডি সংখ্যা`")

# --- ওয়েব সার্ভার (Koyeb Health Check ফিক্স) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Storage Safe Serial Processing Active!"

def run_web():
    app.run(host="0.0.0.0", port=8080) # ৮০৮০ পোরট নিশ্চিত করা

async def start_all():
    Thread(target=run_web).start()
    await user_app.start()
    await bot_app.start()
    await bot_app.send_message(ADMIN_ID, "🚀 বট অনলাইন! আইডি রিজলভ লজিক আপডেট করা হয়েছে।")

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_all())
    asyncio.get_event_loop().run_forever()
