# ======================
# BOT KEHADIRAN FINAL VERSION (STABIL & PRODUCTION READY)
# ======================

# ======================
# IMPORT
# ======================
import os, json, datetime, pytz, random
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# ======================
# CONFIG
# ======================
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEET_ID = os.environ.get("SHEET_ID")
GROUP_ID = int(os.environ.get("GROUP_ID"))


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
    "📘✨ “Ilmu tidak menjadikan kita lebih tinggi, tetapi menjadikan kita lebih rendah hati…fikir-fikirkanlah.” 🤲",
    "📖🎓 “Ilmu tanpa adab hanya melahirkan kepandaian, tetapi ilmu bersama adab melahirkan kebijaksanaan…fikir-fikirkanlah.” 🌺",
    "🤲📚 “Didiklah dengan kasih, kerana ilmu yang lahir dari hati akan kekal lebih lama di jiwa…fikir-fikirkanlah.” 💖",
    "Semakin tinggi ilmu, sepatutnya semakin rendah hati…fikir-fikirkanlah.” 🤲📘",
    "Ilmu tanpa tawaduk hanya melahirkan ego, bukan kebijaksanaan…fikir-fikirkanlah.” 📖🧭",
]

def get_random_quote():
    return random.choice(SWEET_QUOTES)


# ======================
# SENARAI KELAS RASMI
# ======================
ALL_CLASSES = [
    "1 Amber", "1 Amethyst", "1 Aquamarine",
    "2 Amber", "2 Amethyst", "2 Aquamarine",
    "3 Amber", "3 Amethyst", "3 Aquamarine",
    "4 Amber", "4 Amethyst", "4 Aquamarine",
    "5 Amber", "5 Amethyst", "5 Aquamarine",
    "6 Amber", "6 Amethyst", "6 Aquamarine",
    "PRA CITRINE", "PRA CRYSTAL"
]


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


def find_existing_row(kelas, tarikh):
    records = sheet_kehadiran.get_all_records()
    for idx, r in enumerate(records, start=2):
        if r["Kelas"] == kelas and r["Tarikh"] == tarikh:
            return idx
    return None


# ======================
# START / MENU UTAMA
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    inline_keyboard = [
        [InlineKeyboardButton("📋 Rekod Kehadiran", callback_data="rekod")],
        [InlineKeyboardButton("🔍 Semak Kehadiran", callback_data="semak")],
        [InlineKeyboardButton("🍱 Semak RMT Hari Ini", callback_data="semak_rmt_today")]
    ]

    reply_keyboard = ReplyKeyboardMarkup([[KeyboardButton("🏠 Menu Utama")]], resize_keyboard=True)

    quote = get_random_quote()

    text = (
        "🏫 Tracker Kehadiran Murid SK Labu Besar\n\n"
        f"💬 {quote}\n\n"
        "Pilih menu:"
    )

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
    await update.message.reply_text(
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

    # ---------- SEMAK RMT ----------
    if data == "semak_rmt_today":
        today = get_today_malaysia()
        tarikh = today.strftime("%d/%m/%Y")

        murid_records = sheet_murid.get_all_records()
        all_rmt = set()
        rmt_by_class = {}

        for r in murid_records:
            nama = r["Nama Murid"]
            kelas = r["Kelas"]
            catatan = str(r.get("Catatan", "")).upper()

            if "(RMT)" in nama.upper() or "RMT" in catatan:
                nama = nama.replace("(RMT)", "").strip()
                all_rmt.add(nama)
                rmt_by_class.setdefault(kelas, []).append(nama)

        hadir_records = sheet_kehadiran.get_all_records()
        tidak_hadir = {}

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
            "🍱 Laporan Kehadiran RMT Hari Ini\n\n"
            f"📅 {tarikh}\n"
            f"📊 Hadir: {hadir} / {total}\n"
        )

        if tidak_hadir:
            msg += f"\n❌ Tidak Hadir ({total_absent} murid)\n"
            for k in sorted(tidak_hadir):
                msg += f"\n🏫 {k}\n"
                for i, n in enumerate(tidak_hadir[k], 1):
                    msg += f"{i}. {n}\n"
        else:
            msg += "\n🎉 Semua murid RMT hadir hari ini.\n"

        await query.edit_message_text(msg)
        return

    # ---------- REKOD (3 COLUMN) ----------
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

        await query.edit_message_text(
            "Pilih kelas:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---------- PILIH KELAS REKOD ----------
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

    # ---------- SEMAK (3 COLUMN) ----------
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

        keyboard.append([InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_weekly")])

        await query.edit_message_text(
            "Pilih kelas untuk semak:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---------- PILIH KELAS SEMAK ----------
    if data.startswith("semak_kelas|"):
        kelas = data.split("|")[1]
        user_state[user_id] = {"semak_kelas": kelas}

        keyboard = [
            [InlineKeyboardButton("📅 Hari Ini", callback_data="semak_tarikh|today")],
            [InlineKeyboardButton("📆 Semalam", callback_data="semak_tarikh|yesterday")],
            [InlineKeyboardButton("🗓 Pilih Tarikh", callback_data="semak_tarikh|calendar")],
            [InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_weekly")]
        ]

        await query.message.reply_text(
            f"🏫 {kelas}\n\nPilih tarikh:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
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
        InlineKeyboardButton("💾 Simpan", callback_data="simpan"),
        InlineKeyboardButton("♻️ Reset", callback_data="reset"),
        InlineKeyboardButton("✅ Semua Hadir", callback_data="semua_hadir")
    ])

    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ======================
# MENU BUTTON HANDLER
# ======================
async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "🏠 Menu Utama":
        user_state.pop(update.message.from_user.id, None)
        await start(update, context)


# ======================
# MAIN
# ======================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_button))

    print("🤖 Bot Kehadiran sedang berjalan...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
