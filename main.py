import os
import cv2
import numpy as np
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

# --- Blur Logic (သေသပ်သော ဝါးနည်း) ---
async def blur_watermark(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None: return False
    
    h, w, _ = img.shape
    
    # ==========================================
    # ချိန်ညှိရန် နေရာ (Box Configuration)
    # ==========================================
    # အလယ်က စာတန်းနေရာကို မှန်းထားခြင်း
    BOX_WIDTH_PCT = 0.25   # အကျယ် 30% (လိုရင်တိုးပါ)
    BOX_HEIGHT_PCT = 0.07  # အမြင့် 8%
    # ==========================================

    # ၁။ Center Coordinates တွက်ခြင်း
    center_x, center_y = w // 2, h // 2
    box_w = int(w * BOX_WIDTH_PCT)
    box_h = int(h * BOX_HEIGHT_PCT)
    
    x1 = center_x - (box_w // 2)
    x2 = center_x + (box_w // 2)
    y1 = center_y - (box_h // 2)
    y2 = center_y + (box_h // 2)

    # Boundary Checks (ဘောင်မကျော်အောင် စစ်)
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)

    # ၂။ ROI (Region of Interest) ကို ယူမယ်
    roi = img[y1:y2, x1:x2]

    # ၃။ Gaussian Blur လုပ်မယ် (ဒါက အသားတကျ ဝါးစေတယ်)
    # (51, 51) က ဝါးမယ့် အား (ကိန်းဂဏန်း ကြီးလေ ပိုဝါးလေ)
    # ကိန်းဂဏန်းသည် မကိန်း (Odd Number) ဖြစ်ရမယ်
    blurred_roi = cv2.GaussianBlur(roi, (89, 89), 25)

    # ၄။ မူရင်းပုံထဲ ပြန်ထည့်မယ်
    img[y1:y2, x1:x2] = blurred_roi
    
    # Optional: အနားသတ်တွေ မတောင့်အောင် ထပ်လုပ်ချင်ရင်
    # ရိုးရိုးလေးပဲ ထားလိုက်တာ ပိုကောင်းပါတယ်

    cv2.imwrite(output_path, img)
    return True

async def handle_photo(update: Update, context):
    if not update.message or not update.message.photo:
        return

    msg = await update.message.reply_text("အလယ်ကစာကို ဝါးနေပါသည်... ⏳")

    try:
        file = await update.message.photo[-1].get_file()
        in_f = f"in_{update.message.message_id}.jpg"
        out_f = f"out_{update.message.message_id}.jpg"
        
        await file.download_to_drive(in_f)
        
        if await blur_watermark(in_f, out_f):
            await update.message.reply_photo(photo=open(out_f, 'rb'))
            await msg.delete()
        else:
            await msg.edit_text("ပုံကို ဖတ်၍မရပါ။")
            
        if os.path.exists(in_f): os.remove(in_f)
        if os.path.exists(out_f): os.remove(out_f)
            
    except Exception as e:
        print(f"Error: {e}")
        await msg.edit_text(f"Error: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_health_server, daemon=True).start()
    
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot Started (Blur Mode)...")
    app.run_polling()

