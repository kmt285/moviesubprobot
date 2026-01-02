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

# --- Watermark ဖျက်တဲ့ Logic အသစ် ---
async def remove_watermark(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None: return False
    
    h, w, _ = img.shape
    
    # 1. ရုပ်ထွက်ပိုရှင်းအောင် အရင်လုပ်မယ် (Contrast Boosting)
    # ဒါမှ အရောင်မှိန်နေတဲ့ Watermark တွေကိုပါ မြင်ရမှာ
    alpha = 1.5 # Contrast control
    beta = 0    # Brightness control
    adjusted = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
    
    # 2. Grayscale ပြောင်းမယ်
    gray = cv2.cvtColor(adjusted, cv2.COLOR_BGR2GRAY)
    
    # 3. Edge Detection (Canny) သုံးမယ်
    # ဒါက အရောင်မရွေးဘူး၊ စာသားရဲ့ ဘောင်တွေကို ရှာပေးတယ် (Multicolored text အတွက် အရေးကြီးတယ်)
    edges = cv2.Canny(gray, 50, 150)
    
    # 4. စာသားတွေကို ပိုပြီး ထင်ရှားအောင် Mask လုပ်မယ် (Dilation)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.dilate(edges, kernel, iterations=2)
    
    # 5. Region of Interest (ROI) သတ်မှတ်မယ် 
    # (ပုံတစ်ခုလုံး လျှောက်ဖျက်ရင် ရုပ်ပျက်သွားမှာစိုးလို့ အောက်ခြေနားကိုပဲ ဦးတည်ပြီးဖျက်မယ်)
    # လိုအပ်ရင် ဒီဧရိယာကို ပြင်နိုင်ပါတယ်
    final_mask = np.zeros_like(mask)
    
    # ဥပမာ - ပုံရဲ့ အောက်ခြေ 40% လောက်ကိုပဲ ရှာပြီးဖျက်မယ်
    y_start = int(h * 0.60) 
    final_mask[y_start:h, 0:w] = mask[y_start:h, 0:w]
    
    # 6. Inpainting (စာသားနေရာကို ဘေးကအရောင်နဲ့ အစားထိုးမယ်)
    # Radius ကို 3 ထားလိုက်တယ်၊ သိပ်ကြီးရင် ဝါးသွားတတ်လို့ပါ
    result = cv2.inpaint(img, final_mask, 3, cv2.INPAINT_TELEA)
    
    cv2.imwrite(output_path, result)
    return True

async def handle_photo(update: Update, context):
    if not update.message or not update.message.photo:
        return

    # User ကို စောင့်နေကြောင်း အသိပေးမယ်
    processing_msg = await update.message.reply_text("ဓာတ်ပုံကို ပြုပြင်နေပါသည်... ခဏစောင့်ပါ ⏳")

    try:
        file = await update.message.photo[-1].get_file()
        in_f = f"in_{update.message.message_id}.jpg"
        out_f = f"out_{update.message.message_id}.jpg"
        
        await file.download_to_drive(in_f)
        
        if await remove_watermark(in_f, out_f):
            await update.message.reply_photo(photo=open(out_f, 'rb'))
            await processing_msg.delete() # ပြီးရင် msg ပြန်ဖျက်
        else:
            await processing_msg.edit_text("ပုံကို ပြုပြင်၍ မရပါ။")
            
        # Cleanup
        if os.path.exists(in_f): os.remove(in_f)
        if os.path.exists(out_f): os.remove(out_f)
            
    except Exception as e:
        print(f"Error: {e}")
        await processing_msg.edit_text("Error တစ်ခုဖြစ်သွားပါတယ် :( ")

if __name__ == '__main__':
    # Web Server Run
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # Bot Start
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Error: BOT_TOKEN is missing!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        print("Bot is polling...")
        app.run_polling()
