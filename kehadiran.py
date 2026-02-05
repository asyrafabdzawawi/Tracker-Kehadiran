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
    "📘✨ Ilmu tidak menjadikan kita lebih tinggi, tetapi menjadikan kita lebih rendah hati.",
    "📖🎓 Ilmu tanpa adab hanya melahirkan kepandaian.",
    "🤲📚 Didiklah dengan kasih.",
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
        f"🏫 {kelas}\n"
        f"📅 {hari}\n"
        f"🗓 {tarikh}\n\n"
        f"📊 Kehadiran\n"
        f"{hadir}/{total}\n"
    )
    if absent:
        msg += f"\n❌ Tidak Hadir ({len(absent)})\n"
        for i, n in enumerate(absent, 1):
            msg += f"{i}. {n}\n"
    else:
        msg += "\n🎉 Semua murid hadir\n"
    return msg


def find_existing_row(kelas, tarikh):
    records = sheet_kehadiran.get_all_records()
    for idx, r in enumerate(records, start=2):
        if r["Kelas"] == kelas and r["Tarikh"] == tarikh:
            return idx
    return None


# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    inline_keyboard = [
        [InlineKeyboardButton("📋 Rekod Kehadiran", callback_data="rekod")],
        [InlineKeyboardButton("🔍 Semak Kehadiran", callback_data="semak")]
    ]

    reply_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🏠 Menu Utama")]],
        resize_keyboard=True
    )

    await update.message.reply_photo(
        photo="https://raw.githubusercontent.com/asyrafabdzawawi/Tracker-Kehadiran/main/logo_tracker.jpg"
    )

    await update.message.reply_text(
        "🏫 Tracker Kehadiran Murid\n\nPilih menu:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

    await update.message.reply_text(
        "Tekan untuk kembali ke Menu Utama",
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

        await query.edit_message_text(
            "Pilih kelas:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ---------- PILIH KELAS ----------
    if data.startswith("kelas|"):
        kelas = data.split("|")[1]
        today = get_today_malaysia()

        user_state[user_id] = {
            "kelas": kelas,
            "tarikh": today.strftime("%d/%m/%Y"),
            "hari": today.strftime("%A"),
            "students": get_students_by_class(kelas),
            "absent": []
        }

        await show_student_buttons(query, user_id)
        return

    # ---------- TOGGLE MURID ----------
    if data.startswith("murid|"):
        nama = data.split("|", 1)[1]
        state = user_state.get(user_id)
        if not state:
            return

        if nama in state["absent"]:
            state["absent"].remove(nama)
        else:
            state["absent"].append(nama)

        await show_student_buttons(query, user_id)
        return

    # ---------- RESET ----------
    if data == "reset":
        state = user_state.get(user_id)
        if state:
            state["absent"] = []
            await show_student_buttons(query, user_id)
        return

    # ---------- SEMUA HADIR ----------
    if data == "semua_hadir":
        state = user_state.get(user_id)
        if state:
            state["absent"] = []
            await show_student_buttons(query, user_id)
        return

    # ---------- SIMPAN ----------
    if data == "simpan":
        state = user_state.get(user_id)
        if not state:
            return

        row = find_existing_row(state["kelas"], state["tarikh"])
        data_row = [
            state["kelas"],
            state["tarikh"],
            state["hari"],
            len(state["students"]),
            ", ".join(state["absent"]),
            ""
        ]

        if row:
            sheet_kehadiran.update(f"A{row}:F{row}", [data_row])
        else:
            sheet_kehadiran.append_row(data_row)

        await query.edit_message_text(
            f"✅ Kehadiran berjaya disimpan\n\n🏫 {state['kelas']}\n📅 {state['tarikh']}"
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
# MENU BUTTON
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
