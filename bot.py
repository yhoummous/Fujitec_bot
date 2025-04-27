import os
import logging
import telebot
import qrcode
from flask import Flask, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.lib.units import cm
from barcode import Code128
from barcode.writer import ImageWriter

# === Configure Logging ===
logging.basicConfig(filename='bot.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === Flask App ===
app = Flask(__name__)

# === Bot Configuration ===
API_TOKEN = os.getenv("API_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Example: https://your-bot.vercel.app/
bot = telebot.TeleBot(API_TOKEN)

# === / Route (for webhook setup) ===
@app.route('/', methods=['GET'])
def index():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + 'webhook')
    return "Webhook has been set!", 200

# === /webhook Route (for receiving updates) ===
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return '', 403

# === /start Command ===
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        logo_path = "logo.png"
        with open(logo_path, 'rb') as logo:
            bot.send_photo(message.chat.id, logo, caption=(
                "👋 <b>Welcome to Fujitec Barcode Bot!</b>\n\n"
                "🔹 Easily create professional barcode stickers for your spare parts.\n\n"
                "<b>📄 Manual Entry:</b>\n"
                "Send text like:\n"
                "<code>123456789012, Motor Gear, R12</code>\n"
                "<code>987654321098, Brake Unit, R34</code>\n\n"
                "✅ After sending, the bot will generate and send you a ready-to-print PDF.\n\n"
                "⚡ Let's get started!\n\n"
                "For Support Call @BDM_IT"
            ), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending welcome message: {e}")
        bot.reply_to(message, "❌ Error: Could not send the welcome message with logo.")

# === Handle Manual Entry ===
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    try:
        lines = message.text.strip().split('\n')
        data = []
        for line in lines:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) != 3:
                bot.reply_to(message, "❌ Use format: Barcode, Part Name, Rack")
                return
            data.append(parts)

        generating_msg = bot.reply_to(message, "⏳ Generating your PDF...")

        pdf_path = generate_pdf(data)

        with open(pdf_path, 'rb') as pdf_file:
            bot.send_document(message.chat.id, pdf_file)

        os.remove(pdf_path)
        bot.delete_message(message.chat.id, generating_msg.message_id)

    except Exception as e:
        logger.error(f"Manual entry error: {e}")
        bot.reply_to(message, f"❌ Error: {e}")

# === Generate PDF with Barcode, QR, and Part Name ===
def generate_pdf(labels_data):
    barcode_numbers = [item[0] for item in labels_data]
    pdf_file_name = ",".join(barcode_numbers) + "_labels.pdf"

    width, height = 10 * cm, 15 * cm
    c = canvas.Canvas(pdf_file_name, pagesize=portrait((width, height)))

    for barcode_number, part_name, rack in labels_data:
        barcode_filename = f"{barcode_number}_barcode.png"
        barcode = Code128(barcode_number, writer=ImageWriter())
        barcode.save(barcode_filename[:-4])

        qr_path = f"{barcode_number}_qr.png"
        qr = qrcode.make(f"{barcode_number} | {part_name} | {rack}")
        qr.save(qr_path)

        c.setLineWidth(1)
        c.rect(5, 5, width - 10, height - 10)

        y = height - 1 * cm
        space = 0.7 * cm

        if os.path.exists("logo.png"):
            c.drawImage("logo.png", cm, y - 2*cm, width - 2*cm, 2*cm, preserveAspectRatio=True)
        y -= 2*cm + space

        c.drawImage(barcode_filename, cm, y - 2.5*cm, width - 2*cm, 2.5*cm)
        y -= 2.5*cm + space

        c.drawImage(qr_path, cm + 2*cm, y - 3*cm, 3*cm, 3*cm)
        y -= 3*cm + space

        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(width/2, y, f"Part: {part_name}")
        y -= 1.2 * cm
        c.drawCentredString(width/2, y, f"Rack: {rack}")

        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString(width / 2, 1 * cm, "FUJITEC SA - JEDDAH WAREHOUSE")

        c.showPage()

        os.remove(barcode_filename)
        os.remove(qr_path)

    c.save()
    return pdf_file_name
