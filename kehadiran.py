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
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.lib import colors
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import time
from zoneinfo import ZoneInfo


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
    "🌙✨ Selamat menunaikan ibadah puasa, semoga Ramadan kali ini membawa keberkatan yang melimpah, ketenangan dalam hati, kesihatan yang baik serta pahala yang berlipat ganda buat kita semua 🤲💖",
    "🕌🌟 Salam Ramadan Al-Mubarak, semoga setiap amalan yang kita lakukan sepanjang bulan mulia ini diterima Allah SWT dan menjadi asbab kebaikan di dunia serta akhirat 🤲📖✨",
    "🕌💚 Ramadan yang penuh barakah ini semoga mendidik hati kita menjadi lebih sabar, lebih bersyukur dan lebih dekat kepada Allah SWT dalam setiap keadaan 🤲✨",
    "🌙🤍 Selamat berpuasa, semoga kita diberikan kekuatan menahan lapar dan dahaga, kesabaran dalam menghadapi ujian serta keikhlasan dalam setiap ibadah yang dilakukan 💫🤲",
    "🌅🍽️ Semoga setiap waktu sahur dan berbuka menjadi saat yang penuh makna, mengeratkan silaturahim serta mengundang keberkatan dalam keluarga tercinta 🌙💞",
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
    [InlineKeyboardButton("🍱 Semak RMT Hari Ini", callback_data="semak_rmt_today")],
    [InlineKeyboardButton("📊 Statistik Kehadiran", callback_data="smart_statistik")]
    ]

    reply_keyboard = ReplyKeyboardMarkup([[KeyboardButton("🏠 Menu Utama")]], resize_keyboard=True)

    quote = get_random_quote()

    text = (
        "🏫 Tracker Kehadiran Murid SK Labu Besar\n\n"
        f"💬 {quote}\n\n"
        "Pilih menu:"
    )

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

    if data == "semak_rmt_today":

        today = get_today_malaysia()
        tarikh = today.strftime("%d/%m/%Y")

        murid_records = sheet_murid.get_all_records()

        # ======================
        # BINA DATA RMT → KELAS
        # ======================
        rmt_by_class = {}
        all_rmt_students = set()

        for r in murid_records:
            nama = r["Nama Murid"]
            kelas = r["Kelas"]
            catatan = str(r.get("Catatan", "")).upper()

            if "(RMT)" in nama.upper() or "RMT" in catatan:
                nama_bersih = nama.replace("(RMT)", "").strip()
                all_rmt_students.add(nama_bersih)

                if kelas not in rmt_by_class:
                    rmt_by_class[kelas] = []

                rmt_by_class[kelas].append(nama_bersih)

        # ======================
        # SEMAK KEHADIRAN
        # ======================
        hadir_records = sheet_kehadiran.get_all_records()
        tidak_hadir_by_class = {}

        for r in hadir_records:
            if r["Tarikh"] == tarikh:
                kelas = r["Kelas"]
                absent_list = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []

                for name in absent_list:
                    nama_bersih = name.replace("(RMT)", "").strip()
                    if nama_bersih in all_rmt_students:
                        tidak_hadir_by_class.setdefault(kelas, []).append(nama_bersih)

        # ======================
        # KIRAAN
        # ======================
        total_rmt = len(all_rmt_students)
        total_tidak_hadir = sum(len(v) for v in tidak_hadir_by_class.values())
        hadir_rmt = total_rmt - total_tidak_hadir

        # ======================
        # PAPARAN
        # ======================
        msg = (
            "🍱 Laporan Kehadiran RMT Hari Ini\n\n"
            f"📅 {tarikh}\n"
            f"📊 Hadir: {hadir_rmt} / {total_rmt}\n"
        )

        if tidak_hadir_by_class:
            msg += f"\n❌ Tidak Hadir ({total_tidak_hadir} murid)\n"

            for kelas in sorted(tidak_hadir_by_class):
                murid = tidak_hadir_by_class[kelas]
                msg += f"\n🏫 {kelas}\n"
                for i, nama in enumerate(murid, 1):
                    msg += f"{i}. {nama}\n"
        else:
            msg += "\n🎉 Semua murid RMT hadir hari ini.\n"

        await query.edit_message_text(msg)
        return

    if data == "smart_statistik":
        await show_smart_dashboard(query)
        return


    # ---------- REKOD ----------
    if data == "rekod":
        records = sheet_murid.get_all_records()
        kelas_list = sorted(set(r["Kelas"] for r in records))
        
        keyboard = []
        row = []

        for k in kelas_list:
            row.append(InlineKeyboardButton(k, callback_data=f"kelas|{k}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

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

        # 🔔 PANGGIL SEMAK GROUP
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

        # 🔔 PANGGIL SEMAK GROUP
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

        keyboard = []
        row = []

        for k in kelas_list:
            row.append(InlineKeyboardButton(k, callback_data=f"semak_kelas|{k}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_weekly")
        ])


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
            try:
                await query.edit_message_text(msg)
            except Exception:
                pass
            return

    keyboard = [
        [InlineKeyboardButton("📅 Hari Ini", callback_data="semak_tarikh|today")],
        [InlineKeyboardButton("📆 Semalam", callback_data="semak_tarikh|yesterday")],
        [InlineKeyboardButton("🗓 Pilih Tarikh", callback_data="semak_tarikh|calendar")],
        [InlineKeyboardButton("📄 Export PDF Mingguan", callback_data="export_pdf_weekly")]
    ]

    try:
        await query.edit_message_text(
            "❌ Tiada rekod untuk tarikh ini.\n\nPilih tarikh lain:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception:
        pass


# ======================
# EXPORT PDF MINGGUAN
# ======================
async def export_pdf_weekly(query):

    today = get_today_malaysia()
    start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)

    records = sheet_kehadiran.get_all_records()
    styles = getSampleStyleSheet()

    file_path = "/tmp/Rekod_Kehadiran_Mingguan.pdf"
    doc = SimpleDocTemplate(file_path)
    story = []

    story.append(Paragraph("Rekod Kehadiran Murid SK Labu Besar", styles["Title"]))
    story.append(Paragraph("Laporan Mingguan", styles["Heading2"]))
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

        story.append(Paragraph(f"{hari}  |  {tarikh}", styles["Heading2"]))
        story.append(Spacer(1, 8))

        for r in sorted(daily, key=lambda x: x["Kelas"]):
            absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
            hadir = int(r["Jumlah"]) - len(absent)

            story.append(Paragraph(f"<b>Kelas : {r['Kelas']}</b>", styles["Heading3"]))
            story.append(Paragraph(f"Hari : {hari}", styles["Normal"]))
            story.append(Paragraph(f"Tarikh : {tarikh}", styles["Normal"]))
            story.append(Spacer(1, 4))

            story.append(Paragraph(f"Kehadiran : {hadir} / {r['Jumlah']}", styles["Normal"]))

            if absent:
                story.append(Paragraph("Tidak Hadir:", styles["Normal"]))
                for idx, name in enumerate(absent, 1):
                    story.append(Paragraph(f"{idx}. {name}", styles["Normal"]))
            else:
                story.append(Paragraph("Semua murid hadir", styles["Normal"]))

            story.append(Spacer(1, 12))

    if not ada_data:
        story.append(Paragraph(
            "Tiada rekod kehadiran direkodkan setakat ini untuk minggu ini.",
        styles["Normal"]
    ))
        story.append(Spacer(1, 12))

    # 📊 Bar Chart Ranking Mingguan
    summary, top3 = generate_weekly_summary()

    if top3:

        drawing = Drawing(400, 200)
        chart = VerticalBarChart()
        chart.x = 50
        chart.y = 50
        chart.height = 125
        chart.width = 300

        chart.data = [[p for _, p in top3]]
        chart.categoryAxis.categoryNames = [k for k, _ in top3]
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = 100

        drawing.add(chart)
        story.append(Spacer(1, 20))
        story.append(Paragraph("Graf Top 3 Kehadiran Mingguan", styles["Heading2"]))
        story.append(drawing)
        
    doc.build(story)

    await query.message.reply_document(
        document=open(file_path, "rb"),
        filename="Rekod_Kehadiran_Mingguan.pdf",
        caption="📄 Rekod Kehadiran Mingguan"
    )

# ======================
# SMART MONITORING 4.0
# ======================

async def show_smart_dashboard(query):

    # 🏆 Top 3 Bulanan
    monthly_summary, monthly_top3 = generate_monthly_summary()

    # 📊 Ranking Mingguan
    weekly_summary, _ = generate_weekly_summary()

    decline = detect_decline_two_weeks()
    trend = calculate_1_month_trend()

    msg = "📊 Statistik Kehadiran\n\n"

    # 🏆 Top 3 Bulanan
    msg += "🏆 Top 3 Kehadiran Bulanan\n"
    for i, (k, p) in enumerate(monthly_top3):
        medal = ["🥇","🥈","🥉"][i]
        msg += f"{medal} {k} - {p:.1f}%\n"

    # 📊 Ranking Mingguan (guna weekly)
    msg += "\n" + weekly_summary + "\n\n"

    if decline:
        msg += "⚠️ Kehadiran merosot dalam tempoh 2 minggu:\n"
        for k in decline:
            msg += f"- {k}\n"
        msg += "\n"

    msg += "📈 Trend 1 Bulan (Tertinggi → Terendah)\n"
    for k, v in trend:
        msg += f"{k} - {v:.1f}%\n"

    await query.edit_message_text(msg)


def generate_weekly_summary():

    today = get_today_malaysia()
    start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)

    records = sheet_kehadiran.get_all_records()
    statistik = {}

    for i in range(7):
        day = start + datetime.timedelta(days=i)
        tarikh = day.strftime("%d/%m/%Y")

        daily = [r for r in records if r["Tarikh"] == tarikh]

        for r in daily:
            kelas = r["Kelas"]
            try:
                total = int(r["Jumlah"])
            except:
                continue

            absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
            hadir = total - len(absent)

            statistik.setdefault(kelas, {"hadir": 0, "total": 0})
            statistik[kelas]["hadir"] += hadir
            statistik[kelas]["total"] += total

    if not statistik:
        return "Tiada data minggu ini.", []

    ranking = []
    for kelas, data in statistik.items():
        percent = (data["hadir"] / data["total"]) * 100
        ranking.append((kelas, percent))

    ranking.sort(key=lambda x: x[1], reverse=True)

    msg = "📊 Ranking Mingguan\n"
    for i, (k, p) in enumerate(ranking):
        msg += f"{i+1}. {k} - {p:.1f}%\n"

    return msg, ranking[:3]

