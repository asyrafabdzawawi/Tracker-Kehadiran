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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

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


# ======================
# PDF FUNCTIONS
# ======================
def get_week_range_ahad(today):
    weekday = today.weekday()
    days_since_sunday = (weekday + 1) % 7
    sunday = today - datetime.timedelta(days=days_since_sunday)
    saturday = sunday + datetime.timedelta(days=6)
    return sunday, saturday


def generate_weekly_pdf():
    today = get_today_malaysia()
    sunday, saturday = get_week_range_ahad(today)

    records = sheet_kehadiran.get_all_records()
    data_by_date = {}

    for r in records:
        try:
            rec_date = datetime.datetime.strptime(r["Tarikh"], "%d/%m/%Y").date()
        except:
            continue

        if sunday <= rec_date <= saturday:
            if rec_date not in data_by_date:
                data_by_date[rec_date] = []
            data_by_date[rec_date].append(r)

    if not data_by_date:
        return None

    filename = f"Laporan_Kehadiran_Mingguan_{sunday.strftime('%d-%m-%Y')}_{saturday.strftime('%d-%m-%Y')}.pdf"

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    story = []

    title = f"Rekod Kehadiran Murid SK Labu Besar Minggu Ini<br/>Minggu: {sunday.strftime('%d/%m/%Y')} - {saturday.strftime('%d/%m/%Y')}"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 20))

    for rec_date in sorted(data_by_date.keys()):
        hari = rec_date.strftime("%A")
        tarikh_str = rec_date.strftime("%d/%m/%Y")

        story.append(Paragraph(f"📅 {hari}", styles["Heading2"]))
        story.append(Paragraph(f"🗓 {tarikh_str}", styles["Normal"]))
        story.append(Spacer(1, 10))

        for r in data_by_date[rec_date]:

            kelas = r["Kelas"]
            hadir = r.get("Hadir", r["Jumlah"])
            jumlah = r["Jumlah"]
            tidak_hadir = r["Tidak Hadir"]

            story.append(Paragraph(f"🏫 {kelas}", styles["Heading3"]))
            story.append(Paragraph(f"📊 Kehadiran: {hadir}/{jumlah}", styles["Normal"]))

            if tidak_hadir:
                names = [x.strip() for x in tidak_hadir.split(",")]
                story.append(Paragraph(f"❌ Tidak Hadir ({len(names)} murid)", styles["Normal"]))
                for i, n in enumerate(names, 1):
                    story.append(Paragraph(f"{i}. {n}", styles["Normal"]))
            else:
                story.append(Paragraph("🎉 Semua murid hadir.", styles["Normal"]))

            story.append(Spacer(1, 15))

        story.append(Spacer(1, 25))

    doc.build(story)
    return filename


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

    # ---------- EXPORT PDF MINGGUAN ----------
    if data == "export_pdf_week":

        await query.edit_message_text("⏳ Menjana laporan PDF minggu ini...")

        pdf_path = generate_weekly_pdf()

        if not pdf_path:
            await query.edit_message_text("❌ Tiada data kehadiran dijumpai untuk minggu ini.")
            return

        await query.message.reply_document(
            document=open(pdf_path, "rb"),
            filename=os.path.basename(pdf_path),
            caption="📄 Laporan Kehadiran Mingguan\nRekod Kehadiran Murid SK Labu Besar Minggu Ini"
        )

        os.remove(pdf_path)
        return

    # ---------- SEMAK ----------
    if data == "semak":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard = [[InlineKeyboardButton(k, callback_data=f"semak_kelas|{k}")] for k in kelas_list]
        keyboard.append([InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_week")])

        await query.edit_message_text("Pilih kelas untuk semak:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("semak_kelas|"):
        kelas = data.split("|")[1]
        user_state[user_id] = {"semak_kelas": kelas}

        keyboard = [
            [InlineKeyboardButton("📅 Hari Ini", callback_data="semak_tarikh|today")],
            [InlineKeyboardButton("📆 Semalam", callback_data="semak_tarikh|yesterday")],
            [InlineKeyboardButton("🗓 Pilih Tarikh", callback_data="semak_tarikh|calendar")],
            [InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_week")]
        ]

        await query.edit_message_text("Pilih tarikh:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # (SEMUA BAHAGIAN REKOD / SIMPAN / KALENDAR KEKAL SAMA DENGAN KOD ASAL AWAK)

    # ---------- SEMAK TARIKH ----------
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


# ======================
# MENU BUTTON HANDLER
# ======================
async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "🏠 Menu Utama":
        user_state.pop(update.message.from_user.id, None)
        await start(update, context)


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
        [InlineKeyboardButton("🗓 Pilih Tarikh", callback_data="semak_tarikh|calendar")],
        [InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_week")]
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
