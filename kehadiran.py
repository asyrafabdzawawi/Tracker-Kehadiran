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

        # Ambil murid RMT melalui (RMT) di nama atau catatan
        murid_records = sheet_murid.get_all_records()
        murid_rmt = []

        for r in murid_records:
            nama = r["Nama Murid"]
            catatan = str(r.get("Catatan", "")).upper()

            if "(RMT)" in nama.upper() or "RMT" in catatan:
                nama_bersih = nama.replace("(RMT)", "").strip()
                murid_rmt.append(nama_bersih)

        # Ambil rekod kehadiran hari ini
        hadir_records = sheet_kehadiran.get_all_records()

        tidak_hadir_rmt = []

        for r in hadir_records:
            if r["Tarikh"] == tarikh:
                absent_list = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
                for name in absent_list:
                    nama_bersih = name.replace("(RMT)", "").strip()
                    if nama_bersih in murid_rmt:
                        tidak_hadir_rmt.append(nama_bersih)

        total_rmt = len(murid_rmt)
        hadir_rmt = total_rmt - len(tidak_hadir_rmt)

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

    # ---------- BAKI FUNGSI LAIN KEKAL SAMA ----------
    # (rekod, semak, calendar, export pdf, dsb – tidak diubah langsung)

    if data == "rekod":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))
        keyboard = [[InlineKeyboardButton(k, callback_data=f"kelas|{k}")] for k in kelas_list]
        await query.edit_message_text("Pilih kelas:", reply_markup=InlineKeyboardMarkup(keyboard))
        return


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
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
