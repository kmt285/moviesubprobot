import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from motor.motor_asyncio import AsyncIOMotorClient
import os

# --- Configurations ---
API_ID = int(os.environ.get("API_ID", 12345)) # Render မှာ ထည့်ထားတဲ့ ID ကို ယူမယ်
API_HASH = os.environ.get("API_HASH", "your_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_token")
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri")

# Force Join စစ်မည့် Channel များ
# Example: [-10012345678, -10087654321]
AUTH_CHANNELS = [-1003622691900, -1003629942364] 

client = AsyncIOMotorClient(MONGO_URI)
db = client.movie_bot
movies_collection = db.movies

app = Client("movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Functions ---
async def is_subscribed(user_id):
    for channel in AUTH_CHANNELS:
        try:
            await app.get_chat_member(channel, user_id)
        except UserNotParticipant:
            return False
        except Exception:
            continue
    return True

# --- Commands ---

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    user_id = message.from_user.id
    
    # Start Parameter ပါမပါ စစ်မယ်
    if len(message.command) > 1:
        movie_id = message.command[1]
        
        # Subscribe စစ်မယ်
        if not await is_subscribed(user_id):
            buttons = []
            for i, channel_id in enumerate(AUTH_CHANNELS, 1):
                invite_link = (await client.get_chat(channel_id)).invite_link
                buttons.append([InlineKeyboardButton(f"Join Channel {i}", url=invite_link)])
            
            # ပြန်နှိပ်ရန် Try Again Button
            buttons.append([InlineKeyboardButton("Joined - Try Again", url=f"https://t.me/{(await client.get_me()).username}?start={movie_id}")])
            
            return await message.reply_text(
                "ဒီရုပ်ရှင်ကို ကြည့်ဖို့အတွက် ကျွန်တော်တို့ရဲ့ Channel တွေကို အရင် Join ပေးပါဦး။",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # DB ထဲမှာ Movie ရှာမယ်
        movie = await movies_collection.find_one({"movie_id": movie_id})
        if movie:
            await client.copy_message(
                chat_id=user_id,
                from_chat_id=movie['channel_id'],
                message_id=movie['msg_id'],
                caption=f"**{movie['file_name']}**"
            )
        else:
            await message.reply_text("စိတ်မရှိပါနဲ့၊ ရုပ်ရှင်ရှာမတွေ့ပါ။")
    else:
        await message.reply_text("Welcome! ပိုစတာအောက်က link ကနေတစ်ဆင့် ရုပ်ရှင်ကြည့်နိုင်ပါတယ်။")

# Admin Only: Indexing Movies
@app.on_message(filters.command("update") & filters.user(ADMINS))
async def update_movies(client, message):
    # Format: /update -100xxxx 10 50
    if len(message.command) < 4:
        return await message.reply_text("Format: `/update [channel_id] [start_id] [end_id]`")

    target_chat = int(message.command[1])
    start_id = int(message.command[2])
    end_id = int(message.command[3])
    
    count = 0
    status_msg = await message.reply_text("Indexing စတင်နေပါပြီ...")

    for msg_id in range(start_id, end_id + 1):
        try:
            msg = await client.get_messages(target_chat, msg_id)
            if msg.video:
                file_name = msg.video.file_name or f"Movie_{msg_id}"
                movie_id = f"movie_{target_chat}_{msg_id}".replace("-", "")
                
                await movies_collection.update_one(
                    {"movie_id": movie_id},
                    {"$set": {
                        "movie_id": movie_id,
                        "channel_id": target_chat,
                        "msg_id": msg_id,
                        "file_name": file_name
                    }},
                    upsert=True
                )
                
                # Auto Link ထုတ်ပေးခြင်း
                bot_username = (await client.get_me()).username
                movie_link = f"https://t.me/{bot_username}?start={movie_id}"
                await client.send_message(
                    message.chat.id, 
                    f"✅ **Indexed:** {file_name}\n🔗 **Link:** `{movie_link}`"
                )
                count += 1
        except Exception:
            continue
    
    await status_msg.edit(f"ပြီးဆုံးပါပြီ။ စုစုပေါင်း {count} ဖိုင် သိမ်းဆည်းပြီး။")

app.run()