def generate_monthly_summary():

    today = get_today_malaysia()
    one_month_ago = today - datetime.timedelta(days=30)

    records = sheet_kehadiran.get_all_records()
    statistik = {}

    for r in records:

        try:
            tarikh_obj = datetime.datetime.strptime(r["Tarikh"], "%d/%m/%Y").date()
        except:
            continue

        if tarikh_obj < one_month_ago:
            continue

        kelas = r["Kelas"]

        try:
            total = int(r["Jumlah"])
        except:
            continue

        if total <= 0:
            continue

        absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
        hadir = total - len(absent)

        statistik.setdefault(kelas, {"hadir": 0, "total": 0})
        statistik[kelas]["hadir"] += hadir
        statistik[kelas]["total"] += total

    if not statistik:
        return "Tiada data bulan ini.", []

    ranking = []
    for kelas, data in statistik.items():
        percent = (data["hadir"] / data["total"]) * 100
        ranking.append((kelas, percent))

    ranking.sort(key=lambda x: x[1], reverse=True)

    msg = "📊 Ranking Bulanan\n"
    for i, (k, p) in enumerate(ranking):
        msg += f"{i+1}. {k} - {p:.1f}%\n"

    return msg, ranking[:3]

def calculate_1_month_trend():

    today = get_today_malaysia()
    one_month_ago = today - datetime.timedelta(days=30)

    records = sheet_kehadiran.get_all_records()
    statistik = {}

    for r in records:

        try:
            tarikh_obj = datetime.datetime.strptime(r["Tarikh"], "%d/%m/%Y").date()
        except:
            continue

        if tarikh_obj < one_month_ago:
            continue

        kelas = r["Kelas"]

        try:
            total = int(r["Jumlah"])
        except:
            continue

        if total <= 0:
            continue

        absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
        hadir = total - len(absent)

        statistik.setdefault(kelas, {"hadir": 0, "total": 0})
        statistik[kelas]["hadir"] += hadir
        statistik[kelas]["total"] += total

    ranking = []
    for kelas, data in statistik.items():
        percent = (data["hadir"] / data["total"]) * 100
        ranking.append((kelas, percent))

    ranking.sort(key=lambda x: x[1], reverse=True)

    return ranking


