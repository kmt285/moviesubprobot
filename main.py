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
    cy1, cy2, cx1, cx2 = int(h*0.3), int(h*0.7), int(w*0.2), int(w*0.8)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    final_mask = np.zeros_like(mask)
    final_mask[cy1:cy2, cx1:cx2] = mask[cy1:cy2, cx1:cx2]
    result = cv2.inpaint(img, final_mask, 7, cv2.INPAINT_TELEA)
    cv2.imwrite(output_path, result)
    return True

async def handle_photo(update: Update, context):
    file = await update.message.photo[-1].get_file()
    in_f, out_f = f"in_{update.id}.jpg", f"out_{update.id}.jpg"
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
