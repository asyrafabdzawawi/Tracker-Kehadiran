# ======================
# IMPORT
# ======================
import os, json, datetime, pytz
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

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

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

def already_recorded(kelas, tarikh):
    records = sheet_kehadiran.get_all_records()
    for r in records:
        if r["Kelas"] == kelas and r["Tarikh"] == tarikh:
            return True
    return False

# ======================
# START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    inline_keyboard = [
        [InlineKeyboardButton("📋 Rekod Kehadiran", callback_data="rekod")],
        [InlineKeyboardButton("🔍 Semak Kehadiran", callback_data="semak")],
        [InlineKeyboardButton("🍱 Semak RMT Hari Ini", callback_data="semak_rmt_today")]
    ]

    reply_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🏠 Menu Utama")]],
        resize_keyboard=True
    )

    text = "Tracker Kehadiran Murid SK Labu Besar\n\nPilih menu:"

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
        await update.message.reply_text("🏠 Tekan Menu Utama di bawah", reply_markup=reply_keyboard)

# ======================
# BUTTON HANDLER (SEMUA CALLBACK DALAM SATU TEMPAT)
# ======================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # ---------- SEMAK RMT ----------
    if data == "semak_rmt_today":
        today = get_today_malaysia().strftime("%d/%m/%Y")
        records = sheet_kehadiran.get_all_records()
        murid = sheet_murid.get_all_records()

        rmt = [r["Nama Murid"] for r in murid if "RMT" in str(r.get("Catatan", ""))]

        result = []
        for r in records:
            if r["Tarikh"] == today and r["Tidak Hadir"]:
                for name in r["Tidak Hadir"].split(","):
                    if name.replace("(RMT)", "").strip() in rmt:
                        result.append(f"{name} - {r['Kelas']}")

        if not result:
            await query.edit_message_text(f"🎉 Semua murid RMT hadir hari ini\n📅 {today}")
            return

        msg = f"🍱 RMT Tidak Hadir Hari Ini\n📅 {today}\n\n"
        for i, n in enumerate(result, 1):
            msg += f"{i}. {n}\n"

        await query.edit_message_text(msg)
        return

    # ---------- REKOD ----------
    if data == "rekod":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))
        keyboard = [[InlineKeyboardButton(k, callback_data=f"kelas|{k}")] for k in kelas_list]
        await query.edit_message_text("Pilih kelas:", reply_markup=InlineKeyboardMarkup(keyboard))
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

    # ---------- SIMPAN ----------
    if data == "simpan":
        state = user_state[user_id]
        kelas = state["kelas"]
        tarikh = state["tarikh"]

        if already_recorded(kelas, tarikh):
            await query.edit_message_text("❌ Rekod telah wujud.")
            return

        total = len(state["students"])
        absent = state["absent"]
        hadir = total - len(absent)

        sheet_kehadiran.append_row([
            tarikh, state["hari"], kelas, hadir, total, ", ".join(absent)
        ])

        msg = format_attendance(kelas, tarikh, state["hari"], total, absent)
        await query.edit_message_text("✅ Disimpan\n\n" + msg)
        return

    # ---------- SEMUA HADIR ----------
    if data == "semua_hadir":
        state = user_state[user_id]
        kelas = state["kelas"]
        tarikh = state["tarikh"]

        if already_recorded(kelas, tarikh):
            await query.edit_message_text("❌ Rekod telah wujud.")
            return

        total = len(state["students"])

        sheet_kehadiran.append_row([
            tarikh, state["hari"], kelas, total, total, ""
        ])

        msg = format_attendance(kelas, tarikh, state["hari"], total, [])
        await query.edit_message_text("✅ Disimpan\n\n" + msg)
        return

    # ---------- SEMAK ----------
    if data == "semak":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard = [[InlineKeyboardButton(k, callback_data=f"semak_kelas|{k}")] for k in kelas_list]
        keyboard.append([InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_weekly")])

        await query.edit_message_text("Pilih kelas:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- EXPORT PDF ----------
    if data == "export_pdf_weekly":
        await export_pdf_weekly(query)
        return

# ======================
# SHOW STUDENT BUTTONS
# ======================
async def show_student_buttons(query, user_id):
    state = user_state[user_id]
    keyboard = []

    for n in state["students"]:
        label = f"🔴 {n}" if n in state["absent"] else f"🟢 {n}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"murid|{n}")])

    keyboard.append([
        InlineKeyboardButton("💾 Simpan", callback_data="simpan"),
        InlineKeyboardButton("♻️ Reset", callback_data="reset"),
        InlineKeyboardButton("✅ Semua Hadir", callback_data="semua_hadir")
    ])

    msg = format_attendance(
        state["kelas"], state["tarikh"], state["hari"],
        len(state["students"]), state["absent"]
    )

    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# ======================
# EXPORT PDF
# ======================
async def export_pdf_weekly(query):

    today = get_today_malaysia()
    start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
    end = start + datetime.timedelta(days=6)

    records = sheet_kehadiran.get_all_records()

    styles = getSampleStyleSheet()
    file_path = "/tmp/Rekod_Kehadiran_Mingguan.pdf"
    doc = SimpleDocTemplate(file_path)

    story = []
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
        story.append(Paragraph(f"{hari} - {tarikh}", styles["Heading2"]))

        for r in daily:
            absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
            text = format_attendance(
                r["Kelas"], r["Tarikh"], r["Hari"], int(r["Jumlah"]), absent
            ).replace("\n", "<br/>")

            story.append(Paragraph(text, styles["BodyText"]))
            story.append(Spacer(1, 10))

    if not ada_data:
        await query.edit_message_text("❌ Tiada data minggu ini.")
        return

    doc.build(story)

    await query.message.reply_document(
        document=open(file_path, "rb"),
        filename="Rekod_Kehadiran_Mingguan.pdf",
        caption="📄 Rekod Kehadiran Mingguan"
    )

# ======================
# MENU BUTTON
# ======================
async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🏠 Menu Utama":
        await start(update, context)

# ======================
# MAIN
# ======================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_button))

    print("🤖 Bot Kehadiran berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