def detect_decline_two_weeks():

    records = sheet_kehadiran.get_all_records()
    statistik = {}

    for r in records:
        kelas = r["Kelas"]

        try:
            total = int(r["Jumlah"])
        except (ValueError, TypeError):
            continue

        if total <= 0:
            continue

        absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
        hadir = total - len(absent)

        percent = (hadir / total) * 100

        statistik.setdefault(kelas, []).append(percent)

    decline = []
    for kelas, values in statistik.items():
        if len(values) >= 2 and values[-1] < values[-2]:
            decline.append(kelas)

    return decline
# ======================
# MENU BUTTON HANDLER
# ======================
async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "🏠 Menu Utama":
        user_state.pop(update.message.from_user.id, None)
        await start(update, context)

async def auto_send_friday_report(context: ContextTypes.DEFAULT_TYPE):

    summary, top3 = generate_weekly_summary()
    decline = detect_decline_two_weeks()

    msg = "📡 AUTO LAPORAN KEHADIRAN MINGGUAN\n\n"

    if top3:
        msg += "🏆 Top 3 Mingguan\n"
        for i, (k, p) in enumerate(top3):
            medal = ["🥇","🥈","🥉"][i]
            msg += f"{medal} {k} - {p:.1f}%\n"
        msg += "\n"

    msg += summary

    if decline:
        msg += "\n\n🧠 2 Minggu Menurun:\n"
        for k in decline:
            msg += f"⚠️ {k}\n"

    await context.bot.send_message(chat_id=GROUP_ID, text=msg)

