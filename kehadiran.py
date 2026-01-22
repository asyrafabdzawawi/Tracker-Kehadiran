# ---------- SEMAK KELAS BELUM ISI HARI INI ----------
if data == "kelas_belum_isi_today":

    kelas_dah, kelas_belum = semak_kelas_belum_isi_hari_ini()
    today = get_today_malaysia().strftime("%d/%m/%Y")

    msg = f"📊 Status Kehadiran Hari Ini\n📅 {today}\n\n"

    msg += "✅ Sudah isi:\n"
    if kelas_dah:
        for k in kelas_dah:
            msg += f"- {k}\n"
    else:
        msg += "- Belum ada\n"

    msg += "\n❌ Belum isi:\n"
    if kelas_belum:
        for k in kelas_belum:
            msg += f"- {k}\n"
    else:
        msg += "- Semua kelas telah lengkap 🎉\n"

    await query.edit_message_text(msg)
    return
