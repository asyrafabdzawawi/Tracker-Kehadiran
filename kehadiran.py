# ======================
# BOT KEHADIRAN FINAL VERSION (STABIL & PRODUCTION READY)
# ======================

# ======================
# IMPORT
# ======================
import os, json, datetime, pytz, random
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
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
# UTIL
# ======================
def get_today_malaysia():
    tz = pytz.timezone("Asia/Kuala_Lumpur")
    return datetime.datetime.now(tz).date()


# =====================================================
# ================= SMART ANALYTICS ===================
# =====================================================

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
            total = int(r["Jumlah"])
            absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
            hadir = total - len(absent)

            statistik.setdefault(kelas, {"hadir": 0, "total": 0})
            statistik[kelas]["hadir"] += hadir
            statistik[kelas]["total"] += total

    if not statistik:
        return "Tiada data minggu ini."

    ranking = []
    for kelas, data in statistik.items():
        percent = (data["hadir"] / data["total"]) * 100
        ranking.append((kelas, percent))

    ranking.sort(key=lambda x: x[1], reverse=True)

    medals = ["🥇", "🥈", "🥉"]

    msg = "🏆 Ranking Mingguan\n"
    for i, (k, p) in enumerate(ranking):
        icon = medals[i] if i < 3 else ""
        msg += f"{i+1}. {icon} {k} - {p:.1f}%\n"

    lowest = ranking[-1]
    msg += f"\n⚠️ Terendah: {lowest[0]} ({lowest[1]:.1f}%)"

    risk = [k for k, p in ranking if p < 85]
    if risk:
        msg += "\n\n🧠 Risiko <85%:\n"
        for k in risk:
            msg += f"⚠️ {k}\n"

    return msg


def detect_decline_two_weeks():

    records = sheet_kehadiran.get_all_records()
    weekly_data = {}

    for r in records:
        kelas = r["Kelas"]
        tarikh = datetime.datetime.strptime(r["Tarikh"], "%d/%m/%Y").date()
        week = tarikh.isocalendar()[1]

        total = int(r["Jumlah"])
        absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
        hadir = total - len(absent)
        percent = (hadir / total) * 100

        weekly_data.setdefault(kelas, {}).setdefault(week, []).append(percent)

    decline = []

    for kelas, weeks in weekly_data.items():
        sorted_weeks = sorted(weeks.keys())
        if len(sorted_weeks) >= 2:
            last = sum(weeks[sorted_weeks[-1]]) / len(weeks[sorted_weeks[-1]])
            prev = sum(weeks[sorted_weeks[-2]]) / len(weeks[sorted_weeks[-2]])

            if last < prev:
                decline.append(kelas)

    return decline


def calculate_3_month_trend():

    today = get_today_malaysia()
    three_months_ago = today - datetime.timedelta(days=90)

    records = sheet_kehadiran.get_all_records()
    statistik = {}

    for r in records:
        tarikh_obj = datetime.datetime.strptime(r["Tarikh"], "%d/%m/%Y").date()

        if tarikh_obj >= three_months_ago:
            kelas = r["Kelas"]
            total = int(r["Jumlah"])
            absent = r["Tidak Hadir"].split(", ") if r["Tidak Hadir"] else []
            hadir = total - len(absent)

            statistik.setdefault(kelas, {"hadir": 0, "total": 0})
            statistik[kelas]["hadir"] += hadir
            statistik[kelas]["total"] += total

    trend = {}
    for kelas, data in statistik.items():
        trend[kelas] = (data["hadir"] / data["total"]) * 100

    return trend


def compare_year_groups():

    trend = calculate_3_month_trend()
    year_avg = {}

    for kelas, percent in trend.items():
        tahun = kelas.split()[0]
        if tahun.isdigit():
            year_avg.setdefault(tahun, []).append(percent)

    result = {}
    for tahun, values in year_avg.items():
        result[tahun] = sum(values) / len(values)

    return result


# =====================================================
# SMART DASHBOARD VIEW
# =====================================================

async def show_smart_dashboard(query):

    weekly = generate_weekly_summary()
    decline = detect_decline_two_weeks()
    trend3 = calculate_3_month_trend()
    year_compare = compare_year_groups()

    msg = "📊 SMART MONITORING SYSTEM 4.0\n\n"
    msg += weekly + "\n\n"

    if decline:
        msg += "🧠 2 Minggu Menurun:\n"
        for k in decline:
            msg += f"⚠️ {k}\n"
        msg += "\n"

    msg += "📈 Trend 3 Bulan:\n"
    for k, v in trend3.items():
        msg += f"{k} - {v:.1f}%\n"

    msg += "\n🏫 Perbandingan Tahun:\n"
    for tahun, val in year_compare.items():
        msg += f"Tahun {tahun} - {val:.1f}%\n"

    await query.edit_message_text(msg)


# =====================================================
# AUTO JUMAAT
# =====================================================

async def auto_send_friday_report(context: ContextTypes.DEFAULT_TYPE):

    summary = generate_weekly_summary()
    decline = detect_decline_two_weeks()

    msg = "📡 AUTO LAPORAN JUMAAT\n\n"
    msg += summary

    if decline:
        msg += "\n\n🧠 2 Minggu Menurun:\n"
        for k in decline:
            msg += f"⚠️ {k}\n"

    await context.bot.send_message(chat_id=GROUP_ID, text=msg)


# =====================================================
# MAIN
# =====================================================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.job_queue.run_daily(
        auto_send_friday_report,
        time=datetime.time(hour=14, minute=0),
        days=(4,)
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_button))

    print("🤖 Bot Kehadiran Smart 4.0 berjalan...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
