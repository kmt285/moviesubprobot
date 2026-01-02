import os
import cv2
import numpy as np
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# --- Health Check ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- Concurrency Control (အရေးကြီးသည်) ---
# တပြိုင်နက် ပုံ ၂ ပုံပဲ လက်ခံမယ်၊ ကျန်တာ တန်းစီခိုင်းမယ် (RAM မပြည့်အောင်)
semaphore = asyncio.Semaphore(2)

# --- Processing Logic (Blocking Code) ---
# ဒီ Function ကို async မတပ်တော့ပါ (Thread ထဲမှာ run မှာမို့လို့)
def process_image_sync(input_path, output_path):
    try:
        img = cv2.imread(input_path)
        if img is None: return False
        
        h, w, _ = img.shape
        
        # --- Settings ---
        BOX_WIDTH_PCT = 0.35
        BOX_HEIGHT_PCT = 0.08
        NEW_TEXT = "@moviesbydatahouse"
        
        # 1. Box Setup
        center_x, center_y = w // 2, h // 2
        box_w = int(w * BOX_WIDTH_PCT)
        box_h = int(h * BOX_HEIGHT_PCT)
        
        x1 = max(0, center_x - (box_w // 2))
        x2 = min(w, center_x + (box_w // 2))
        y1 = max(0, center_y - (box_h // 2))
        y2 = min(h, center_y + (box_h // 2))

        # 2. Blur
        roi = img[y1:y2, x1:x2]
        # Blur အားကို လိုသလို ပြင်ပါ (99, 99)
        blurred_roi = cv2.GaussianBlur(roi, (99, 99), 30)
        img[y1:y2, x1:x2] = blurred_roi

        # 3. Text Overlay
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 2
        target_text_width = box_w * 0.9
        (base_w, base_h), _ = cv2.getTextSize(NEW_TEXT, font, 1.0, thickness)
        font_scale = target_text_width / base_w if base_w > 0 else 1
        
        (text_w, text_h), _ = cv2.getTextSize(NEW_TEXT, font, font_scale, thickness)
        text_x = int(x1 + (box_w - text_w) / 2)
        text_y = int(y1 + (box_h + text_h) / 2)

        # Outline & Text
        cv2.putText(img, NEW_TEXT, (text_x, text_y), font, font_scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
        cv2.putText(img, NEW_TEXT, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        cv2.imwrite(output_path, img)
        return True
    except Exception as e:
        print(f"CV2 Error: {e}")
        return False

async def handle_photo(update: Update, context):
    if not update.message or not update.message.photo:
        return

    # User ကို တန်းစီခိုင်းမယ်
    msg = await update.message.reply_text("ပုံကို လက်ခံရရှိပါပြီ... တန်းစီနေပါသည် ⏳")

    file_id = update.message.photo[-1].file_id
    in_f = f"in_{file_id}.jpg"
    out_f = f"out_{file_id}.jpg"

    try:
        # Semaphore သုံးပြီး တပြိုင်နက် အလုပ်လုပ်မည့် အရေအတွက်ကို ထိန်းချုပ်မယ်
        async with semaphore:
            await msg.edit_text("ပြုပြင်နေပါသည်... (Processing) ⚙️")
            
            # Download Image
            file = await context.bot.get_file(file_id)
            await file.download_to_drive(in_f)
            
            # --- အရေးကြီးဆုံး အပိုင်း ---
            # OpenCV က Blocking ဖြစ်လို့ သီးသန့် Thread တစ်ခုနဲ့ Run ခိုင်းမယ်
            # ဒါမှ Bot က နောက်ဝင်လာတဲ့ စာတွေကို ဆက်ဖတ်နိုင်မှာ
            loop = asyncio.get_running_loop()
            success = await loop.run_in_executor(None, process_image_sync, in_f, out_f)
            # -------------------------

            if success:
                await update.message.reply_photo(photo=open(out_f, 'rb'))
                await msg.delete()
            else:
                await msg.edit_text("Error processing image.")

    except Exception as e:
        print(f"Handler Error: {e}")
        await msg.edit_text("ဆာဗာ Error ဖြစ်သွားပါသည် (ခဏကြာမှ ပြန်စမ်းပါ)။")
        
    finally:
        # ပြီးရင် ဖိုင်တွေကို ချက်ချင်းဖျက် (Storage မပြည့်အောင်)
        if os.path.exists(in_f): os.remove(in_f)
        if os.path.exists(out_f): os.remove(out_f)

if __name__ == '__main__':
    # Web Server for Render
    threading.Thread(target=run_health_server, daemon=True).start()
    
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Error: TOKEN not found")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        # concurrent_updates ထည့်ထားရင် ပိုကောင်းတယ်
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        
        print("Bot Started with Threading & Queue System...")
        app.run_polling()
