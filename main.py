import os
import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# --- Render အတွက် Dummy Web Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- Watermark ဖျက်တဲ့ Logic ---
async def remove_watermark(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None: return False
    
    h, w, _ = img.shape
    
    # ၁။ စာသားရှိနိုင်တဲ့ ဧရိယာကို ချဲ့ထွင်သတ်မှတ်ခြင်း (အပေါ်အောက် ၂၅% မှ ၇၅%)
    cy1, cy2 = int(h * 0.25), int(h * 0.75)
    cx1, cx2 = int(w * 0.15), int(w * 0.85)
    
    # ၂။ အဖြူရောင် နှင့် အနီရောင် စာသားများကို ရှာဖွေခြင်း
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # အဖြူရောင်အတွက် Mask
    lower_white = np.array([0, 0, 200])
    upper_white = np.array([180, 30, 255])
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    
    # အနီရောင်အတွက် Mask (ပုံထဲက အနီရောင်စာသားအတွက်)
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 50, 50])
    upper_red2 = np.array([180, 255, 255])
    mask_red = cv2.inRange(hsv, lower_red1, upper_red1) + cv2.inRange(hsv, lower_red2, upper_red2)
    
    # Mask နှစ်ခုပေါင်းခြင်း
    combined_mask = cv2.bitwise_or(mask_white, mask_red)
    
    # ၃။ အလယ်ဗဟိုကစာသားကိုပဲ ယူမယ်
    final_mask = np.zeros_like(combined_mask)
    final_mask[cy1:cy2, cx1:cx2] = combined_mask[cy1:cy2, cx1:cx2]
    
    # ၄။ Dilation - ရှာတွေ့တဲ့စာသားကို ၃ pixels လောက် ဘေးကို ချဲ့လိုက်ခြင်း (ပိုသန့်အောင်)
    kernel = np.ones((3,3), np.uint8)
    final_mask = cv2.dilate(final_mask, kernel, iterations=1)
    
    # ၅။ Inpaint (Radius ကို 7 အထိ တိုးလိုက်ပါမယ်)
    result = cv2.inpaint(img, final_mask, 7, cv2.INPAINT_TELEA)
    
    cv2.imwrite(output_path, result)
    return True

async def handle_photo(update: Update, context):
    file = await update.message.photo[-1].get_file()
    in_f, out_f = f"in_{update.message.message_id}.jpg", f"out_{update.message.message_id}.jpg"
    await file.download_to_drive(in_f)
    if await remove_watermark(in_f, out_f):
        await update.message.reply_photo(photo=open(out_f, 'rb'))
    os.remove(in_f); os.remove(out_f)

if __name__ == '__main__':
    # Web Server ကို Thread တစ်ခုနဲ့ သီးသန့် run ထားမယ်
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # Telegram Bot ကို Run မယ်
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.run_polling()


