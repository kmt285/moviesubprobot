import os
import telebot
import pytz
import requests
from datetime import datetime, timedelta
from telebot import types
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask import Flask, render_template_string, request, jsonify
from threading import Thread
from dotenv import load_dotenv
from telegraph import Telegraph, upload_file

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
movies_col = db['movies'] # Web App အတွက် Collection အသစ်

# Telegraph Account (For Image Hosting)
telegraph = Telegraph()
try:
    telegraph.create_account(short_name='MovieBot')
except:
    pass # Already created

REQUIRED_CHANNELS = [
    {"id": -1003179962336, "link": "https://t.me/moviesbydatahouse"},
]

app = Flask('')

# --- ၂။ HTML Template (Mini Web App Design) ---
WEBAPP_HTML = """
<!DOCTYPE html>
<html lang="my">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Movie Store</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background-color: #141414; color: #fff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; }
        .header { padding: 15px; text-align: center; background: linear-gradient(to bottom, rgba(0,0,0,0.9), rgba(0,0,0,0)); position: sticky; top: 0; z-index: 10; backdrop-filter: blur(5px); }
        .header h2 { margin: 0; color: #E50914; font-size: 24px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; }
        
        .grid-container { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 10px; }
        
        .movie-card { position: relative; border-radius: 4px; overflow: hidden; cursor: pointer; transition: transform 0.2s; aspect-ratio: 2/3; background: #222; }
        .movie-card:active { transform: scale(0.95); }
        
        .movie-poster { width: 100%; height: 100%; object-fit: cover; }
        
        .movie-info { 
            position: absolute; bottom: 0; left: 0; right: 0; 
            background: linear-gradient(to top, rgba(0,0,0,0.9), transparent); 
            padding: 10px 5px; 
        }
        .movie-title { font-size: 11px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: center; }
        
        /* Modal for Details */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 100; align-items: center; justify-content: center; }
        .modal-content { background: #181818; padding: 20px; border-radius: 10px; width: 85%; max-width: 400px; text-align: center; border: 1px solid #333; }
        .modal-poster { width: 150px; border-radius: 5px; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .modal-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
        .modal-desc { font-size: 13px; color: #ccc; margin-bottom: 20px; line-height: 1.4; max-height: 100px; overflow-y: auto; text-align: left; }
        .play-btn { background: #E50914; color: white; border: none; padding: 12px 0; width: 100%; border-radius: 4px; font-weight: bold; font-size: 16px; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .close-btn { background: transparent; border: 1px solid #555; color: #aaa; margin-top: 10px; padding: 8px; width: 100%; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="header"><h2>MOVIE STORE</h2></div>
    
    <div class="grid-container" id="movieGrid">
        <div style="grid-column: 1/-1; text-align:center; padding: 20px; color: #666;">Loading...</div>
    </div>

    <div class="modal" id="movieModal">
        <div class="modal-content">
            <img src="" class="modal-poster" id="mPoster">
            <div class="modal-title" id="mTitle"></div>
            <div class="modal-desc" id="mDesc"></div>
            <button class="play-btn" id="playBtn">▶️ ကြည့်မည်</button>
            <button class="close-btn" onclick="closeModal()">Close</button>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        let allMovies = [];

        fetch('/api/movies')
            .then(res => res.json())
            .then(data => {
                allMovies = data;
                renderMovies(data);
            });

        function renderMovies(movies) {
            const grid = document.getElementById('movieGrid');
            grid.innerHTML = '';
            
            movies.forEach(movie => {
                const card = document.createElement('div');
                card.className = 'movie-card';
                card.onclick = () => openModal(movie);
                card.innerHTML = `
                    <img src="${movie.poster_url}" class="movie-poster" loading="lazy">
                    <div class="movie-info">
                        <div class="movie-title">${movie.title}</div>
                    </div>
                `;
                grid.appendChild(card);
            });
        }

        function openModal(movie) {
            document.getElementById('mPoster').src = movie.poster_url;
            document.getElementById('mTitle').innerText = movie.title;
            document.getElementById('mDesc').innerText = movie.description || "No description";
            
            const playBtn = document.getElementById('playBtn');
            playBtn.onclick = () => {
                tg.sendData("watch_" + movie.file_db_id);
            };
            
            document.getElementById('movieModal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('movieModal').style.display = 'none';
        }
    </script>
</body>
</html>
"""

