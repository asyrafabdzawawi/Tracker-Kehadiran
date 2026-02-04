# ======================
# BOT KEHADIRAN FINAL VERSION v2 (MENU FIXED)
# ======================

# ======================
# IMPORT
# ======================
import os, json, datetime, pytz, random
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# ======================
# CONFIG
# ======================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")

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
# QUOTES
# ======================
SWEET_QUOTES = [
    "📘✨ Ilmu tidak menjadikan kita lebih tinggi, tetapi lebih rendah hati.",
    "📖🎓 Ilmu bersama adab melahirkan kebijaksanaan.",
    "🤲📚 Didik dengan kasih, ilmu akan kekal di jiwa.",
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
    return [
        r["Nama Murid"] + (f" ({r['Catatan']})" if r.get("Catatan") else "")
        for r in records if r["Kelas"] == kelas
    ]


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
        msg += "\n❌ Tidak Hadir:\n"
        for i, n in enumerate(absent, 1):
            msg += f"{i}. {n}\n"
    else:
        msg += "\n🎉 Semua murid hadir."
    return msg


# ======================
# HELPER: EDIT CAPTION
# ======================
async def edit_caption(query, text, keyboard):
    await query.edit_message_caption(
        caption=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ======================
# MAIN MENU (FIXED)
# ======================
async def show_main_menu(query):
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

    await edit_caption(query, caption, keyboard)


# ======================
# START (/start sahaja)
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
        await show_main_menu(query)
        return

    # ---------- RMT ----------
    if data == "semak_rmt_today":
        today = get_today_malaysia()
        tarikh = today.strftime("%d/%m/%Y")

        murid = sheet_murid.get_all_records()
        hadir = sheet_kehadiran.get_all_records()

        rmt = {
            r["Nama Murid"].replace("(RMT)", "").strip()
            for r in murid if "RMT" in (r["Nama Murid"] + str(r.get("Catatan", ""))).upper()
        }

        tidak_hadir = set()
        for r in hadir:
            if r["Tarikh"] == tarikh and r["Tidak Hadir"]:
                for n in r["Tidak Hadir"].split(", "):
                    if n in rmt:
                        tidak_hadir.add(n)

        msg = (
            "🍱 *Laporan Kehadiran RMT Hari Ini*\n\n"
            f"📅 {tarikh}\n"
            f"📊 Hadir: {len(rmt)-len(tidak_hadir)}/{len(rmt)}"
        )

        await edit_caption(query, msg, [
            [InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu")]
        ])
        return

    # ---------- REKOD ----------
    if data == "rekod":
        records = sheet_murid.get_all_records()
        kelas_list = sorted({r["Kelas"] for r in records})

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


# ======================
# STUDENT BUTTONS
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

    keyboard = [
        [InlineKeyboardButton(
            ("🔴 " if n in state["absent"] else "🟢 ") + n,
            callback_data=f"murid|{n}"
        )] for n in state["students"]
    ]

    keyboard.append([InlineKeyboardButton("⬅️ Menu Utama", callback_data="menu")])

    await edit_caption(query, msg, keyboard)


# ======================
# MAIN
# ======================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Bot Kehadiran berjalan (FINAL v2)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
