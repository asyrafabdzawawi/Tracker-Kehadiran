# ======================
# BOT KEHADIRAN FINAL VERSION (STABIL & PRODUCTION READY)
# ======================

# ======================
# IMPORT
# ======================
import os, json, datetime, pytz, random
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# ======================
# CONFIG
# ======================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
GROUP_ID = int(os.environ.get("GROUP_ID"))

LOGO_URL = "https://raw.githubusercontent.com/asyrafabdzawawi/Tracker-Kehadiran/main/logo_tracker.jpg"


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
# SWEET QUOTES
# ======================
SWEET_QUOTES = [
    "📘✨ Ilmu tidak menjadikan kita lebih tinggi, tetapi menjadikan kita lebih rendah hati…",
    "📖🎓 Ilmu tanpa adab hanya melahirkan kepandaian…",
    "🤲📚 Didiklah dengan kasih, kerana ilmu yang lahir dari hati akan kekal lebih lama…",
]

def get_random_quote():
    return random.choice(SWEET_QUOTES)


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
            if r.get("Catatan"):
                name += f" ({r['Catatan']})"
            students.append(name)
    return students


def format_attendance(kelas, tarikh, hari, total, absent):
    hadir = total - len(absent)
    msg = (
        f"🏫 *{kelas}*\n"
        f"📅 {hari}\n"
        f"🗓 {tarikh}\n\n"
        f"📊 *Kehadiran*\n"
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
# FIX: HELPER KHAS UNTUK MESEJ BERGAMBAR
# ======================
async def edit_caption(query, text, keyboard=None):
    await query.edit_message_caption(
        caption=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )


# ======================
# START / MENU UTAMA
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [InlineKeyboardButton("📋 Rekod Kehadiran", callback_data="rekod")],
        [InlineKeyboardButton("🔍 Semak Kehadiran", callback_data="semak")],
        [InlineKeyboardButton("🍱 Semak RMT Hari Ini", callback_data="semak_rmt_today")]
    ]

    caption = (
        "🏫 *Tracker Kehadiran Murid*\n"
        "*SK Labu Besar*\n\n"
        f"💬 {get_random_quote()}\n\n"
        "⬇️ *Pilih menu*"
    )

    await update.message.reply_photo(
        photo=LOGO_URL,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ======================
# BUTTON HANDLER
# ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # ---------- MENU ----------
    if data == "menu":
        await start(query.message, context)
        return

    # ---------- SEMAK RMT ----------
    if data == "semak_rmt_today":
        today = get_today_malaysia()
        tarikh = today.strftime("%d/%m/%Y")

        murid_records = sheet_murid.get_all_records()
        all_rmt = set()
        tidak_hadir = {}

        for r in murid_records:
            if "RMT" in (r.get("Catatan", "") + r["Nama Murid"]).upper():
                all_rmt.add(r["Nama Murid"].replace("(RMT)", "").strip())

        hadir_records = sheet_kehadiran.get_all_records()
        for r in hadir_records:
            if r["Tarikh"] == tarikh:
                for n in r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []:
                    n = n.replace("(RMT)", "").strip()
                    if n in all_rmt:
                        tidak_hadir.setdefault(r["Kelas"], []).append(n)

        total = len(all_rmt)
        total_absent = sum(len(v) for v in tidak_hadir.values())
        hadir = total - total_absent

        msg = (
            "🍱 *Laporan Kehadiran RMT Hari Ini*\n\n"
            f"📅 {tarikh}\n"
            f"📊 Hadir: {hadir}/{total}\n"
        )

        keyboard = [[InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu")]]

        await edit_caption(query, msg, keyboard)
        return

    # ---------- REKOD ----------
    if data == "rekod":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard, row = [], []
        for k in kelas_list:
            row.append(InlineKeyboardButton(k, callback_data=f"kelas|{k}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu")])
        await edit_caption(query, "Pilih kelas:", keyboard)
        return

    # ---------- PILIH KELAS ----------
    if data.startswith("kelas|"):
        kelas = data.split("|")[1]
        students = get_students_by_class(kelas)
        today = get_today_malaysia()

        user_state[user_id] = {
            "kelas": kelas,
            "tarikh": today.strftime("%d/%m/%Y"),
            "hari": today.strftime("%A"),
            "students": students,
            "absent": []
        }

        await show_student_buttons(query, user_id)
        return

    # ---------- SEMAK ----------
    if data == "semak":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard, row = [], []
        for k in kelas_list:
            row.append(InlineKeyboardButton(k, callback_data=f"semak_kelas|{k}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu")])
        await edit_caption(query, "Pilih kelas untuk semak:", keyboard)
        return


# ======================
# SHOW STUDENT BUTTONS
# ======================
async def show_student_buttons(query, user_id):

    state = user_state[user_id]

    msg = format_attendance(
        state["kelas"],
        state["tarikh"],
        state["hari"],
        len(state["students"]),
        state["absent"]
    )

    keyboard = []
    for n in state["students"]:
        label = f"🔴 {n}" if n in state["absent"] else f"🟢 {n}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"murid|{n}")])

    keyboard.append([
        InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu")
    ])

    await edit_caption(query, msg, keyboard)


# ======================
# MAIN
# ======================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Bot Kehadiran sedang berjalan...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