# --- ၃။ Flask Routes (Web App) ---
@app.route('/')
def home(): 
    return "Bot is running with Web App!"

@app.route('/webapp')
def webapp():
    return render_template_string(WEBAPP_HTML)

@app.route('/api/movies')
def get_movies():
    # နောက်ဆုံးတင်ထားသော ကားများကို ရှေ့ဆုံးမှပြမည်
    movies = list(movies_col.find().sort('_id', -1).limit(100))
    output = []
    for m in movies:
        output.append({
            "title": m.get('title', 'Unknown'),
            "poster_url": m.get('poster_url', ''),
            "description": m.get('description', ''),
            "file_db_id": m.get('file_db_id', '')
        })
    return jsonify(output)

# --- ၄။ Utility Functions ---
def get_not_joined(user_id):
    """User မ Join ရသေးသော Channel များစာရင်းကို ပြန်ပေးမည်"""
    not_joined = []
    if user_id == ADMIN_ID: return []
    for ch in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(ch['id'], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(ch)
        except Exception as e:
            print(f"DEBUG Error: {e}")
            continue
    return not_joined

def send_movie(user_id, file_db_id):
    # မူရင်း Logic အတိုင်း Limit စစ်ဆေးပြီး ပို့ပေးမည်
    protect_content = False
    is_vip = False
    
    if user_id != ADMIN_ID:
        user = users_col.find_one({"_id": user_id})
        if user:
            vip_expiry = user.get('vip_expiry')
            if vip_expiry and vip_expiry > datetime.now():
                is_vip = True
            
            # Reset Logic
            yangon_tz = pytz.timezone('Asia/Yangon')
            today_str = datetime.now(yangon_tz).strftime("%Y-%m-%d")
            last_reset = user.get('last_reset_date')
            
            if last_reset != today_str:
                users_col.update_one({"_id": user_id}, {
                    "$set": {"daily_total": 0, "daily_save": 0, "last_reset_date": today_str}
                })
                user['daily_total'] = 0
                user['daily_save'] = 0
            
            daily_total = user.get('daily_total', 0)
            daily_save = user.get('daily_save', 0)

            if not is_vip:
                if daily_total >= FREE_DAILY_LIMIT:
                    return bot.send_message(user_id, "⚠️ Daily Limit Exceeded!")
                if daily_save >= FREE_SAVE_LIMIT:
                    protect_content = True
            else:
                if daily_save >= VIP_SAVE_LIMIT:
                    protect_content = True

    try:
        data = files_col.find_one({"_id": ObjectId(file_db_id)})
        if data:
            config = config_col.find_one({"type": "caption_config"})
            permanent_text = config['text'] if config else ""
            status_text = "🌟 Premium User" if is_vip else "👤 Free User"
            final_caption = f"{data['caption']}\n\n{permanent_text}\n\n{status_text}"
            
            bot.send_video(user_id, data['file_id'], caption=final_caption, protect_content=protect_content)
            
            if user_id != ADMIN_ID:
                update_query = {"$inc": {"daily_total": 1}}
                if not protect_content:
                    update_query["$inc"]["daily_save"] = 1
                users_col.update_one({"_id": user_id}, update_query)
        else:
            bot.send_message(user_id, "❌ ဖိုင်ရှာမတွေ့ပါ။")
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(user_id, "❌ Error sending file.")

# --- ၅။ Admin Commands & Web App Creation Flow ---

# [NEW] Admin က Poster Forward လုပ်ရင် Web App ထဲထည့်မယ့် Flow (Fixed Version)
@bot.message_handler(content_types=['photo'], func=lambda m: m.from_user.id == ADMIN_ID)
def handle_poster_upload(message):
    if not message.caption:
        return bot.reply_to(message, "⚠️ Caption မပါပါ။ (Poster + Title/Description လိုအပ်သည်)")

    try:
        status_msg = bot.reply_to(message, "⏳ Uploading Poster...")
        
        # 1. Get File Path from Telegram
        file_info = bot.get_file(message.photo[-1].file_id)
        file_url = f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}'
        
        # 2. Download Image
        response = requests.get(file_url)
        if response.status_code != 200:
            return bot.reply_to(message, "❌ ဓာတ်ပုံဒေါင်းလုပ်ဆွဲမရပါ။")

        # 3. Direct Upload to Telegra.ph (Using requests instead of library)
        # ယာယီဖိုင်သိမ်းစရာမလိုဘဲ Memory ထဲကနေ တန်းတင်ပါမယ် (ပိုမြန်သည်)
        files = {
            'file': ('poster.jpg', response.content, 'image/jpeg')
        }
        
        upload_response = requests.post('https://telegra.ph/upload', files=files)
        upload_data = upload_response.json()

        # Error handling for upload
        if isinstance(upload_data, list) and 'src' in upload_data[0]:
            poster_path = upload_data[0]['src']
            poster_url = f"https://telegra.ph{poster_path}"
            
            # 4. Success - Ask for DB ID
            msg = bot.edit_message_text(
                f"✅ Poster Uploaded!\n\n🔗 URL: {poster_url}\n\n👇 **ဒီကားအတွက် Database ID (File ID) ကို Reply ပြန်ပေးပါ။**\n(files collection ထဲက _id ကို copy ကူးထည့်ပါ)",
                chat_id=message.chat.id,
                message_id=status_msg.message_id
            )
            
            # Save context
            bot.register_next_step_handler(msg, save_movie_to_webapp, 
                                         poster_url=poster_url, 
                                         original_caption=message.caption)
        else:
            bot.edit_message_text(f"❌ Upload Failed: {upload_data}", chat_id=message.chat.id, message_id=status_msg.message_id)
            
    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, f"❌ Error: {e}")

def save_movie_to_webapp(message, poster_url, original_caption):
    file_db_id = message.text.strip()
    
    # Check if ID is valid ObjectId
    if not ObjectId.is_valid(file_db_id):
        return bot.reply_to(message, "❌ ID မှားယွင်းနေပါသည်။ (Must be valid ObjectId)")

    # Separate Title and Description
    lines = original_caption.split('\n')
    title = lines[0] # First line is title
    description = "\n".join(lines[1:]) # Rest is description
    
    movie_data = {
        "title": title,
        "description": description,
        "poster_url": poster_url,
        "file_db_id": file_db_id,
        "created_at": datetime.now()
    }
    
    movies_col.insert_one(movie_data)
    bot.reply_to(message, f"✅ **Web App တွင် သိမ်းဆည်းပြီးပါပြီ!**\n\n🎬 Title: {title}")


# Regular File Upload (Old Method)
@bot.message_handler(content_types=['video', 'document'], func=lambda m: m.from_user.id == ADMIN_ID)
def handle_file(message):
    file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
    caption = message.caption or "No Title"
    res = files_col.insert_one({"file_id": file_id, "caption": caption})
    
    # ဒီနေရာမှာ ID ကို Copy ကူးလို့လွယ်အောင် ပို့ပေးမယ်
    share_link = f"https://t.me/{(bot.get_me()).username}?start={res.inserted_id}"
    bot.reply_to(message, f"✅ Database သို့ သိမ်းပြီး!\n\n🆔 ID: `{res.inserted_id}`\n(Web App တင်ရန် ဤ ID ကို သုံးပါ)\n\nLink: `{share_link}`", parse_mode="Markdown")

# --- ၆။ User Interactions ---

# [NEW] Web App Data Handler
@bot.message_handler(content_types=['web_app_data'])
def web_app_data_handler(message):
    try:
        data = message.web_app_data.data # "watch_698af..."
        if data.startswith("watch_"):
            file_db_id = data.split("_")[1]
            
            # Check Force Sub
            if get_not_joined(message.from_user.id):
                return bot.send_message(message.chat.id, "⚠️ Channel အရင် Join ပေးပါ!", 
                                      reply_markup=types.ReplyKeyboardRemove())
            
            send_movie(message.from_user.id, file_db_id)
    except Exception as e:
        print(e)

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    users_col.update_one({"_id": user_id}, {"$set": {"username": username}}, upsert=True)
    
    args = message.text.split()
    not_joined = get_not_joined(user_id)

    # Web App Button
    web_app_btn = types.WebAppInfo("https://moviesubprobot.onrender.com") # ⚠️ REPLACE THIS
    
    if not_joined:
        markup = types.InlineKeyboardMarkup()
        for ch in not_joined:
            markup.add(types.InlineKeyboardButton("📢 Join Channel", url=ch['link']))
        
        callback_data = f"check_{args[1]}" if len(args) > 1 else "check_only"
        markup.add(types.InlineKeyboardButton("♻️ Join ပြီးပါပြီ", callback_data=callback_data))
        return bot.send_message(user_id, "⚠️ **ဗီဒီယိုကြည့်ရှုရန် အောက်ပါ Channelကို အရင် Join ပေးပါ။**", reply_markup=markup, parse_mode="Markdown")

    if len(args) > 1:
        send_movie(user_id, args[1])
    else:
        # Start နှိပ်ရင် Web App ဖွင့်မယ့် ခလုတ်ပြမယ်
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton(text="🎬 Movie Store", web_app=web_app_btn))
        bot.send_message(user_id, "👇 ရုပ်ရှင်ကြည့်ရန် အောက်ပါ ခလုတ်ကို နှိပ်ပါ!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def check_callback(call):
    user_id = call.from_user.id
    data_parts = call.data.split("_")
    
    if get_not_joined(user_id):
        bot.answer_callback_query(call.id, "❌ Channel မ Join ရသေးပါ။", show_alert=True)
    else:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        if len(data_parts) > 1 and data_parts[1] != "only":
            send_movie(user_id, data_parts[1])
        else:
            # Join ပြီးရင် Web App ခလုတ်ပို့ပေးမယ်
            web_app_btn = types.WebAppInfo("https://moviesubprobot.onrender.com") # ⚠️ REPLACE THIS
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton(text="🎬 Movie Store", web_app=web_app_btn))
            bot.send_message(user_id, "✅ Join ပြီးပါပြီ။", reply_markup=markup)

# Admin Commands (Stats, VIP, etc.) - မူရင်းအတိုင်းထားသည်
@bot.message_handler(commands=['stats'], func=lambda m: m.from_user.id == ADMIN_ID)
def get_stats(message):
    total = users_col.count_documents({})
    movies = movies_col.count_documents({})
    bot.reply_to(message, f"📊 **Stats**\nUsers: `{total}`\nMovies in WebApp: `{movies}`", parse_mode="Markdown")

@bot.message_handler(commands=['addvip'], func=lambda m: m.from_user.id == ADMIN_ID)
def add_vip(message):
    try:
        args = message.text.split()
        user_id_to_add = int(args[1])
        days = int(args[2])
        expiry = datetime.now() + timedelta(days=days if days > 0 else 36500)
        users_col.update_one({"_id": user_id_to_add}, {"$set": {"vip_expiry": expiry}}, upsert=True)
        bot.reply_to(message, "✅ VIP Added.")
    except:
        bot.reply_to(message, "Error.")

@bot.message_handler(commands=['broadcast'], func=lambda m: m.from_user.id == ADMIN_ID)
def broadcast_command(message):
    if not message.reply_to_message: return
    users = users_col.find()
    count = 0
    for u in users:
        try:
            bot.copy_message(u['_id'], ADMIN_ID, message.reply_to_message.message_id)
            count += 1
        except: pass
    bot.reply_to(message, f"Sent to {count} users.")

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

if __name__ == "__main__":
    Thread(target=run).start()
    bot.infinity_polling()


