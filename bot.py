import asyncio
import os
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient

# --- Flask Web Server (For Render) ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot is Alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- Configs (Render Dashboard မှာ ထည့်ပေးရန်) ---
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token")
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri")
ADMINS = [7812553563] # သင့် User ID ထည့်ပါ
AUTH_CHANNELS = [-1003622691900, -1003629942364] # Join ခိုင်းမည့် Channel များ

# Database Setup
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client.movie_database
movies_col = db.movies

app = Client("movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Functions ---
async def is_subscribed(user_id):
    for chat_id in AUTH_CHANNELS:
        try:
            await app.get_chat_member(chat_id, user_id)
        except UserNotParticipant:
            return False
        except Exception:
            continue
    return True

# --- Handlers ---

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    
    # ရုပ်ရှင် Link ကနေ လာတာလား စစ်မယ်
    if len(message.command) > 1:
        movie_id = message.command[1]
        
        # Channel Join ထားလား စစ်မယ်
        if not await is_subscribed(user_id):
            buttons = []
            for i, chat_id in enumerate(AUTH_CHANNELS, 1):
                chat = await client.get_chat(chat_id)
                buttons.append([InlineKeyboardButton(f"Join Channel {i}", url=chat.invite_link)])
            
            # ပြန်စစ်မယ့် Button
            buttons.append([InlineKeyboardButton("Join ပြီးပါပြီ (Try Again)", url=f"https://t.me/{(await client.get_me()).username}?start={movie_id}")])
            
            return await message.reply_text(
                "🎬 **ရုပ်ရှင်ကြည့်ရန် အောက်က Channel တွေကို အရင် Join ပေးပါ**",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Database ထဲမှာ ရှာမယ်
        movie = await movies_col.find_one({"movie_id": movie_id})
        if movie:
            await client.copy_message(
                chat_id=user_id,
                from_chat_id=movie['from_chat_id'],
                message_id=movie['msg_id'],
                caption=f"🍿 **Enjoy Your Movie!**\n\n{movie.get('caption', '')}"
            )
        else:
            await message.reply_text("❌ စိတ်မရှိပါနဲ့၊ ဒီ Movie Link က သက်တမ်းကုန်ဆုံးသွားပါပြီ။")
    else:
        await message.reply_text("မင်္ဂလာပါ! ကျွန်တော်က ရုပ်ရှင်တွေကို ရှာဖွေပေးမယ့် Bot ဖြစ်ပါတယ်။")

# Admin Command: Channel ထဲက movie တွေကို Database ထဲ သွင်းမယ်
@app.on_message(filters.command("index") & filters.user(ADMINS))
async def index_movies(client, message):
    if len(message.command) < 4:
        return await message.reply_text("Format: `/index [channel_id] [start_id] [end_id]`")

    target_chat = int(message.command[1])
    start = int(message.command[2])
    end = int(message.command[3])
    
    status = await message.reply_text("⏳ Processing...")
    count = 0

@app.on_message(filters.command("index") & filters.user(ADMINS))
async def index_movies(client, message):
    if len(message.command) < 4:
        return await message.reply_text("Format: `/index [channel_id] [start_id] [end_id]`")

    try:
        # ID ကို string ကနေ integer ပြောင်းလဲမှုကို သေချာအောင်လုပ်ခြင်း
        input_chat = message.command[1]
        if not input_chat.startswith("-100"):
            target_chat = int("-100" + input_chat)
        else:
            target_chat = int(input_chat)
            
        start = int(message.command[2])
        end = int(message.command[3])
    except Exception as e:
        return await message.reply_text(f"❌ Input Error: {str(e)}")
    
    status = await message.reply_text("🔍 Channel ကို စတင်ချိတ်ဆက်နေပါပြီ...")
    count = 0

    try:
        # Bot က Channel ကို တကယ်မြင်ရလား အရင်စစ်မယ်
        chat_info = await client.get_chat(target_chat)
        await status.edit(f"✅ Connection အောင်မြင်သည်- {chat_info.title}\n🎥 Indexing စတင်နေပြီ...")
    except Exception as e:
        return await status.edit(f"❌ Channel Error: Bot က Channel ကို မမြင်ရပါ။ Bot ကို Admin ခန့်ထားတာ သေချာပါသလား?\nError: {str(e)}")

    for msg_id in range(start, end + 1):
        try:
            msg = await client.get_messages(target_chat, msg_id)
            
            if msg and (msg.video or msg.document):
                media = msg.video or msg.document
                file_name = getattr(media, 'file_name', f"Movie_{msg_id}")
                
                # Movie ID ကို Link အတွက် ပြုလုပ်ခြင်း
                short_id = str(target_chat).replace("-100", "")
                movie_id = f"vid_{short_id}_{msg_id}"
                
                await movies_col.update_one(
                    {"movie_id": movie_id},
                    {"$set": {
                        "movie_id": movie_id,
                        "from_chat_id": target_chat,
                        "msg_id": msg_id,
                        "caption": msg.caption or file_name
                    }}, upsert=True
                )
                
                count += 1
                # ၅ ခုမြောက်တိုင်း တစ်ခါ status update ပေးမယ်
                if count % 5 == 0:
                    await status.edit(f"⏳ လုပ်ဆောင်နေဆဲ... သိမ်းဆည်းပြီး: {count}")
            
            await asyncio.sleep(1.0) # Telegram Flood Wait ရှောင်ရန်
        except Exception:
            continue

    await status.edit(f"✅ ပြီးဆုံးပါပြီ။\nစုစုပေါင်း {count} ဖိုင် သိမ်းဆည်းပြီး။")
    
# Admin Command: Database ထဲက movie အရေအတွက် ကြည့်ရန်
@app.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats(client, message):
    total = await movies_col.count_documents({})
    await message.reply_text(f"📊 **Database Status:**\n\nစုစုပေါင်း ရုပ်ရှင်အရေအတွက်: {total} ကား")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot is running...")
    app.run()



