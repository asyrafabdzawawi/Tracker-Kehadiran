# ======================
# BOT KEHADIRAN MURID SK LABU BESAR
# VERSI STABIL + OVERWRITE DENGAN CONFIRMATION
# Python Telegram Bot v20.x
# ======================

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


def delete_existing_record(kelas, tarikh):
    records = sheet_kehadiran.get_all_records()
    for idx, r in enumerate(records, start=2):  # row 1 header
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

    # ---------- SEMAK RMT HARI INI ----------
    if data == "semak_rmt_today":
        today = get_today_malaysia()
        tarikh = today.strftime("%d/%m/%Y")

        records_kehadiran = sheet_kehadiran.get_all_records()
        records_murid = sheet_murid.get_all_records()

        rmt_students = {}
        for r in records_murid:
            if "RMT" in str(r.get("Catatan", "")):
                rmt_students[r["Nama Murid"]] = r["Kelas"]

        rmt_absent = {}

        for r in records_kehadiran:
            if r["Tarikh"] == tarikh and r["Tidak Hadir"]:
                kelas = r["Kelas"]
                absent_list = [x.strip() for x in r["Tidak Hadir"].split(",")]

                for name in absent_list:
                    clean_name = name.replace("(RMT)", "").strip()
                    if clean_name in rmt_students:
                        if kelas not in rmt_absent:
                            rmt_absent[kelas] = []
                        rmt_absent[kelas].append(name)

        if not rmt_absent:
            await query.edit_message_text(f"🎉 Semua murid RMT hadir hari ini.\n\n📅 {tarikh}")
            return

        msg = f"🍱 RMT Tidak Hadir Hari Ini\n📅 {tarikh}\n\n"
        total = 0

        for kelas, names in rmt_absent.items():
            msg += f"🏫 {kelas}\n"
            for i, n in enumerate(names, 1):
                msg += f"{i}. {n}\n"
                total += 1
            msg += "\n"

        msg += f"Jumlah RMT tidak hadir: {total} murid"

        await query.edit_message_text(msg)
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

    # ---------- PILIH MURID ----------
    if data.startswith("murid|"):
        name = data.split("|")[1]
        state = user_state.get(user_id)

        if state:
            if name in state["absent"]:
                state["absent"].remove(name)
            else:
                state["absent"].append(name)

        await show_student_buttons(query, user_id)
        return

    if data == "reset":
        state = user_state.get(user_id)
        if state:
            state["absent"] = []
        await show_student_buttons(query, user_id)
        return

    # ---------- SEMUA HADIR ----------
    if data == "semua_hadir":
        state = user_state.get(user_id)
        if not state:
            await query.edit_message_text("❌ Tiada data untuk disimpan.")
            return

        kelas = state["kelas"]
        tarikh = state["tarikh"]
        hari = state["hari"]
        students = state["students"]

        if already_recorded(kelas, tarikh):
            state["pending_overwrite"] = "semua_hadir"
            keyboard = [
                [InlineKeyboardButton("🔁 Ya, Kemaskini", callback_data="confirm_overwrite")],
                [InlineKeyboardButton("❌ Batal", callback_data="cancel_overwrite")]
            ]

            await query.edit_message_text(
                f"⚠️ Rekod kehadiran {kelas} untuk {tarikh} telah wujud.\n\nAdakah cikgu mahu kemaskini rekod ini?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        total = len(students)

        sheet_kehadiran.append_row([tarikh, hari, kelas, total, total, ""])
        msg = format_attendance(kelas, tarikh, hari, total, [])

        await query.edit_message_text("✅ Kehadiran berjaya disimpan!\n\n" + msg)
        user_state.pop(user_id, None)
        return

    # ---------- SIMPAN ----------
    if data == "simpan":
        state = user_state.get(user_id)
        if not state:
            await query.edit_message_text("❌ Tiada data untuk disimpan.")
            return

        kelas = state["kelas"]
        tarikh = state["tarikh"]
        hari = state["hari"]

        if already_recorded(kelas, tarikh):
            state["pending_overwrite"] = "simpan"
            keyboard = [
                [InlineKeyboardButton("🔁 Ya, Kemaskini", callback_data="confirm_overwrite")],
                [InlineKeyboardButton("❌ Batal", callback_data="cancel_overwrite")]
            ]

            await query.edit_message_text(
                f"⚠️ Rekod kehadiran {kelas} untuk {tarikh} telah wujud.\n\nAdakah cikgu mahu kemaskini rekod ini?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        total = len(state["students"])
        absent = state["absent"]
        hadir = total - len(absent)

        sheet_kehadiran.append_row([tarikh, hari, kelas, hadir, total, ", ".join(absent)])
        msg = format_attendance(kelas, tarikh, hari, total, absent)

        await query.edit_message_text("✅ Kehadiran berjaya disimpan!\n\n" + msg)
        user_state.pop(user_id, None)
        return

    # ---------- CONFIRM OVERWRITE ----------
    if data == "confirm_overwrite":
        state = user_state.get(user_id)
        kelas = state["kelas"]
        tarikh = state["tarikh"]
        hari = state["hari"]
        students = state["students"]
        absent = state["absent"]
        mode = state.get("pending_overwrite")

        delete_existing_record(kelas, tarikh)

        total = len(students)

        if mode == "semua_hadir":
            sheet_kehadiran.append_row([tarikh, hari, kelas, total, total, ""])
            msg = format_attendance(kelas, tarikh, hari, total, [])
        else:
            hadir = total - len(absent)
            sheet_kehadiran.append_row([tarikh, hari, kelas, hadir, total, ", ".join(absent)])
            msg = format_attendance(kelas, tarikh, hari, total, absent)

        await query.edit_message_text("✅ Rekod kehadiran berjaya dikemaskini!\n\n" + msg)
        user_state.pop(user_id, None)
        return

    # ---------- CANCEL OVERWRITE ----------
    if data == "cancel_overwrite":
        user_state.pop(user_id, None)
        await query.edit_message_text("❌ Kemaskini dibatalkan.")
        return

    # ---------- SEMAK ----------
    if data == "semak":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard = [[InlineKeyboardButton(k, callback_data=f"semak_kelas|{k}")] for k in kelas_list]
        await query.edit_message_text("Pilih kelas untuk semak:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

# ======================
# SHOW STUDENT BUTTONS
# ======================
async def show_student_buttons(query, user_id):
    state = user_state[user_id]
    kelas = state["kelas"]
    tarikh = state["tarikh"]
    hari = state["hari"]
    students = state["students"]
    absent = state["absent"]

    msg = format_attendance(kelas, tarikh, hari, len(students), absent)

    keyboard = []
    for n in students:
        label = f"🔴 {n}" if n in absent else f"🟢 {n}"
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
