import os
import telebot
from telebot import types
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

# Setup
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URI)
db = client['MovieBot']
files_col = db['files']
settings_col = db['settings']

app = Flask('')
@app.route('/')
def home(): return "Bot is running!"

# Database ကနေ Channel List ကို ဆွဲယူခြင်း
def get_fsub_channels():
    data = settings_col.find_one({"type": "fsub_config"})
    return data['channels'] if data else []

def check_status(user_id):
    channels = get_fsub_channels()
    not_joined = []
    
    # ၁။ Admin ဖြစ်နေရင် ဘာမှစစ်စရာမလိုဘဲ ပေးကြည့်မယ်
    if str(user_id) == str(ADMIN_ID):
        return []

    for ch in channels:
        try:
            # ၂။ Channel ID ကို သေချာစစ်ဆေးမယ်
            raw_id = str(ch['id']).strip()
            
            # -100 မပါရင် ဖြည့်ပေးမယ် (Telegram Channel ID တိုင်းမှာ -100 ပါရပါတယ်)
            if not raw_id.startswith('-100'):
                if raw_id.startswith('-'):
                    clean_id = f"-100{raw_id[1:]}"
                else:
                    clean_id = f"-100{raw_id}"
            else:
                clean_id = raw_id

            # ၃။ Telegram ဆီကနေ User status ကို တောင်းမယ်
            member = bot.get_chat_member(int(clean_id), user_id)
            
            # ၄။ User ရဲ့ status ကို စစ်မယ်
            # member, administrator, creator ထဲမှာ တစ်ခုမှမရှိရင် မ Join ရသေးဘူးလို့ ယူဆမယ်
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(ch)
                
        except Exception as e:
            # Bot က Channel ထဲမှာ Admin မဟုတ်ရင် ဒီနေရာမှာ Error တက်ပါမယ်
            print(f"DEBUG Error for User {user_id} in Channel {ch['id']}: {e}")
            # စစ်လို့မရတဲ့ Channel ရှိရင် User ကို ပေးသွားခိုင်းလိုက်တာ ပိုကောင်းပါတယ်
            continue
            
    return not_joined
# Video ပို့ပေးသည့် သီးသန့် Function
def send_movie(user_id, file_db_id):
    try:
        data = files_col.find_one({"_id": ObjectId(file_db_id)})
        if data:
            bot.send_video(user_id, data['file_id'], caption=data['caption'])
        else:
            bot.send_message(user_id, "❌ ဖိုင်ရှာမတွေ့ပါ။")
    except Exception as e:
        bot.send_message(user_id, "❌ Link မှားယွင်းနေပါသည်။")

# --- Admin Commands ---

@bot.message_handler(commands=['addch'])
def add_channel(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        args = message.text.split()
        ch_id = int(args[1])
        ch_link = args[2]
        settings_col.update_one(
            {"type": "fsub_config"},
            {"$push": {"channels": {"id": ch_id, "link": ch_link}}},
            upsert=True
        )
        bot.reply_to(message, "✅ Channel ထည့်သွင်းပြီးပါပြီ။")
    except:
        bot.reply_to(message, "❌ အသုံးပြုပုံ: `/addch [Channel_ID] [Link]`")

@bot.message_handler(commands=['delch'])
def del_channel(message):
    if message.from_user.id != ADMIN_ID: return
    settings_col.update_one({"type": "fsub_config"}, {"$set": {"channels": []}})
    bot.reply_to(message, "🗑 Channel List အားလုံးကို ဖျက်လိုက်ပါပြီ။")

@bot.message_handler(commands=['listch'])
def list_channel(message):
    if message.from_user.id != ADMIN_ID: return
    channels = get_fsub_channels()
    msg = "📢 **လက်ရှိ Force Join Channels:**\n\n"
    for c in channels:
        msg += f"ID: `{c['id']}`\nLink: {c['link']}\n\n"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

# --- File Handling (Admin Only) ---

@bot.message_handler(content_types=['video', 'document'])
def handle_file(message):
    if message.from_user.id != ADMIN_ID: return
    file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
    caption = message.caption or "No Title"
    res = files_col.insert_one({"file_id": file_id, "caption": caption})
    share_link = f"https://t.me/{(bot.get_me()).username}?start={res.inserted_id}"
    bot.reply_to(message, f"✅ သိမ်းပြီးပါပြီ!\n\nLink: `{share_link}`", parse_mode="Markdown")

# --- User Start Logic ---

@bot.message_handler(commands=['start'])
def start(message):
    args = message.text.split()
    user_id = message.from_user.id

    if len(args) > 1:
        file_db_id = args[1]
        not_joined = check_status(user_id)

        if not_joined:
            markup = types.InlineKeyboardMarkup()
            for ch in not_joined:
                markup.add(types.InlineKeyboardButton("📢 Join Channel", url=ch['link']))
            markup.add(types.InlineKeyboardButton("♻️ Try Again", callback_data=f"check_{file_db_id}"))
            return bot.send_message(user_id, "❌ ဗီဒီယိုကြည့်ရန် အောက်ပါ Channel များကို အရင် Join ပေးပါ။", reply_markup=markup)

        send_movie(user_id, file_db_id)
    else:
        bot.send_message(user_id, "မင်္ဂလာပါ! ဇာတ်ကားကြည့်ရန် Link ကိုနှိပ်ပါ။")

# Try Again ခလုတ်အတွက် Callback Handler
@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def check_callback(call):
    user_id = call.from_user.id
    file_db_id = call.data.split("_")[1]
    not_joined = check_status(user_id)
    
    if not_joined:
        bot.answer_callback_query(call.id, "❌ Channel အားလုံးမ Join ရသေးပါ!", show_alert=True)
    else:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_movie(user_id, file_db_id)

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == "__main__":
    Thread(target=run).start()
    print("Bot is running...")
    bot.infinity_polling()




