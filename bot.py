import os
import telebot
from telebot import types
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

# --- ၁။ Configuration ပိုင်း ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URI)
db = client['MovieBot']
files_col = db['files']

# Force Join စစ်ဆေးလိုသော Channel စာရင်း (ဒီမှာ လိုသလောက် ထည့်နိုင်သည်)
REQUIRED_CHANNELS = [
    {"id": -1003179962336, "link": "https://t.me/moviesbydatahouse"},
    {"id": -1003622691900, "link": "https://t.me/mmsubchannelfu"},
]

app = Flask('')
@app.route('/')
def home(): return "Bot is running!"

# --- ၂။ Force Subscribe စစ်ဆေးသည့် Function ---
def get_not_joined(user_id):
    """User မ Join ရသေးသော Channel များစာရင်းကို ပြန်ပေးမည်"""
    not_joined = []
    
    # Admin ဖြစ်နေရင် ဘာမှစစ်စရာမလိုဘဲ ကျော်ပေးမည်
    if user_id == ADMIN_ID:
        return []

    for ch in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(ch['id'], user_id)
            # member, administrator, creator မဟုတ်လျှင် မ Join သေးဟု သတ်မှတ်
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(ch)
        except Exception as e:
            # Bot က Channel ထဲမှာ Admin မဟုတ်ရင် ကျော်သွားပေးမယ်
            print(f"DEBUG Error for User {user_id} in Channel {ch['id']}: {e}")
            continue
            
    return not_joined

# Video ပို့ပေးသည့် Function
def send_movie(user_id, file_db_id):
    try:
        data = files_col.find_one({"_id": ObjectId(file_db_id)})
        if data:
            bot.send_video(user_id, data['file_id'], caption=data['caption'])
        else:
            bot.send_message(user_id, "❌ ဖိုင်ရှာမတွေ့ပါ။")
    except Exception as e:
        bot.send_message(user_id, "❌ Link မှားယွင်းနေပါသည်။")

# --- ၃။ Admin Commands (File Upload) ---

@bot.message_handler(content_types=['video', 'document'], func=lambda m: m.from_user.id == ADMIN_ID)
def handle_file(message):
    file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
    caption = message.caption or "No Title"
    res = files_col.insert_one({"file_id": file_id, "caption": caption})
    share_link = f"https://t.me/{(bot.get_me()).username}?start={res.inserted_id}"
    bot.reply_to(message, f"✅ သိမ်းပြီးပါပြီ!\n\nLink: `{share_link}`", parse_mode="Markdown")

# --- ၄။ Main logic (Start Command & Force Sub) ---

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()

    # ၁။ Join ထားခြင်း ရှိမရှိ အရင်စစ်ဆေးမည်
    not_joined = get_not_joined(user_id)

    # ၂။ မ Join ရသေးသော Channel ရှိနေလျှင်
    if not_joined:
        markup = types.InlineKeyboardMarkup()
        for ch in not_joined:
            markup.add(types.InlineKeyboardButton("📢 Join Channel", url=ch['link']))
        
        # ရုပ်ရှင် ID ပါလာရင် Try Again ခလုတ်မှာ အဲဒီ ID ထည့်ပေးမည်
        if len(args) > 1:
            file_db_id = args[1]
            markup.add(types.InlineKeyboardButton("♻️ အားလုံး Join ပြီးပါပြီ", callback_data=f"check_{file_db_id}"))
        else:
            markup.add(types.InlineKeyboardButton("♻️ အားလုံး Join ပြီးပါပြီ", callback_data="check_only"))

        # ⚠️ အရေးကြီး - ဒီနေရာမှာ စာပို့ပြီးရင် function ကို ရပ်လိုက်ရပါမယ် (return သုံးရမည်)
        return bot.send_message(user_id, "⚠️ **ဗီဒီယိုကြည့်ရှုရန် အောက်ပါ Channel အားလုံးကို အရင် Join ပေးပါ။**", reply_markup=markup, parse_mode="Markdown")

    # ၃။ အားလုံး Join ပြီးသား ဖြစ်မှသာ ဒီနေရာကို ရောက်လာမည်
    if len(args) > 1:
        send_movie(user_id, args[1]) #
    else:
        bot.send_message(user_id, "မင်္ဂလာပါ! ဇာတ်ကားကြည့်ရန် Link ကိုနှိပ်ပါ။") #

# --- ၅။ Callback Handlers (Try Again ခလုတ်များ) ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def check_callback(call):
    user_id = call.from_user.id
    data_parts = call.data.split("_")
    
    not_joined = get_not_joined(user_id)
    
    if not_joined:
        bot.answer_callback_query(call.id, "❌ Channel အားလုံး မ Join ရသေးပါ။", show_alert=True)
    else:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        # ရုပ်ရှင်ကြည့်ဖို့ လာတာဆိုရင် ရုပ်ရှင်ပို့ပေးမယ်
        if len(data_parts) > 1 and data_parts[1] != "only":
            send_movie(user_id, data_parts[1])
        else:
            bot.send_message(user_id, "✅ Join ပြီးပါပြီ။ အသုံးပြုနိုင်ပါပြီ။")

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == "__main__":
    Thread(target=run).start()
    print("Bot is running...")
    bot.infinity_polling()



