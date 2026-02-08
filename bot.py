import os
import telebot
from datetime import datetime
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
DAILY_LIMIT = 6

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URI)
db = client['MovieBot']
files_col = db['files']
users_col = db['users']
config_col = db['settings']

# Force Join စစ်ဆေးလိုသော Channel စာရင်း (ဒီမှာ လိုသလောက် ထည့်နိုင်သည်)
REQUIRED_CHANNELS = [
    {"id": -1003179962336, "link": "https://t.me/moviesbydatahouse"},
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
    # --- (က) Daily Limit စစ်ဆေးခြင်း ---
    if user_id != ADMIN_ID: # Admin မဟုတ်မှ စစ်မယ်
        user = users_col.find_one({"_id": user_id})
        
        # User Database ထဲမရှိရင် (မတော်တဆ) ကျော်သွားမယ်
        if user:
            today_str = datetime.now().strftime("%Y-%m-%d")
            last_reset = user.get('last_reset_date')
            daily_count = user.get('daily_count', 0)

            # ရက်မတူတော့ရင် (နေ့ကူးသွားရင်) count ကို 0 ပြန်ထားမယ်
            if last_reset != today_str:
                users_col.update_one({"_id": user_id}, {"$set": {"daily_count": 0, "last_reset_date": today_str}})
                daily_count = 0
            
            # Limit ပြည့်မပြည့် စစ်မယ်
            if daily_count >= DAILY_LIMIT:
                return bot.send_message(user_id, f"⚠️ **ဒီနေ့အတွက် ကြည့်ရှုခွင့် ပြည့်သွားပါပြီ။**\n\n(Free Member သည် တစ်ရက်လျှင် {DAILY_LIMIT} ကားသာကြည့်နိုင်သည်)\n 💎Join VIP member for Unlimited💎", parse_mode="Markdown")

    # --- (ခ) ပုံမှန် Video ပို့ပေးခြင်း ---
    try:
        data = files_col.find_one({"_id": ObjectId(file_db_id)})
        if data:
            # Database ထဲက ပုံသေစာသားကို ရှာပါ
            config = config_col.find_one({"type": "caption_config"})
            permanent_text = config['text'] if config else ""
            
            # မူရင်း Caption နဲ့ ပုံသေစာသားကို ပေါင်းပါ
            final_caption = f"{data['caption']}\n\n{permanent_text}"
            
            # ဗီဒီယိုပို့ပါ
            bot.send_video(user_id, data['file_id'], caption=final_caption)
            
            # --- (ဂ) ပို့ပြီးရင် Count တိုးခြင်း ---
            if user_id != ADMIN_ID:
                users_col.update_one(
                    {"_id": user_id},
                    {"$inc": {"daily_count": 1}, "$set": {"last_reset_date": datetime.now().strftime("%Y-%m-%d")}}
                )
        else:
            bot.send_message(user_id, "❌ ဖိုင်ရှာမတွေ့ပါ။")
    except Exception as e:
        print(f"Error sending movie: {e}")
        bot.send_message(user_id, "❌ Link မှားယွင်းနေပါသည်။")

# --- ၃။ Admin Commands (File Upload) ---

@bot.message_handler(content_types=['video', 'document'], func=lambda m: m.from_user.id == ADMIN_ID)
def handle_file(message):
    file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
    caption = message.caption or "No Title"
    res = files_col.insert_one({"file_id": file_id, "caption": caption})
    share_link = f"https://t.me/{(bot.get_me()).username}?start={res.inserted_id}"
    bot.reply_to(message, f"✅ သိမ်းပြီးပါပြီ!\n\nLink: `{share_link}`", parse_mode="Markdown")

# --- User Data သိမ်းဆည်းခြင်း ---
def register_user(message):
    user_id = message.from_user.id
    username = message.from_user.username or "No Username"
    first_name = message.from_user.first_name
    
    # User ရှိမရှိစစ်ပြီး မရှိမှ အသစ်ထည့်မည်
    user_data = {
        "_id": user_id,
        "username": username,
        "name": first_name
    }
    # users_col ဆိုတဲ့ collection အသစ်တစ်ခုကို သတ်မှတ်ပေးပါ (အပေါ်ပိုင်း Setup မှာ)
    users_col.update_one({"_id": user_id}, {"$set": user_data}, upsert=True)

# --- ၄။ Main logic (Start Command & Force Sub) ---

@bot.message_handler(commands=['start'])
def start(message):
    register_user(message)
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
            markup.add(types.InlineKeyboardButton("♻️ Join ပြီးပါပြီ", callback_data=f"check_{file_db_id}"))
        else:
            markup.add(types.InlineKeyboardButton("♻️ Join ပြီးပါပြီ", callback_data="check_only"))

        # ⚠️ အရေးကြီး - ဒီနေရာမှာ စာပို့ပြီးရင် function ကို ရပ်လိုက်ရပါမယ် (return သုံးရမည်)
        return bot.send_message(user_id, "⚠️ **ဗီဒီယိုကြည့်ရှုရန် အောက်ပါ Channelကို အရင် Join ပေးပါ။**", reply_markup=markup, parse_mode="Markdown")

    # ၃။ အားလုံး Join ပြီးသား ဖြစ်မှသာ ဒီနေရာကို ရောက်လာမည်
    if len(args) > 1:
        send_movie(user_id, args[1]) #
    else:
        bot.send_message(user_id, "မင်္ဂလာပါ! ဇာတ်ကားများကြည့်ရန် - https://t.me/moviesbydatahouse") #

@bot.message_handler(commands=['setcaption'], func=lambda m: m.from_user.id == ADMIN_ID)
def set_permanent_caption(message):
    # Command ရဲ့ နောက်က စာသားကို ယူပါ
    text = message.text.replace('/setcaption', '').strip()
    if not text:
        return bot.reply_to(message, "❌ စာသားထည့်ပေးပါ။ ဥပမာ - `/setcaption @mychannel`", parse_mode="Markdown")
    
    # Database ထဲမှာ သိမ်းပါ
    config_col.update_one({"type": "caption_config"}, {"$set": {"text": text}}, upsert=True)
    bot.reply_to(message, f"✅ ပုံသေစာသားကို `{text}` အဖြစ် ပြောင်းလဲလိုက်ပါပြီ။", parse_mode="Markdown")

# --- ၅။ Callback Handlers (Try Again ခလုတ်များ) ---
# --- Admin Stats & User List ---
@bot.message_handler(commands=['stats'], func=lambda m: m.from_user.id == ADMIN_ID)
def get_stats(message):
    total = users_col.count_documents({})
    bot.reply_to(message, f"📊 **Bot Statistics**\n\nစုစုပေါင်း User အရေအတွက်: `{total}` ယောက်", parse_mode="Markdown")

@bot.message_handler(commands=['users'], func=lambda m: m.from_user.id == ADMIN_ID)
def list_users(message):
    users = users_col.find()
    user_list_text = "ID | Username | Name\n" + "-"*30 + "\n"
    for u in users:
        user_list_text += f"{u['_id']} | @{u.get('username')} | {u.get('name')}\n"
    
    # စာသားအရမ်းရှည်နိုင်လို့ ဖိုင်အနေနဲ့ ပို့ပေးမယ်
    with open("users.txt", "w", encoding="utf-8") as f:
        f.write(user_list_text)
    
    with open("users.txt", "rb") as f:
        bot.send_document(message.chat.id, f, caption="👥 Bot အသုံးပြုသူများစာရင်း")

# --- ပိုမိုကောင်းမွန်သော Broadcast Feature (စာရော ပုံပါ ရသည်) ---
@bot.message_handler(commands=['broadcast'], func=lambda m: m.from_user.id == ADMIN_ID)
def broadcast_command(message):
    # Admin က တစ်ခုခုကို Reply ပြန်ပြီး /broadcast လို့ ရိုက်ရပါမယ်
    if not message.reply_to_message:
        return bot.reply_to(message, "❌ Broadcast လုပ်မည့် စာ သို့မဟုတ် ဓာတ်ပုံကို **Reply** လုပ်ပြီး `/broadcast` ဟု ရိုက်ပေးပါ။")

    target_msg = message.reply_to_message
    users = users_col.find()
    success = 0
    fail = 0

    status_msg = bot.send_message(ADMIN_ID, "🚀 Broadcast စတင်နေပါပြီ...")

    for u in users:
        try:
            # copy_message ကို သုံးရင် စာသားရော၊ ပုံရော၊ ဗီဒီယိုပါ မူရင်းအတိုင်း ကူးယူပို့ပေးပါတယ်
            bot.copy_message(u['_id'], ADMIN_ID, target_msg.message_id)
            success += 1
        except:
            fail += 1
            continue
            
    bot.edit_message_text(f"📢 Broadcast ပြီးစီးပါပြီ။\n✅ အောင်မြင်: {success}\n❌ ကျရှုံး: {fail}", ADMIN_ID, status_msg.message_id)
    
@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def check_callback(call):
    user_id = call.from_user.id
    data_parts = call.data.split("_")
    
    not_joined = get_not_joined(user_id)
    
    if not_joined:
        bot.answer_callback_query(call.id, "❌ Channel မ Join ရသေးပါ။", show_alert=True)
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















