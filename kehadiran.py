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
GROUP_ID = int(os.environ.get("GROUP_ID"))   # 🔔 ID GROUP RASMI


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
    "🌤️ Semoga urusan hari ini dipermudahkan. Terima kasih atas dedikasi cikgu.",
    "Kurangkan manis dalam minuman🥤, lebihkan manis dalam senyuman😊",
    "💓 Orang kata jodoh buat jantung berdebar, tapi guru belum isi kehadiran pun boleh buat berdebar.",
    "🤍 Jangan takut gagal, kerana setiap kegagalan adalah batu loncatan menuju kejayaan.",
    "🎓 Terima kasih kerana terus komited demi anak-anak didik kita.",
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
# 🔔 SEMAK SEMUA KELAS & HANTAR KE GROUP
# ======================
async def check_all_classes_completed(context):

    today = get_today_malaysia()
    tarikh = today.strftime("%d/%m/%Y")

    records = sheet_kehadiran.get_all_records()

    recorded = set()
    for r in records:
        if r["Tarikh"] == tarikh:
            recorded.add(r["Kelas"].strip().lower())

    belum = [k for k in ALL_CLASSES if k.strip().lower() not in recorded]

    if not belum:

        msg = (
            "✅ Kehadiran Lengkap Hari Ini\n\n"
            f"📅 Tarikh: {tarikh}\n\n"
            "Semua kelas telah berjaya merekod kehadiran.\n"
            "Terima kasih atas kerjasama semua guru. 🙏\n\n"
            "📊 Sistem Tracker Kehadiran SK Labu Besar"
        )

        try:
            await context.bot.send_message(chat_id=GROUP_ID, text=msg)
        except Exception:
            pass


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

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard))
        await update.message.reply_text(
            "🏠 Tekan butang di bawah untuk kembali ke Menu Utama",
            reply_markup=reply_keyboard
        )
    else:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        await update.callback_query.message.reply_text(
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

    # ---------- SEMAK RMT HARI INI ----------
    if data == "semak_rmt_today":

        today = get_today_malaysia()
        tarikh = today.strftime("%d/%m/%Y")

        # Ambil semua murid RMT
        murid_records = sheet_murid.get_all_records()
        murid_rmt = [
            r["Nama Murid"]
            for r in murid_records
            if str(r.get("RMT", "")).strip().lower() == "ya"
        ]

        # Ambil rekod kehadiran hari ini
        hadir_records = sheet_kehadiran.get_all_records()

        tidak_hadir_rmt = []

        for r in hadir_records:
            if r["Tarikh"] == tarikh:
                absent_list = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
                for name in absent_list:
                    if name in murid_rmt:
                        tidak_hadir_rmt.append(name)

        total_rmt = len(murid_rmt)
        hadir_rmt = total_rmt - len(tidak_hadir_rmt)

        # Format mesej
        msg = (
            "🍱 Laporan Kehadiran RMT Hari Ini\n\n"
            f"📅 {tarikh}\n"
            f"📊 Hadir: {hadir_rmt} / {total_rmt}\n"
        )

        if tidak_hadir_rmt:
            msg += f"\n❌ Tidak Hadir ({len(tidak_hadir_rmt)} murid)\n"
            for i, n in enumerate(tidak_hadir_rmt, 1):
                msg += f"{i}. {n}\n"
        else:
            msg += "\n🎉 Semua murid RMT hadir hari ini.\n"

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

            keyboard = [[
                InlineKeyboardButton("✅ Ya, Overwrite", callback_data="confirm_overwrite"),
                InlineKeyboardButton("❌ Batal", callback_data="cancel_overwrite")
            ]]

            await query.edit_message_text(
                f"⚠️ Rekod kehadiran untuk\n\n🏫 {kelas}\n🗓 {tarikh}\n\nsudah wujud.\n\nAdakah anda mahu overwrite?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        sheet_kehadiran.append_row([tarikh, hari, kelas, hadir, total, ", ".join(absent)])
        msg = format_attendance(kelas, tarikh, hari, total, absent)
        await query.edit_message_text("✅ Kehadiran berjaya disimpan!\n\n" + msg)

        await check_all_classes_completed(context)

        user_state.pop(user_id, None)
        return

    # ---------- CONFIRM OVERWRITE ----------
    if data == "confirm_overwrite":

        info = user_state[user_id]["pending_overwrite"]
        sheet_kehadiran.delete_rows(info["row"])
        sheet_kehadiran.append_row([
            info["tarikh"], info["hari"], info["kelas"],
            info["hadir"], info["total"], ", ".join(info["absent"])
        ])

        msg = format_attendance(info["kelas"], info["tarikh"], info["hari"], info["total"], info["absent"])
        await query.edit_message_text("🔄 Rekod berjaya dioverwrite!\n\n" + msg)

        await check_all_classes_completed(context)

        user_state.pop(user_id, None)
        return

    # ---------- BATAL OVERWRITE ----------
    if data == "cancel_overwrite":
        await query.edit_message_text("❌ Overwrite dibatalkan. Rekod asal dikekalkan.")
        user_state.pop(user_id, None)
        return

    # ---------- SEMAK ----------
    if data == "semak":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))

        keyboard = [[InlineKeyboardButton(k, callback_data=f"semak_kelas|{k}")] for k in kelas_list]
        keyboard.append([InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_weekly")])

        await query.edit_message_text("Pilih kelas untuk semak:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # ---------- EXPORT PDF ----------
    if data == "export_pdf_weekly":
        await export_pdf_weekly(query)
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

    # ---------- SEMAK TARIKH ----------
    if data.startswith("semak_tarikh|"):
        choice = data.split("|")[1]
        state = user_state[user_id]
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
# (BAKI KOD: show_student_buttons, calendar, export_pdf, menu, main)
# ======================
# ❗ SEMUA BAHAGIAN BAWAH KEKAL SAMA SEPERTI KOD ASAL AWAK
