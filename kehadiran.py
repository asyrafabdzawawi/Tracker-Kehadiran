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
# START / MENU UTAMA
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inline_keyboard = [
        [InlineKeyboardButton("📋 Rekod Kehadiran", callback_data="rekod")],
        [InlineKeyboardButton("🔍 Semak Kehadiran", callback_data="semak")]
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
            "#labubest",
            reply_markup=reply_keyboard
        )
    else:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        await update.callback_query.message.reply_text(
            "🏠 Menu tersedia",
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
            await query.edit_message_text(
                f"❌ Rekod kehadiran {kelas} untuk {tarikh} telah dicatat oleh guru lain."
            )
            user_state.pop(user_id, None)
            return

        total = len(students)

        sheet_kehadiran.append_row([
            tarikh, hari, kelas, total, total, ""
        ])

        msg = format_attendance(kelas, tarikh, hari, total, [])

        await query.edit_message_text(
            "✅ Kehadiran berjaya disimpan!\n\n" + msg
        )

        user_state.pop(user_id, None)
        return

    # ---------- SIMPAN ----------
    if data == "simpan":
        state = user_state.get(user_id)
        if not state:
            await query.edit_message_text("❌ Tiada data untuk disimpan.")
            return

        if len(state["absent"]) == 0:
            await query.edit_message_text("⚠️ Tiada murid dipilih sebagai tidak hadir.")
            return

        kelas = state["kelas"]
        tarikh = state["tarikh"]
        hari = state["hari"]

        if already_recorded(kelas, tarikh):
            await query.edit_message_text(
                f"❌ Rekod kehadiran {kelas} untuk {tarikh} telah dicatat oleh guru lain."
            )
            user_state.pop(user_id, None)
            return

        total = len(state["students"])
        absent = state["absent"]
        hadir = total - len(absent)

        sheet_kehadiran.append_row([
            tarikh, hari, kelas, hadir, total, ", ".join(absent)
        ])

        msg = format_attendance(kelas, tarikh, hari, total, absent)

        await query.edit_message_text(
            "✅ Kehadiran berjaya disimpan!\n\n" + msg
        )

        user_state.pop(user_id, None)
        return

    # ---------- SEMAK ----------
    if data == "semak":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard = [[InlineKeyboardButton(k, callback_data=f"semak_kelas|{k}")] for k in kelas_list]
        await query.edit_message_text("Pilih kelas untuk semak:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("semak_kelas|"):
        kelas = data.split("|")[1]
        user_state[user_id] = {"semak_kelas": kelas}

        keyboard = [
            [InlineKeyboardButton("📅 Hari Ini", callback_data="semak_tarikh|today")],
            [InlineKeyboardButton("📆 Semalam", callback_data="semak_tarikh|yesterday")],
            [InlineKeyboardButton("🗓 Pilih Tarikh", callback_data="semak_tarikh|calendar")]
        ]
        await query.edit_message_text("Pilih tarikh:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("semak_tarikh|"):
        choice = data.split("|")[1]
        state = user_state.get(user_id)
        kelas = state["semak_kelas"]

        today = get_today_malaysia()

        if choice == "calendar":
            state["calendar_year"] = today.year
            state["calendar_month"] = today.month
            await show_calendar(query, user_id)
            return

        target_date = today.strftime("%d/%m/%Y") if choice == "today" else \
            (today - datetime.timedelta(days=1)).strftime("%d/%m/%Y")

        await show_record_for_date(query, kelas, target_date)
        return

    # ---------- KALENDAR ----------
    if data.startswith("cal_nav|"):
        _, year, month = data.split("|")
        state = user_state.get(user_id)
        state["calendar_year"] = int(year)
        state["calendar_month"] = int(month)
        await show_calendar(query, user_id)
        return

    if data.startswith("cal_day|"):
        _, year, month, day = data.split("|")
        target_date = f"{int(day):02d}/{int(month):02d}/{year}"
        state = user_state.get(user_id)
        kelas = state["semak_kelas"]
        await show_record_for_date(query, kelas, target_date)
        return


# ======================
# MENU BUTTON HANDLER
# ======================
async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "🏠 Menu Utama":
        user_state.pop(update.message.from_user.id, None)
        await start(update, context)


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

    total = len(students)
    hadir = total - len(absent)

    msg = format_attendance(kelas, tarikh, hari, total, absent)

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
# SHOW CALENDAR
# ======================
async def show_calendar(query, user_id):
    state = user_state[user_id]
    year = state["calendar_year"]
    month = state["calendar_month"]

    first_day = datetime.date(year, month, 1)
    start_weekday = first_day.weekday()
    days_in_month = (datetime.date(year + (month // 12), ((month % 12) + 1), 1) - datetime.timedelta(days=1)).day

    keyboard = []

    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"cal_nav|{year}|{month-1 if month>1 else 12}"),
        InlineKeyboardButton(f"{first_day.strftime('%B')} {year}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"cal_nav|{year}|{month+1 if month<12 else 1}")
    ])

    weekdays = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    keyboard.append([InlineKeyboardButton(d, callback_data="noop") for d in weekdays])

    row = []
    for _ in range(start_weekday):
        row.append(InlineKeyboardButton(" ", callback_data="noop"))

    for day in range(1, days_in_month + 1):
        row.append(InlineKeyboardButton(str(day), callback_data=f"cal_day|{year}|{month}|{day}"))
        if len(row) == 7:
            keyboard.append(row)
            row = []

    if row:
        while len(row) < 7:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)

    await query.edit_message_text("🗓 Pilih tarikh:", reply_markup=InlineKeyboardMarkup(keyboard))


# ======================
# SHOW RECORD FOR DATE
# ======================
async def show_record_for_date(query, kelas, target_date):
    records = sheet_kehadiran.get_all_records()
    for r in records:
        if r["Kelas"] == kelas and r["Tarikh"] == target_date:
            msg = format_attendance(
                kelas,
                r["Tarikh"],
                r["Hari"],
                r["Jumlah"],
                r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
            )
            await query.edit_message_text(msg)
            return

    keyboard = [
        [InlineKeyboardButton("📅 Hari Ini", callback_data="semak_tarikh|today")],
        [InlineKeyboardButton("📆 Semalam", callback_data="semak_tarikh|yesterday")],
        [InlineKeyboardButton("🗓 Pilih Tarikh", callback_data="semak_tarikh|calendar")]
    ]

    await query.edit_message_text(
        "❌ Tiada rekod untuk tarikh ini.\n\nPilih tarikh lain:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


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
