# ======================
# IMPORT
# ======================
import os, json, datetime, pytz
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
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
    for idx, r in enumerate(records, start=2):  # start=2 sebab row 1 header
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

    text = "Tracker Kehadiran Murid SK Labu Besar\n\nPilih menu:"

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
        await update.message.reply_text("🏠 Tekan butang di bawah untuk kembali ke Menu Utama", reply_markup=reply_keyboard)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
        await update.callback_query.message.reply_text("🏠 Tekan butang di bawah untuk kembali ke Menu Utama", reply_markup=reply_keyboard)


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
        keyboard = [[InlineKeyboardButton(k, callback_data=f"kelas|{k}")] for k in kelas_list]
        await query.edit_message_text("Pilih kelas:", reply_markup=InlineKeyboardMarkup(keyboard))
        return


    if data.startswith("kelas|"):
        kelas = data.split("|")[1]
        students = get_students_by_class(kelas)

        today = get_today_malaysia()
        tarikh = today.strftime("%d/%m/%Y")
        hari = today.strftime("%A")

        user_state[user_id] = {
            "kelas": kelas,
            "tarikh": tarikh,
            "hari": hari,
            "students": students,
            "absent": []
        }

        await show_student_buttons(query, user_id)
        return


    # ---------- PILIH MURID ----------
    if data.startswith("murid|"):
        name = data.split("|")[1]
        state = user_state[user_id]

        if name in state["absent"]:
            state["absent"].remove(name)
        else:
            state["absent"].append(name)

        await show_student_buttons(query, user_id)
        return


    # ---------- RESET ----------
    if data == "reset":
        user_state[user_id]["absent"] = []
        await show_student_buttons(query, user_id)
        return


    # ---------- SIMPAN / SEMUA HADIR ----------
    if data in ["simpan", "semua_hadir"]:

        state = user_state[user_id]
        kelas = state["kelas"]
        tarikh = state["tarikh"]
        hari = state["hari"]
        total = len(state["students"])

        absent = [] if data == "semua_hadir" else state["absent"]
        hadir = total - len(absent)

        row = find_existing_row(kelas, tarikh)

        # 🔴 JIKA SUDAH ADA REKOD → MINTA CONFIRM
        if row:
            user_state[user_id]["pending_overwrite"] = {
                "row": row,
                "kelas": kelas,
                "tarikh": tarikh,
                "hari": hari,
                "hadir": hadir,
                "total": total,
                "absent": absent
            }

            keyboard = [
                [
                    InlineKeyboardButton("✅ Ya, Overwrite", callback_data="confirm_overwrite"),
                    InlineKeyboardButton("❌ Batal", callback_data="cancel_overwrite")
                ]
            ]

            await query.edit_message_text(
                f"⚠️ Rekod kehadiran untuk\n\n🏫 {kelas}\n🗓 {tarikh}\n\nsudah wujud.\n\nAdakah anda mahu overwrite?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # 🟢 SIMPAN BIASA (TIADA REKOD LAMA)
        sheet_kehadiran.append_row([tarikh, hari, kelas, hadir, total, ", ".join(absent)])

        msg = format_attendance(kelas, tarikh, hari, total, absent)
        await query.edit_message_text("✅ Kehadiran berjaya disimpan!\n\n" + msg)

        user_state.pop(user_id, None)
        return


    # ---------- CONFIRM OVERWRITE ----------
    if data == "confirm_overwrite":

        info = user_state[user_id]["pending_overwrite"]

        # Padam row lama
        sheet_kehadiran.delete_rows(info["row"])

        # Simpan data baru
        sheet_kehadiran.append_row([
            info["tarikh"],
            info["hari"],
            info["kelas"],
            info["hadir"],
            info["total"],
            ", ".join(info["absent"])
        ])

        msg = format_attendance(info["kelas"], info["tarikh"], info["hari"], info["total"], info["absent"])
        await query.edit_message_text("🔄 Rekod berjaya dioverwrite!\n\n" + msg)

        user_state.pop(user_id, None)
        return


    # ---------- BATAL OVERWRITE ----------
    if data == "cancel_overwrite":
        await query.edit_message_text("❌ Overwrite dibatalkan. Rekod asal dikekalkan.")
        user_state.pop(user_id, None)
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
    app.run_polling()


if __name__ == "__main__":
    main()
