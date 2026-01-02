import os
import cv2
import numpy as np
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def remove_watermark(input_path, output_path):
    img = cv2.imread(input_path)
    if img is None: return False
    
    h, w, _ = img.shape
    # အလယ်ဗဟို ဧရိယာကို သတ်မှတ်ခြင်း (အပေါ်အောက် 30%-70%၊ ဘယ်ညာ 20%-80%)
    cy1, cy2 = int(h * 0.3), int(h * 0.7)
    cx1, cx2 = int(w * 0.2), int(w * 0.8)
    
    # စာသားရှာဖွေရန် Grayscale ပြောင်းပြီး Mask လုပ်ခြင်း
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    
    # အလယ်ဗဟိုက Mask ကိုပဲ ယူခြင်း
    final_mask = np.zeros_like(mask)
    final_mask[cy1:cy2, cx1:cx2] = mask[cy1:cy2, cx1:cx2]
    
    # Inpaint သုံးပြီး ဖျက်ခြင်း
    result = cv2.inpaint(img, final_mask, 7, cv2.INPAINT_TELEA)
    cv2.imwrite(output_path, result)
    return True

async def handle_docs_and_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ဓာတ်ပုံ သို့မဟုတ် File အနေနဲ့ပို့တဲ့ ပုံကို ယူခြင်း
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    else:
        file = await update.message.document.get_file()

    input_file = f"in_{update.message.message_id}.jpg"
    output_file = f"out_{update.message.message_id}.jpg"
    
    await file.download_to_drive(input_file)
    await update.message.reply_text("Watermark ဖျက်နေပါတယ်၊ ခဏစောင့်ပေးပါ...")

    success = await remove_watermark(input_file, output_file)
    
    if success:
        await update.message.reply_photo(photo=open(output_file, 'rb'), caption="ပြီးပါပြီ!")
    else:
        await update.message.reply_text("Error ဖြစ်သွားပါတယ်။")

    # ဖိုင်များကို ပြန်ဖျက်ခြင်း
    if os.path.exists(input_file): os.remove(input_file)
    if os.path.exists(output_file): os.remove(output_file)

if __name__ == '__main__':
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_docs_and_photos))
    print("Bot is running...")
    app.run_polling()