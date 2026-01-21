
# kehadiran.py
# Versi Stabil + Export PDF Mingguan
# Rekod Kehadiran Murid SK Labu Besar Minggu Ini

import os
import json
import datetime
import pytz
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

# ======================
# CONFIG
# ======================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")

# ======================
# GOOGLE SHEET AUTH
# ======================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds_json = json.loads(os.environ.get("GOOGLE_CREDS_JSON"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
client = gspread.authorize(creds)

sheet_murid = client.open_by_key(SHEET_ID).worksheet("Senarai Murid")
sheet_kehadiran = client.open_by_key(SHEET_ID).worksheet("Kehadiran")

# ======================
# GLOBAL STATE
# ======================
user_state = {}

# ======================
# UTILS
# ======================
def get_today_malaysia():
    tz = pytz.timezone("Asia/Kuala_Lumpur")
    return datetime.datetime.now(tz).date()


def get_week_range(today):
    # Ahad hingga Sabtu
    start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
    end = start + datetime.timedelta(days=6)
    return start, end


def format_attendance(kelas, tarikh, hari, total, absent):
    hadir = total - len(absent)
    msg = (
        f"🏫 {kelas}\n"
        f"📅 {hari}\n"
        f"🗓 {tarikh}\n\n"
        f"📊 Kehadiran\n"
        f"{hadir}/{total}\n"
    )
    if absent:
        msg += f"\n❌ Tidak Hadir ({len(absent)} murid)\n"
        for i, n in enumerate(absent, 1):
            msg += f"{i}. {n}\n"
    else:
        msg += "\n🎉 Semua murid hadir.\n"
    return msg


# ======================
# PDF EXPORT
# ======================
def generate_weekly_pdf():
    today = get_today_malaysia()
    start, end = get_week_range(today)

    records = sheet_kehadiran.get_all_records()

    doc = SimpleDocTemplate("/tmp/rekod_kehadiran_mingguan.pdf", pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    title = "Rekod Kehadiran Murid SK Labu Besar Minggu Ini"
    story.append(Paragraph(title, styles["Heading1"]))
    story.append(Spacer(1, 12))

    for i in range(7):
        day = start + datetime.timedelta(days=i)
        tarikh = day.strftime("%d/%m/%Y")
        hari = day.strftime("%A")

        daily_records = [r for r in records if r["Tarikh"] == tarikh]

        if not daily_records:
            continue

        story.append(Paragraph(f"📅 {hari}", styles["Heading2"]))
        story.append(Paragraph(f"🗓 {tarikh}", styles["Normal"]))
        story.append(Spacer(1, 8))

        for r in daily_records:
            kelas = r["Kelas"]
            hadir = r["Hadir"]
            jumlah = r["Jumlah"]
            tidak = r["Tidak Hadir"]

            story.append(Paragraph(f"🏫 {kelas}", styles["Heading3"]))
            story.append(Paragraph(f"📊 Kehadiran {hadir}/{jumlah}", styles["Normal"]))

            if tidak:
                names = tidak.split(",")
                story.append(Paragraph(f"❌ Tidak Hadir ({len(names)} murid)", styles["Normal"]))
                for idx, n in enumerate(names, 1):
                    story.append(Paragraph(f"{idx}. {n}", styles["Normal"]))
            else:
                story.append(Paragraph("🎉 Semua murid hadir", styles["Normal"]))

            story.append(Spacer(1, 12))

        story.append(Spacer(1, 24))

    doc.build(story)
    return "/tmp/rekod_kehadiran_mingguan.pdf"


# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inline_keyboard = [
        [InlineKeyboardButton("📋 Rekod Kehadiran", callback_data="rekod")],
        [InlineKeyboardButton("🔍 Semak Kehadiran", callback_data="semak")],
        [InlineKeyboardButton("🍱 Semak RMT Hari Ini", callback_data="semak_rmt_today")]
    ]

    reply_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🏠 Menu Utama")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    text = "Tracker Kehadiran Murid SK Labu Besar\n\nPilih menu:"

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
        await update.message.reply_text("🏠 Tekan butang di bawah untuk kembali ke Menu Utama", reply_markup=reply_keyboard)


# ======================
# BUTTON HANDLER
# ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # EXPORT PDF
    if data == "export_pdf_week":
        file_path = generate_weekly_pdf()
        await context.bot.send_document(chat_id=query.message.chat_id, document=open(file_path, "rb"))
        return

    # SEMAK
    if data == "semak":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard = [[InlineKeyboardButton(k, callback_data=f"semak_kelas|{k}")] for k in kelas_list]
        keyboard.append([InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_week")])

        await query.edit_message_text("Pilih kelas untuk semak:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("semak_kelas|"):
        kelas = data.split("|")[1]
        user_state[query.from_user.id] = {"semak_kelas": kelas}

        keyboard = [
            [InlineKeyboardButton("📅 Hari Ini", callback_data="semak_tarikh|today")],
            [InlineKeyboardButton("📆 Semalam", callback_data="semak_tarikh|yesterday")],
            [InlineKeyboardButton("🗓 Pilih Tarikh", callback_data="semak_tarikh|calendar")],
            [InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_week")]
        ]

        await query.edit_message_text("Pilih tarikh:", reply_markup=InlineKeyboardMarkup(keyboard))
        return


# ======================
# MAIN
# ======================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Bot Kehadiran sedang berjalan...")
    app.run_polling()


if __name__ == "__main__":
    main()
