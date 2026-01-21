import asyncio
import os
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant, FloodWait
from motor.motor_asyncio import AsyncIOMotorClient

# --- Flask Server ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Bot status: Online"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- Configurations ---
API_ID = int(os.environ.get("API_ID", "12345"))
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token")
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri")
ADMINS = [7812553563]
AUTH_CHANNELS = [-1003622691900, -1003629942364]

# Database
client_db = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client_db.movie_bot
movies_collection = db.movies

app = Client("movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Functions ---
async def is_subscribed(user_id):
    for chat_id in AUTH_CHANNELS:
        try:
            member = await app.get_chat_member(chat_id, user_id)
            if member.status in ["kicked", "left"]: return False
        except UserNotParticipant: return False
        except Exception: continue
    return True

# --- Handlers ---

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    if len(message.command) > 1:
        movie_id = message.command[1]
        if not await is_subscribed(user_id):
            buttons = []
            for i, chat_id in enumerate(AUTH_CHANNELS, 1):
                try:
                    chat = await client.get_chat(chat_id)
                    link = chat.invite_link or f"https://t.me/c/{str(chat_id).replace('-100','')}/1"
                    buttons.append([InlineKeyboardButton(f"Join Channel {i}", url=link)])
                except: continue
            buttons.append([InlineKeyboardButton("Joined - Try Again", url=f"https://t.me/{(await client.get_me()).username}?start={movie_id}")])
            return await message.reply_text("🎬 ရုပ်ရှင်ကြည့်ရန် အရင် Join ပါ။", reply_markup=InlineKeyboardMarkup(buttons))

        movie = await movies_collection.find_one({"movie_id": movie_id})
        if movie:
            try:
                await client.copy_message(chat_id=user_id, from_chat_id=movie['channel_id'], message_id=movie['msg_id'])
            except Exception as e:
                await message.reply_text(f"❌ ပို့မရပါ- {str(e)}")
        else:
            await message.reply_text("❌ ရုပ်ရှင်ရှာမတွေ့ပါ။")
    else:
        await message.reply_text("Welcome! ပိုစတာအောက်က link ကနေတစ်ဆင့် ရုပ်ရှင်ကြည့်နိုင်ပါတယ်။")

@app.on_message(filters.command("index") & filters.user(ADMINS))
async def index_movies(client, message):
    if len(message.command) < 4:
        return await message.reply_text("Format: `/index [channel_id] [start_id] [end_id]`")

    try:
        target_chat = int(message.command[1])
        start = int(message.command[2])
        end = int(message.command[3])
    except:
        return await message.reply_text("ဂဏန်းများသာ ရိုက်ထည့်ပါ။")

    status = await message.reply_text("🔍 စစ်ဆေးနေသည်...")
    count = 0

    for msg_id in range(start, end + 1):
        try:
            # ဗားရှင်းအသစ်များအတွက် ပိုမိုသေချာသော နည်းလမ်းဖြင့် ဆွဲထုတ်ခြင်း
            msg = await client.get_messages(target_chat, msg_id)
            
            if msg and not msg.empty and (msg.video or msg.document):
                media = msg.video or msg.document
                f_name = getattr(media, 'file_name', f"Movie_{msg_id}")
                m_id = f"vid_{str(target_chat).replace('-100', '')}_{msg_id}"

                await movies_collection.update_one(
                    {"movie_id": m_id},
                    {"$set": {"movie_id": m_id, "channel_id": target_chat, "msg_id": msg_id, "file_name": f_name}},
                    upsert=True
                )
                count += 1
                if count % 5 == 0:
                    await status.edit(f"⏳ သိမ်းဆည်းဆဲ... {count} ကား (ID: {msg_id})")
            
            await asyncio.sleep(1.2) # Flood Wait ရှောင်ရန်

        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"Error at ID {msg_id}: {e}")
            continue

    await status.edit(f"✅ လုပ်ငန်းစဉ်ပြီးဆုံး။ စုစုပေါင်း: {count}")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()