# ======================
# 🔔 AUTO REMINDER 9:45 PAGI
# ======================

async def auto_reminder_unupdated_classes(context: ContextTypes.DEFAULT_TYPE):

    today = get_today_malaysia()
    tarikh = today.strftime("%d/%m/%Y")

    records = sheet_kehadiran.get_all_records()

    recorded = set()
    for r in records:
        if r["Tarikh"] == tarikh:
            recorded.add(r["Kelas"].strip().lower())

    belum_update = [
        k for k in ALL_CLASSES
        if k.strip().lower() not in recorded
    ]

    if not belum_update:
        # Semua dah update, tak perlu hantar apa-apa
        return

    msg = (
        "⏰ PERINGATAN PENGISIAN KEHADIRAN KELAS \n\n"
        f"📅 {tarikh}\n\n"
        "Kelas berikut masih belum mengisi kehadiran:\n\n"
    )

    for i, kelas in enumerate(belum_update, 1):
        msg += f"{i}. {kelas}\n"

    msg += "\n⚠️ Mohon guru semasa ambil tindakan segera.\n\n"
    msg += "\n Mesej ini dijana secara automatik.\n\n"
    msg += "📊 Sistem Tracker Kehadiran SK Labu Besar"

    try:
        await context.bot.send_message(chat_id=GROUP_ID, text=msg)
    except Exception:
        pass
# ======================
# MAIN
# ======================


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Auto Jumaat 2PM (Malaysia Time)
    
    FRIDAY = 4
    
    app.job_queue.run_daily(
        auto_send_friday_report,
        time=time(14, 0, tzinfo=ZoneInfo("Asia/Kuala_Lumpur")),
        days=(FRIDAY,)
    )

    # Auto Reminder 9:45 pagi (Isnin - Jumaat)

    app.job_queue.run_daily(
        auto_reminder_unupdated_classes,
        time=time(9, 45, tzinfo=ZoneInfo("Asia/Kuala_Lumpur")),
        days=(6,0,1,2,3)  # Isnin hingga Jumaat
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_button))

    print("🤖 Bot Kehadiran Smart 4.0 berjalan...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
