import os
import json
import datetime
import pytz
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
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

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ======================
# [BARU] SENARAI KELAS HARI INI
# ======================
KELAS_HARI_INI = [
    "1 Amber", "1 Amethyst", "1 Aquamarine",
    "2 Amber", "2 Amethyst", "2 Aquamarine",
    "3 Amber", "3 Amethyst", "3 Aquamarine",
    "4 Amber", "4 Amethyst", "4 Aquamarine",
    "5 Amber", "5 Amethyst", "5 Aquamarine",
    "6 Amber", "6 Amethyst", "6 Aquamarine"
]

# ======================
# CONFIG (GUNA ENV)
# ======================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")

# ======================
# GOOGLE SHEET AUTH (GUNA ENV JSON)
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

def get_students_by_class(kelas):
    records = sheet_murid.get_all_records()
    students = []
    for r in records:
        if r["Kelas"] == kelas:
            name = r["Nama Murid"]
            if r["Catatan"]:
                name += f" ({r['Catatan']})"
            students.append(name)
    return students

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

def already_recorded(kelas, tarikh):
    records = sheet_kehadiran.get_all_records()
    for r in records:
        if r["Kelas"] == kelas and r["Tarikh"] == tarikh:
            return True
    return False

# ======================
# [BARU] SEMAK KELAS BELUM ISI HARI INI
# ======================
def semak_kelas_belum_isi_hari_ini():
    today = get_today_malaysia()
    tarikh = today.strftime("%d/%m/%Y")

    records = sheet_kehadiran.get_all_records()

    kelas_dah_isi = []
    for r in records:
        if r["Tarikh"] == tarikh:
            kelas_dah_isi.append(r["Kelas"])

    kelas_belum_isi = []
    for k in KELAS_HARI_INI:
        if k not in kelas_dah_isi:
            kelas_belum_isi.append(k)

    return kelas_dah_isi, kelas_belum_isi

# ======================
# START / MENU UTAMA
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    inline_keyboard = [
        [InlineKeyboardButton("📋 Rekod Kehadiran", callback_data="rekod")],
        [InlineKeyboardButton("🔍 Semak Kehadiran", callback_data="semak")],
        [InlineKeyboardButton("🍱 Semak RMT Hari Ini", callback_data="semak_rmt_today")],
        # [BARU]
        [InlineKeyboardButton("📊 Kelas Belum Isi Hari Ini", callback_data="kelas_belum_isi_today")]
    ]

    reply_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🏠 Menu Utama")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    text = "Tracker Kehadiran Murid SK Labu Besar\n\nPilih menu:"

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        await update.message.reply_text(
            "🏠 Tekan butang di bawah untuk kembali ke Menu Utama",
            reply_markup=reply_keyboard
        )
    else:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        await update.callback_query.message.reply_text(
            "🏠 Tekan butang di bawah untuk kembali ke Menu Utama",
            reply_markup=reply_keyboard
        )

# ======================
# BUTTON HANDLER
# ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # ---------- [BARU] SEMAK KELAS BELUM ISI ----------
    if data == "kelas_belum_isi_today":

        kelas_dah, kelas_belum = semak_kelas_belum_isi_hari_ini()
        today = get_today_malaysia().strftime("%d/%m/%Y")

        msg = f"📊 Status Kehadiran Hari Ini\n📅 {today}\n\n"

        msg += "✅ Sudah isi:\n"
        if kelas_dah:
            for k in kelas_dah:
                msg += f"- {k}\n"
        else:
            msg += "- Belum ada\n"

        msg += "\n❌ Belum isi:\n"
        if kelas_belum:
            for k in kelas_belum:
                msg += f"- {k}\n"
        else:
            msg += "- Semua kelas telah lengkap 🎉\n"

        await query.edit_message_text(msg)
        return

    # ======================
    # SEMUA KOD ASAL AWAK KEKAL DI BAWAH INI
    # ======================
