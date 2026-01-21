import os
import json
import datetime
import pytz
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ======================
# CONFIG (ENV RAILWAY)
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


# ======================
# START / MENU UTAMA
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    inline_keyboard = [
        [InlineKeyboardButton("📋 Rekod Kehadiran", callback_data="rekod")],
        [InlineKeyboardButton("🔍 Semak Kehadiran", callback_data="semak")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu")]
    ]

    text = "Tracker Kehadiran Murid SK Labu Besar\n\nPilih menu:"

    msg = await update.effective_chat.send_message(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

    # simpan message id untuk auto clear
    user_state[user_id] = user_state.get(user_id, {})
    user_state[user_id]["last_msgs"] = [msg.message_id]


# ======================
# BUTTON HANDLER
# ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # ---------- MENU UTAMA (AUTO CLEAR BIASA) ----------
    if data == "menu":
        state = user_state.get(user_id, {})

        # padam mesej bot sebelum ni
        for mid in state.get("last_msgs", []):
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat_id,
                    message_id=mid
                )
            except:
                pass

        # padam message semasa
        try:
            await query.message.delete()
        except:
            pass

        user_state[user_id] = {}
        await start(update, context)
        return

    # ---------- REKOD ----------
    if data == "rekod":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard = [[InlineKeyboardButton(k, callback_data=f"kelas|{k}")] for k in kelas_list]
        msg = await query.edit_message_text(
            "Pilih kelas:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        user_state[user_id]["last_msgs"].append(msg.message_id)
        return

    if data.startswith("kelas|"):
        kelas = data.split("|")[1]
        students = get_students_by_class(kelas)

        today = get_today_malaysia()
        tarikh = today.strftime("%d/%m/%Y")
        hari = today.strftime("%A")

        user_state[user_id].update({
            "kelas": kelas,
            "tarikh": tarikh,
            "hari": hari,
            "students": students,
            "absent": []
        })

        await show_student_buttons(query, user_id)
        return

    # ---------- PILIH MURID ----------
    if data.startswith("murid|"):
        name = data.split("|")[1]
        state = user_state.get(user_id)

        if name in state["absent"]:
            state["absent"].remove(name)
        else:
            state["absent"].append(name)

        await show_student_buttons(query, user_id)
        return

    if data == "reset":
        user_state[user_id]["absent"] = []
        await show_student_buttons(query, user_id)
        return

    # ---------- SIMPAN ----------
    if data == "simpan":
        state = user_state.get(user_id)
        kelas = state["kelas"]
        tarikh = state["tarikh"]
        hari = state["hari"]

        if already_recorded(kelas, tarikh):
            await query.edit_message_text("❌ Rekod sudah wujud.")
            user_state[user_id] = {}
            return

        total = len(state["students"])
        absent = state["absent"]
        hadir = total - len(absent)

        sheet_kehadiran.append_row([
            tarikh, hari, kelas, hadir, total, ", ".join(absent)
        ])

        msg = format_attendance(kelas, tarikh, hari, total, absent)
        await query.edit_message_text("✅ Disimpan!\n\n" + msg)
        user_state[user_id] = {}
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
        InlineKeyboardButton("🏠 Menu Utama", callback_data="menu")
    ])

    edited = await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    user_state[user_id]["last_msgs"].append(edited.message_id)


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
