import os
import telebot
from telebot import types
from pymongo import MongoClient
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

# Setup
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
FSUB_CHANNEL = int(os.getenv('FSUB_CHANNEL'))
CHANNEL_URL = os.getenv('CHANNEL_URL')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = telebot.TeleBot(BOT_TOKEN)
db = MongoClient(MONGO_URI)['MovieBot']['files']

app = Flask('')

@app.route('/')
def home(): return "Bot is running!"

# Force Join စစ်ဆေးသည့် Function
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(FSUB_CHANNEL, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

# Admin အတွက် File သိမ်းသည့် Command
@bot.message_handler(content_types=['video', 'document'])
def save_file(message):
    if message.from_user.id != ADMIN_ID:
        return

    file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
    caption = message.caption or "No Title"
    
    # DB ထဲသိမ်းပြီး ID ထုတ်ပေးမယ်
    res = db.insert_one({"file_id": file_id, "caption": caption})
    share_link = f"https://t.me/{(bot.get_me()).username}?start={res.inserted_id}"
    
    bot.reply_to(message, f"✅ သိမ်းဆည်းပြီးပါပြီ!\n\nLink: `{share_link}`", parse_mode="Markdown")

# /start logic (File ထုတ်ပေးခြင်း နှင့် Force Join)
@bot.message_handler(commands=['start'])
def start(message):
    args = message.text.split()
    user_id = message.from_user.id

    if len(args) > 1:
        file_db_id = args[1]
        
        # Force Join စစ်မယ်
        if not is_subscribed(user_id):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL))
            markup.add(types.InlineKeyboardButton("♻️ Try Again", url=f"https://t.me/{(bot.get_me()).username}?start={file_db_id}"))
            
            return bot.send_message(user_id, "❌ ဗီဒီယိုကြည့်ရှုရန် ကျွန်ုပ်တို့၏ Channel ကို အရင် Join ပေးပါ။", reply_markup=markup)

        # File ထုတ်ပေးမယ်
        data = db.find_one({"_id": file_db_id}) # မှတ်ချက်- တကယ်တမ်းစာရင် ObjectId နဲ့စစ်ရပါတယ်
        # ရိုးရှင်းအောင် string ID နဲ့ပဲပြထားပါတယ်
        try:
            from bson.objectid import ObjectId
            data = db.find_one({"_id": ObjectId(file_db_id)})
            if data:
                bot.send_video(user_id, data['file_id'], caption=data['caption'])
            else:
                bot.send_message(user_id, "ဖိုင်ရှာမတွေ့ပါ။")
        except:
            bot.send_message(user_id, "Invalid Link.")
    else:
        bot.send_message(user_id, "မင်္ဂလာပါ! ဇာတ်ကား link ကိုနှိပ်ပြီး ဝင်ရောက်ကြည့်ရှုပါ။")

# အသုံးဝင်မယ့် Admin Commands
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id == ADMIN_ID:
        count = db.count_documents({})
        bot.reply_to(message, f"စုစုပေါင်း သိမ်းထားသော ဇာတ်ကားအရေအတွက်: {count}")

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == "__main__":
    Thread(target=run).start()
    bot.infinity_polling()
