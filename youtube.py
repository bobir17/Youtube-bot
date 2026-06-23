getsize(fpath)
    if fsize > MAX_FILE_SIZE_MB * 1024 * 1024:
        os.remove(fpath)
        await status.edit_text(f"❌ Fayl juda katta ({fsize//1024//1024}MB).\nKichikroq sifat tanlang.")
        return
    await status.edit_text("📤 Yuborilmoqda...")
    with open(fpath, "rb") as f:
        if mode == "audio":
            await query.message.reply_audio(audio=f, title=title[:64], caption=f"🎵 {title[:200]}")
        else:
            await query.message.reply_video(video=f, caption=f"🎬 {title[:200]}", supports_streaming=True)
    await status.delete()
    os.remove(fpath)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler
