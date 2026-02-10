import os
import time
import requests
import telebot
from flask import Flask, jsonify, request, render_template_string
from threading import Thread
from telebot import types
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
admin_env = os.getenv('ADMIN_IDS', '')
ADMIN_IDS = [int(i) for i in admin_env.split(',') if i.strip()]

bot = telebot.TeleBot(BOT_TOKEN)

# MongoDB Setup
try:
    client = MongoClient(MONGO_URI)
    db = client['MyBotDB']
    config_col = db['settings']
    movies_col = db['movies']  # Movie တွေသိမ်းမယ့် Collection
    print("✅ MongoDB Connected Successfully!")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# --- Helper Function: Upload Image to Telegraph ---
# Web App မှာ ပုံပေါ်ဖို့အတွက် Telegram က ပုံကို Link ပြောင်းပေးရပါမယ်
def upload_to_telegraph(file_path):
    try:
        url = "https://telegra.ph/upload"
        files = {'file': ('image.jpg', open(file_path, 'rb'), 'image/jpeg')}
        response = requests.post(url, files=files)
        src = response.json()[0]['src']
        return f"https://telegra.ph{src}"
    except Exception as e:
        print(e)
        return None

# --- Flask Server (Mini App Backend) ---
app = Flask(__name__)

# Netflix Style HTML Template (Simple Version)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Movie App</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #141414; color: white; font-family: sans-serif; }
        .movie-card { transition: transform 0.3s; }
        .movie-card:active { transform: scale(0.95); }
    </style>
</head>
<body class="p-4">
    <h1 class="text-2xl font-bold text-red-600 mb-4">MOVIES</h1>
    
    <div id="movie-grid" class="grid grid-cols-2 gap-4">
        </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        // Fetch Movies from API
        fetch('/api/movies')
            .then(response => response.json())
            .then(data => {
                const grid = document.getElementById('movie-grid');
                data.forEach(movie => {
                    const card = document.createElement('div');
                    card.className = 'movie-card bg-gray-800 rounded-lg overflow-hidden relative';
                    card.innerHTML = `
                        <img src="${movie.poster}" class="w-full h-48 object-cover">
                        <div class="p-2">
                            <h3 class="text-sm font-bold truncate">${movie.title}</h3>
                            <p class="text-xs text-gray-400 truncate">${movie.description}</p>
                            <button onclick="watchMovie('${movie.msg_id}')" class="mt-2 w-full bg-red-600 text-white py-1 rounded text-sm">
                                ▶ Watch
                            </button>
                        </div>
                    `;
                    grid.appendChild(card);
                });
            });

        function watchMovie(msgId) {
            // Bot ကို start param နဲ့ လှမ်းခေါ်မည်
            // user က bot ထဲရောက်တာနဲ့ file auto ကျလာမည်
            tg.openTelegramLink(`https://t.me/${tg.initDataUnsafe.bot_username}?start=${msgId}`);
            tg.close();
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/movies')
def get_movies():
    # နောက်ဆုံးတင်တဲ့ ၂၀ ကားကို ယူမည်
    movies = list(movies_col.find({}, {'_id': 0}).sort('_id', -1).limit(20))
    return jsonify(movies)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- Bot Helpers ---
def get_config():
    data = config_col.find_one({"_id": "bot_settings"})
    return data if data else {}

def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- Admin Movie Upload Wizard (The Manual Part) ---
user_steps = {} # Temporary storage for wizard

@bot.message_handler(commands=['add'], func=lambda m: is_admin(m.from_user.id))
def add_movie_step1(message):
    msg = bot.reply_to(message, "📸 **အဆင့် (၁):** Movie Poster ပုံကို ပို့ပေးပါ။")
    bot.register_next_step_handler(msg, process_poster)

def process_poster(message):
    if not message.photo:
        return bot.reply_to(message, "❌ ပုံမဟုတ်ပါ။ `/add` ပြန်ခေါ်ပါ။")
    
    # Download and Upload to Telegraph for permanent link
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    with open("temp.jpg", 'wb') as new_file:
        new_file.write(downloaded_file)
    
    poster_url = upload_to_telegraph("temp.jpg")
    os.remove("temp.jpg") # Clean up
    
    if not poster_url:
        return bot.reply_to(message, "❌ Error uploading image.")

    user_steps[message.from_user.id] = {'poster': poster_url}
    msg = bot.reply_to(message, "📝 **အဆင့် (၂):** နာမည် နှင့် အညွှန်း ရေးပို့ပါ။\n(Format: Name | Description)")
    bot.register_next_step_handler(msg, process_details)

def process_details(message):
    try:
        text = message.text.split('|')
        title = text[0].strip()
        desc = text[1].strip() if len(text) > 1 else "No description"
        
        user_steps[message.from_user.id]['title'] = title
        user_steps[message.from_user.id]['description'] = desc
        
        msg = bot.reply_to(message, "📂 **အဆင့် (၃):** DB Channel ထဲက Movie File ကို ဒီကို Forward လုပ်ပေးပါ။")
        bot.register_next_step_handler(msg, process_file)
    except:
        bot.reply_to(message, "❌ Format မှားနေပါသည်။ `/add` ပြန်လုပ်ပါ။")

def process_file(message):
    if not message.forward_from_chat:
        return bot.reply_to(message, "⚠️ DB Channel ကနေ forward လုပ်ထားတာ မဟုတ်ပါ။")
    
    data = user_steps.get(message.from_user.id)
    movie_data = {
        "title": data['title'],
        "description": data['description'],
        "poster": data['poster'],
        "msg_id": message.forward_from_message_id, # File ID link
        "created_at": time.time()
    }
    
    # Save to MongoDB
    movies_col.insert_one(movie_data)
    bot.reply_to(message, f"✅ **Saved Successfully!**\nMovie: {data['title']}\nAdded to Mini App.")
    user_steps.pop(message.from_user.id, None)

# --- Existing Bot Logic (Start & File Delivery) ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    config = get_config()
    args = message.text.split()
    payload = args[1] if len(args) > 1 else "only"

    # Join Check (Simplified for brevity)
    # ... (Your existing join check code here) ...

    if payload != "only":
        send_file(user_id, payload)
    else:
        # Show Mini App Button
        markup = types.InlineKeyboardMarkup()
        web_app = types.WebAppInfo(url=f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}") 
        # Note: Render URL မသိရင် bot father မှာထည့်မဲ့ link ကို hardcode ထည့်လဲရတယ်
        
        markup.add(types.InlineKeyboardButton("🎬 Open Movie App", web_app=web_app))
        bot.send_message(user_id, "Welcome to Movie Bot!", reply_markup=markup)

def send_file(user_id, msg_id):
    config = get_config()
    db_id = config.get('db_channel_id')
    try:
        bot.copy_message(user_id, db_id, int(msg_id))
    except Exception as e:
        bot.send_message(user_id, "❌ File Not Found or Bot not Admin in DB Channel.")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
