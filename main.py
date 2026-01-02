import os
import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# --- Render Health Check ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- Watermark ဖျက်တဲ့ Logic (Fixed Box Method) ---
async def remove_watermark(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None: return False
    
    h, w, _ = img.shape
    
    # ==========================================
    # ချိန်ညှိရန် နေရာ (Box Configuration)
    # ==========================================
    # ပို့ပေးထားတဲ့ Reference ပုံထဲက အဖြူကွက် အရွယ်အစားအတိုင်း မှန်းထားပါတယ်
    # လိုအပ်ရင် ဒီဂဏန်းတွေကို အတိုးအလျှော့ လုပ်နိုင်ပါတယ်
    
    # 35% of Image Width (အလျား ၃၅ ရာခိုင်နှုန်း)
    BOX_WIDTH_PCT = 0.35  
    
    # 8% of Image Height (အမြင့် ၈ ရာခိုင်နှုန်း)
    BOX_HEIGHT_PCT = 0.08 
    
    # ==========================================

    # ၁။ အလယ်မှတ် (Center Point) ရှာခြင်း
    center_x, center_y = w // 2, h // 2
    
    # ၂။ လေးထောင့်ကွက်၏ Pixel အကျယ်အဝန်းကို တွက်ခြင်း
    box_w = int(w * BOX_WIDTH_PCT)
    box_h = int(h * BOX_HEIGHT_PCT)
    
    # ၃။ လေးထောင့်ကွက်၏ ထောင့်စွန်း Coordinates များကို တွက်ခြင်း
    x1 = center_x - (box_w // 2)
    x2 = center_x + (box_w // 2)
    y1 = center_y - (box_h // 2)
    y2 = center_y + (box_h // 2)

    # ၄။ Mask ဖန်တီးခြင်း
    mask = np.zeros(img.shape[:2], dtype=np.uint8)
    # တွက်ချက်ထားသော နေရာကို အဖြူရောင် (255) ဖြင့် Mask လုပ်မည်
    mask[y1:y2, x1:x2] = 255

    # ၅။ Inpainting (အစားထိုး ဖျက်ခြင်း)
    # radius 3 က အနားသတ်တွေကို သေသပ်စေပါတယ်
    result = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
    
    cv2.imwrite(output_path, result)
    return True

async def handle_photo(update: Update, context):
    if not update.message or not update.message.photo:
        return

    # User feedback
    msg = await update.message.reply_text("သတ်မှတ်ထားသော နေရာကွက်ကို ဖျက်နေပါသည်... ⏳")

    try:
        file = await update.message.photo[-1].get_file()
        in_f = f"in_{update.message.message_id}.jpg"
        out_f = f"out_{update.message.message_id}.jpg"
        
        await file.download_to_drive(in_f)
        
        if await remove_watermark(in_f, out_f):
            await update.message.reply_photo(photo=open(out_f, 'rb'))
            await msg.delete()
        else:
            await msg.edit_text("ပုံကို ဖတ်၍မရပါ။")
            
        # Cleanup
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
    print("Bot Started (Fixed Box Mode)...")
    app.run_polling()
