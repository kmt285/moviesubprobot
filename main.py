import os
import cv2
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# --- Health Check Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- Watermark ဖျက်တဲ့ Logic (Fixed Center Area) ---
async def remove_watermark(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None: return False
    
    h, w, _ = img.shape
    
    # --- ၁။ ဖျက်မယ့် ဧရိယာ (ROI) ကို သတ်မှတ်မယ် ---
    # ပုံတိုင်းရဲ့ အလယ်တည့်တည့်မှာပဲ ရှိတယ်ဆိုလို့ ဒီဂဏန်းတွေ သတ်မှတ်ထားပါတယ်
    # (0.45 မှ 0.55 ဆိုတာ ပုံအမြင့်ရဲ့ 45% နဲ့ 55% ကြားနေရာပါ)
    y1 = int(h * 0.45)  # အပေါ်ဘက် ဘောင် (အနည်းငယ် လျှော့ချထားသည်)
    y2 = int(h * 0.70)  # အောက်ဘက် ဘောင် (အနည်းငယ် တိုးထားသည်)
    x1 = int(w * 0.20)  # ဘယ်ဘက် ဘောင်
    x2 = int(w * 0.80)  # ညာဘက် ဘောင်

    # အဲ့ဒီဧရိယာအကွက်လေးကိုပဲ ဖြတ်ထုတ်မယ်
    roi = img[y1:y2, x1:x2]
    
    # --- ၂။ Text Mask ဖန်တီးခြင်း (ROI အတွင်းမှာပဲ) ---
    # Grayscale ပြောင်း
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # Gradient Method (ကာလာမရွေးဘူး၊ စာရဲ့ အဖုအထစ်ကို ရှာတယ်)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    grad = cv2.morphologyEx(gray_roi, cv2.MORPH_GRADIENT, kernel)
    
    # Thresholding (စာသားတွေကို အဖြူရောင်ဖြစ်အောင် ပြောင်း)
    _, binary_mask = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    
    # Morphological Close (စာလုံးတွေ ပြတ်တောက်မနေအောင် ဆက်ပေးမယ်)
    kernel_connect = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1)) # အလျားလိုက် ဦးစားပေးဆက်မယ်
    connected_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel_connect)
    
    # Dilation (စာလုံးထက် Mask က နည်းနည်းပိုကြီးနေမှ ဖျက်ရင်ပြောင်မှာ)
    final_roi_mask = cv2.dilate(connected_mask, None, iterations=4)
    
    # --- ၃။ Full Image Mask ပြန်ပေါင်းခြင်း ---
    # ပုံအကြီးကြီးအတိုင်း Mask အလွတ်တစ်ခုယူမယ်
    full_mask = np.zeros((h, w), dtype=np.uint8)
    # ခုနက ROI Mask လေးကို သူ့နေရာ (အလယ်) မှာ ပြန်ထည့်မယ်
    full_mask[y1:y2, x1:x2] = final_roi_mask
    
    # --- ၄။ Inpainting (ဖျက်ပြီး အစားထိုးခြင်း) ---
    # Radius 5 သုံးထားတယ်
    result = cv2.inpaint(img, full_mask, 5, cv2.INPAINT_TELEA)
    
    cv2.imwrite(output_path, result)
    return True

async def handle_photo(update: Update, context):
    if not update.message or not update.message.photo:
        return

    msg = await update.message.reply_text("အလယ်ကစာကို ဖျက်နေပါသည်... ⏳")

    try:
        file = await update.message.photo[-1].get_file()
        in_f = f"in_{update.message.message_id}.jpg"
        out_f = f"out_{update.message.message_id}.jpg"
        
        await file.download_to_drive(in_f)
        
        if await remove_watermark(in_f, out_f):
            await update.message.reply_photo(photo=open(out_f, 'rb'))
            await msg.delete()
        else:
            await msg.edit_text("Failed to process image.")
            
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
    print("Bot Started with Fixed Center Mode...")
    app.run_polling()
