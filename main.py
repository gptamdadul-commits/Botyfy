import os
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from flask import Flask
from threading import Thread

# --- Configuration (Environment Variables) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
STRING_SESSION = os.environ.get("STRING_SESSION")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
TARGET_BOT = os.environ.get("TARGET_BOT")

# --- Flask Health Check Server ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Running", 200

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# --- Bot Clients ---
bot = Client("admin_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("user_session", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

# --- Core Logic ---

@bot.on_message(filters.command("start_job") & filters.user(ADMIN_ID))
async def start_job_handler(client, message):
    try:
        args = message.text.split()
        if len(args) < 4:
            await message.reply("❌ ফরম্যাট: `/start_job [ID] [Start_Msg_ID] [Count]`")
            return

        source_chat = args[1]
        start_id = int(args[2])
        count = int(args[3])

        # Resolve Target Bot ID
        target_info = await user.get_users(TARGET_BOT)
        target_id = target_info.id

        status_msg = await message.reply("🔄 সরাসরি ফরোয়ার্ড টাস্ক শুরু হচ্ছে...")

        for i in range(count):
            current_msg_id = start_id + i
            
            await status_msg.edit(f"⏳ প্রসেস হচ্ছে: {i+1}/{count}\nMessage ID: {current_msg_id}")

            try:
                # সরাসরি ফরোয়ার্ড করার কমান্ড (ডাউনলোড-আপলোড এর প্রয়োজন নেই)
                await user.forward_messages(
                    chat_id=target_id,
                    from_chat_id=source_chat,
                    message_ids=current_msg_id
                )
                
                await status_msg.edit(f"✅ ফরোয়ার্ড সফল: {i+1}/{count}")
                # ফরোয়ার্ডের ক্ষেত্রে খুব দ্রুত করলে টেলিগ্রাম স্প্যাম ধরতে পারে, তাই ২ সেকেন্ড বিরতি
                await asyncio.sleep(2)

            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                # মেসেজ না থাকলে বা অন্য এরর হলে স্কিপ করবে
                continue

        await status_msg.edit("🏁 সরাসরি ফরোয়ার্ড টাস্ক সম্পূর্ণ হয়েছে!")

    except Exception as e:
        await message.reply(f"❌ ত্রুটি: {str(e)}")

# --- Execution ---
if __name__ == "__main__":
    Thread(target=run_flask).start()
    print("Forwarder Bot Starting...")
    user.start()
    bot.run()
