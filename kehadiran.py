# ======================
# IMPORT
# ======================
import os, json, datetime, pytz
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


    # ---------- SEMAK ----------
    if data == "semak":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard = [[InlineKeyboardButton(k, callback_data=f"semak_kelas|{k}")] for k in kelas_list]
        keyboard.append([InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_weekly")])

        await query.edit_message_text("Pilih kelas untuk semak:", reply_markup=InlineKeyboardMarkup(keyboard))
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

        # mesej baru di bawah
        await query.message.reply_text(
            f"🏫 {kelas}\n\nPilih tarikh:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return


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


    # ---------- NAVIGASI BULAN ----------
    if data.startswith("cal_nav|"):
        _, year, month = data.split("|")

        state = user_state[user_id]
        year = int(year)
        month = int(month)

        if month == 0:
            month = 12
            year -= 1
        elif month == 13:
            month = 1
            year += 1

        state["calendar_year"] = year
        state["calendar_month"] = month

        await show_calendar(query, user_id)
        return


    # ---------- PILIH HARI ----------
    if data.startswith("cal_day|"):
        _, year, month, day = data.split("|")

        target_date = f"{int(day):02d}/{int(month):02d}/{year}"
        state = user_state[user_id]
        kelas = state["semak_kelas"]

        await show_record_for_date(query, kelas, target_date)
        return


# ======================
# SHOW CALENDAR  (FIX UTAMA)
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

    # 🔴 EDIT MESEJ BARU (BUKAN edit_message_text)
    await query.message.edit_text("🗓 Pilih tarikh:", reply_markup=InlineKeyboardMarkup(keyboard))


# ======================
# SHOW RECORD FOR DATE  (FIX UTAMA)
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

            # 🔴 EDIT MESEJ YANG SAMA
            await query.message.edit_text(msg)
            return

    keyboard = [
        [InlineKeyboardButton("📅 Hari Ini", callback_data="semak_tarikh|today")],
        [InlineKeyboardButton("📆 Semalam", callback_data="semak_tarikh|yesterday")],
        [InlineKeyboardButton("🗓 Pilih Tarikh", callback_data="semak_tarikh|calendar")],
        [InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_weekly")]
    ]

    await query.message.edit_text(
        "❌ Tiada rekod untuk tarikh ini.\n\nPilih tarikh lain:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ======================
# EXPORT PDF MINGGUAN (LOGO OK)
# ======================
async def export_pdf_weekly(query):

    today = get_today_malaysia()
    start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)

    records = sheet_kehadiran.get_all_records()
    styles = getSampleStyleSheet()

    file_path = "/tmp/Rekod_Kehadiran_Mingguan.pdf"
    doc = SimpleDocTemplate(file_path)
    story = []

    logo_path = "sklb.png"   # 🔴 PASTIKAN FAIL INI DALAM REPO

    if os.path.exists(logo_path):
        img = Image(logo_path, width=80, height=80)
        img.hAlign = 'CENTER'
        story.append(img)
        story.append(Spacer(1, 12))

    story.append(Paragraph("Rekod Kehadiran Murid SK Labu Besar Minggu Ini", styles["Title"]))
    story.append(Spacer(1, 12))

    ada_data = False

    for i in range(7):
        day = start + datetime.timedelta(days=i)
        tarikh = day.strftime("%d/%m/%Y")
        hari = day.strftime("%A")

        daily = [r for r in records if r["Tarikh"] == tarikh]
        if not daily:
            continue

        ada_data = True
        story.append(Paragraph(f"{hari} : {tarikh}", styles["Heading2"]))
        story.append(Spacer(1, 8))

        for r in sorted(daily, key=lambda x: x["Kelas"]):
            absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
            hadir = int(r["Jumlah"]) - len(absent)

            story.append(Paragraph(f"Kelas : {r['Kelas']}", styles["Heading3"]))
            story.append(Paragraph(f"{hari} : {tarikh}", styles["Normal"]))
            story.append(Paragraph(f"Kehadiran : {hadir} / {r['Jumlah']}", styles["Normal"]))

            if absent:
                story.append(Paragraph(f"Tidak Hadir ({len(absent)} murid)", styles["Normal"]))
                for idx, name in enumerate(absent, 1):
                    story.append(Paragraph(f"{idx}. {name}", styles["Normal"]))
            else:
                story.append(Paragraph("Semua murid hadir", styles["Normal"]))

            story.append(Spacer(1, 10))

    if not ada_data:
        await query.message.edit_text("❌ Tiada data kehadiran untuk minggu ini.")
        return

    doc.build(story)

    await query.message.reply_document(
        document=open(file_path, "rb"),
        filename="Rekod_Kehadiran_Mingguan.pdf",
        caption="📄 Rekod Kehadiran Mingguan"
    )


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
