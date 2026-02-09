import os
import telebot
import pytz
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
FREE_DAILY_LIMIT = 10
FREE_SAVE_LIMIT = 2
VIP_SAVE_LIMIT = 50

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
    # Default Settings
    protect_content = False  # ပုံမှန်အားဖြင့် Save ခွင့်ပြုမည်
    is_vip = False
    
    # --- (က) User Status စစ်ဆေးခြင်း ---
    if user_id != ADMIN_ID:
        user = users_col.find_one({"_id": user_id})
        
        if user:
            is_vip = user.get('is_vip', False)
            
            # Reset Logic (VIP ရော Free ရော ရက်ကူးရင် Reset လုပ်ပေးရမယ်)
            yangon_tz = pytz.timezone('Asia/Yangon')
            today_str = datetime.now(yangon_tz).strftime("%Y-%m-%d")
            last_reset = user.get('last_reset_date')
            
            # Counter တွေကို ယူမယ် (မရှိရင် 0)
            daily_total = user.get('daily_total', 0)
            daily_save = user.get('daily_save', 0)

            # ရက်ကူးသွားရင် Reset လုပ်မယ်
            if last_reset != today_str:
                users_col.update_one({"_id": user_id}, {
                    "$set": {
                        "daily_total": 0, 
                        "daily_save": 0, 
                        "last_reset_date": today_str
                    }
                })
                daily_total = 0
                daily_save = 0
            
            # --- Limit စစ်ဆေးခြင်း ---
            if not is_vip:
                # Free User ဆိုရင် Total Limit (10 ကား) စစ်မယ်
                if daily_total >= FREE_DAILY_LIMIT:
                    return bot.send_message(user_id, 
                        f"⚠️ Free User Daily Limit Exceeded!\n ⏳Please try again after 24 hours\n\n"
                        f"💎 Join VIP for Unlimited 💎 @moviestoreadmin", 
                        parse_mode="Markdown")
                
                # Free User Save Limit Check
                if daily_save >= FREE_SAVE_LIMIT:
                    protect_content = True

            else:
                # VIP User ဆိုရင် Save Limit (50 ကား) ပဲ စစ်မယ် (Total Limit မစစ်ဘူး)
                if daily_save >= VIP_SAVE_LIMIT:
                    protect_content = True
                    # VIP ကို Save မရတော့ကြောင်း အသိပေးချင်ရင် ဒီအောက်က Comment ကို ဖွင့်ပါ
                    # bot.send_message(user_id, "⚠️ VIP Save Limit ပြည့်သွားပါပြီ။ ယခုကားမှစ၍ Save ခွင့်မပြုတော့ပါ။")

    # --- (ခ) Video ပို့ပေးခြင်း ---
    try:
        data = files_col.find_one({"_id": ObjectId(file_db_id)})
        if data:
            # Caption ပြင်ဆင်ခြင်း
            config = config_col.find_one({"type": "caption_config"})
            permanent_text = config['text'] if config else ""
            
            status_text = "🌟 Premium User" if is_vip else "👤 Free User"
            final_caption = f"{data['caption']}\n\n{permanent_text}\n\n{status_text}"
            
            # ဗီဒီယိုပို့ပါ (protect_content ကို ဒီနေရာမှာ သုံးပါပြီ)
            bot.send_video(user_id, data['file_id'], caption=final_caption, protect_content=protect_content)
            
            # --- (ဂ) Database Update လုပ်ခြင်း ---
            # VIP ရော Free ရော Count တိုးပေးရမယ် (ဒါမှ Limit စစ်လို့ရမှာ)
            if user_id != ADMIN_ID:
                update_query = {"$inc": {"daily_total": 1}}
                
                # Save လုပ်ခွင့်ရတဲ့ အလုံးဆိုရင် daily_save ကိုပါ +1 တိုးမယ်
                # (protect_content=False ဆိုရင် Save လို့ရတာမို့ Count တိုးမယ်)
                if not protect_content:
                    update_query["$inc"]["daily_save"] = 1
                    
                users_col.update_one(
                    {"_id": user_id},
                    update_query
                )
        else:
            bot.send_message(user_id, "❌ ဖိုင်ရှာမတွေ့ပါ။")
    except Exception as e:
        print(f"Error: {e}")
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

# --- VIP Management Commands ---
@bot.message_handler(commands=['addvip'], func=lambda m: m.from_user.id == ADMIN_ID)
def add_vip(message):
    try:
        # Command ပုံစံ: /addvip 123456789
        user_id_to_add = int(message.text.split()[1])
        users_col.update_one({"_id": user_id_to_add}, {"$set": {"is_vip": True}}, upsert=True)
        bot.reply_to(message, f"✅ User ID `{user_id_to_add}` ကို VIP အဖြစ် သတ်မှတ်လိုက်ပါပြီ။", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ ID မှားယွင်းနေပါသည်။\nအသုံးပြုပုံ: `/addvip <user_id>`", parse_mode="Markdown")

@bot.message_handler(commands=['removevip'], func=lambda m: m.from_user.id == ADMIN_ID)
def remove_vip(message):
    try:
        user_id_to_remove = int(message.text.split()[1])
        users_col.update_one({"_id": user_id_to_remove}, {"$set": {"is_vip": False}})
        bot.reply_to(message, f"User ID `{user_id_to_remove}` မှ VIP ကို ဖယ်ရှားလိုက်ပါပြီ။", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ Error.")

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



















