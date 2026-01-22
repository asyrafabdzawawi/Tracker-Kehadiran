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

# ======================
# CONFIG (GUNA ENV)
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

def already_recorded(kelas, tarikh):
    records = sheet_kehadiran.get_all_records()
    for r in records:
        if r["Kelas"] == kelas and r["Tarikh"] == tarikh:
            return True
    return False

# 🆕 PADAM REKOD LAMA (UNTUK OVERWRITE)
def delete_existing_record(kelas, tarikh):
    records = sheet_kehadiran.get_all_records()
    for idx, r in enumerate(records, start=2):
        if r["Kelas"] == kelas and r["Tarikh"] == tarikh:
            sheet_kehadiran.delete_rows(idx)
            return True
    return False

# ======================
# START / MENU UTAMA
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

    # ---------- CONFIRM OVERWRITE ----------
    if data == "confirm_overwrite":
        state = user_state.get(user_id)

        if not state:
            await query.edit_message_text("❌ Tiada data untuk dikemaskini.")
            return

        kelas = state["kelas"]
        tarikh = state["tarikh"]
        hari = state["hari"]
        students = state["students"]
        absent = state["absent"]

        delete_existing_record(kelas, tarikh)

        total = len(students)
        hadir = total - len(absent)

        sheet_kehadiran.append_row([
            tarikh, hari, kelas, hadir, total, ", ".join(absent)
        ])

        msg = format_attendance(kelas, tarikh, hari, total, absent)

        await query.edit_message_text("✅ Rekod kehadiran berjaya dikemaskini!\n\n" + msg)

        user_state.pop(user_id, None)
        return

    # ---------- CANCEL OVERWRITE ----------
    if data == "cancel_overwrite":
        user_state.pop(user_id, None)
        await query.edit_message_text("❌ Kemaskini dibatalkan.")
        return

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

    # ---------- SEMUA HADIR ----------
    if data == "semua_hadir":
        state = user_state.get(user_id)

        kelas = state["kelas"]
        tarikh = state["tarikh"]

        if already_recorded(kelas, tarikh):
            state["overwrite_mode"] = "semua_hadir"

            keyboard = [
                [
                    InlineKeyboardButton("🔁 Ya, Kemaskini", callback_data="confirm_overwrite"),
                    InlineKeyboardButton("❌ Batal", callback_data="cancel_overwrite")
                ]
            ]

            await query.edit_message_text(
                f"⚠️ Rekod kehadiran {kelas} untuk {tarikh} sudah wujud.\n\n"
                "Adakah cikgu mahu kemaskini (overwrite) rekod ini?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        sheet_kehadiran.append_row([tarikh, state["hari"], kelas, len(state["students"]), len(state["students"]), ""])
        msg = format_attendance(kelas, tarikh, state["hari"], len(state["students"]), [])
        await query.edit_message_text("✅ Kehadiran berjaya disimpan!\n\n" + msg)
        user_state.pop(user_id, None)
        return

    # ---------- SIMPAN ----------
    if data == "simpan":
        state = user_state.get(user_id)

        kelas = state["kelas"]
        tarikh = state["tarikh"]

        if already_recorded(kelas, tarikh):
            state["overwrite_mode"] = "simpan"

            keyboard = [
                [
                    InlineKeyboardButton("🔁 Ya, Kemaskini", callback_data="confirm_overwrite"),
                    InlineKeyboardButton("❌ Batal", callback_data="cancel_overwrite")
                ]
            ]

            await query.edit_message_text(
                f"⚠️ Rekod kehadiran {kelas} untuk {tarikh} sudah wujud.\n\n"
                "Adakah cikgu mahu kemaskini (overwrite) rekod ini?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        total = len(state["students"])
        absent = state["absent"]
        hadir = total - len(absent)

        sheet_kehadiran.append_row([tarikh, state["hari"], kelas, hadir, total, ", ".join(absent)])
        msg = format_attendance(kelas, tarikh, state["hari"], total, absent)
        await query.edit_message_text("✅ Kehadiran berjaya disimpan!\n\n" + msg)
        user_state.pop(user_id, None)
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
