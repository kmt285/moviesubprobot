import os
import telebot
from telebot import types

# --- ၁။ Configuration ပိုင်း (မိမိ Channel ID များ ဖြည့်ရန်) ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

bot = telebot.TeleBot(API_TOKEN)

# စစ်ဆေးလိုသော Channel စာရင်း (Rose Bot တွင် /id ဖြင့် ID ယူပါ)
# -100 ပါသော ID အပြည့်အစုံ ထည့်ရပါမည်
REQUIRED_CHANNELS = [
    {"id": --1003622691900, "link": "https://t.me/mmsubchannelfu"},
    {"id": --1003179962336, "link": "https://t.me/moviesbydatahouse"},
    # လိုအပ်သလောက် ထပ်တိုးနိုင်ပါသည်
]

# --- ၂။ Force Subscribe စစ်ဆေးသည့် Function ---
def get_not_joined(user_id):
    """User မ Join ရသေးသော Channel များစာရင်းကို ပြန်ပေးမည်"""
    not_joined = []
    
    # Admin ဖြစ်နေရင် စစ်စရာမလိုဘဲ ကျော်ပေးမည်
    if user_id == ADMIN_ID:
        return []

    for ch in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(ch['id'], user_id)
            # member, administrator, creator မဟုတ်လျှင် မ Join သေးဟု သတ်မှတ်
            if member.status not in ['member', 'administrator', 'creator']:
                not_joined.append(ch)
        except Exception as e:
            # Bot ကို Channel ထဲမှာ Admin မခန့်ထားလျှင် ဤနေရာတွင် Error တက်မည်
            print(f"Error checking channel {ch['id']}: {e}")
            continue
            
    return not_joined

# --- ၃။ Message Handler (Main Logic) ---
@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    
    # User Join ထားခြင်း ရှိမရှိ စစ်ဆေးခြင်း
    not_joined_list = get_not_joined(user_id)

    if not_joined_list:
        # မ Join ရသေးသော Channel များအတွက် Button များထုတ်ပေးမည်
        markup = types.InlineKeyboardMarkup()
        for ch in not_joined_list:
            btn = types.InlineKeyboardButton("📢 Join Channel", url=ch['link'])
            markup.add(btn)
        
        # Try Again ခလုတ် (Option)
        # အကယ်၍ /start နှိပ်ထားတာဆိုရင် command ပါတဲ့ start link အတွက် logic ထည့်နိုင်သည်
        markup.add(types.InlineKeyboardButton("♻️ အားလုံး Join ပြီးပါပြီ", callback_data="check_sub"))

        bot.send_message(
            message.chat.id, 
            "⚠️ **ဗီဒီယိုကြည့်ရှုရန် အောက်ပါ Channel အားလုံးကို အရင် Join ပေးပါ။**", 
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    # --- ဒီအောက်မှာမှ Join ပြီးသား User တွေအတွက် လုပ်ဆောင်ချက်များ ရေးရန် ---
    if message.text == "/start":
        bot.send_message(message.chat.id, "✅ မင်္ဂလာပါ! Channel အားလုံး Join ပြီးပါပြီ။ ဇာတ်ကား ID ပို့ပေးပါ။")
    else:
        # ဥပမာ - Movie ID ရှာဖွေခြင်း logic များ ဒီမှာ ထည့်ပါ
        bot.reply_to(message, f"သင်ပို့လိုက်သော ID `{message.text}` ကို ရှာဖွေနေပါသည်...")

# --- ၄။ Try Again ခလုတ်အတွက် Callback ---
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_callback(call):
    user_id = call.from_user.id
    if not get_not_joined(user_id):
        bot.answer_callback_query(call.id, "✅ ကျေးဇူးတင်ပါတယ်! အခု စတင်အသုံးပြုနိုင်ပါပြီ။", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "ဇာတ်ကား ID ကို ရိုက်ထည့်ပေးပါ။")
    else:
        bot.answer_callback_query(call.id, "❌ Channel အားလုံး မ Join ရသေးပါ။", show_alert=True)

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()

