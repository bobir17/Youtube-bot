import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import yt_dlp

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DOWNLOAD_DIR = "./downloads"
MAX_FILE_SIZE_MB = 50

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def is_youtube_url(url):
    return any(d in url for d in ["youtube.com", "youtu.be", "m.youtube.com"])

def get_video_info(url):
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            return ydl.extract_info(url, download=False)
    except:
        return None

def format_duration(s):
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

async def start(update, context):
    await update.message.reply_text(
        "👋 Salom! YouTube havolasini yuboring.\n\n"
        "🎥 Video (MP4) yoki 🎵 Audio (MP3) yuklash mumkin.\n"
        "⚠️ Telegram 50MB gacha fayllarni qabul qiladi."
    )

async def handle_url(update, context):
    url = update.message.text.strip()
    if not is_youtube_url(url):
        await update.message.reply_text("❌ Bu YouTube havolasi emas. To'g'ri havola yuboring.")
        return
    msg = await update.message.reply_text("⏳ Ma'lumot olinmoqda...")
    info = get_video_info(url)
    if not info:
        await msg.edit_text("❌ Video topilmadi yoki xususiy video.")
        return
    context.user_data["url"] = url
    context.user_data["title"] = info.get("title", "Video")
    title = info.get("title", "Noma'lum")
    duration = info.get("duration", 0)
    uploader = info.get("uploader", "Noma'lum")
    keyboard = [
        [InlineKeyboardButton("🎥 Video (MP4)", callback_data="format_video"),
         InlineKeyboardButton("🎵 Audio (MP3)", callback_data="format_audio")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]
    ]
    await msg.edit_text(
        f"📹 *{title[:60]}*\n👤 {uploader}\n⏱ {format_duration(duration)}\n\nFormat tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_format(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.message.edit_text("❌ Bekor qilindi.")
        return
    url = context.user_data.get("url")
    if not url:
        await query.message.edit_text("❌ Havola topilmadi. Qayta yuboring.")
        return
    if query.data == "format_audio":
        await download_send(query, context, url, "audio")
    else:
        keyboard = [
            [InlineKeyboardButton("📱 360p", callback_data="q_360")],
            [InlineKeyboardButton("💻 720p HD", callback_data="q_720")],
            [InlineKeyboardButton("🖥 1080p Full HD", callback_data="q_1080")],
            [InlineKeyboardButton("❌ Bekor", callback_data="cancel")]
        ]
        await query.message.edit_text("🎥 Sifat tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_quality(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.message.edit_text("❌ Bekor qilindi.")
        return
    url = context.user_data.get("url")
    if not url:
        await query.message.edit_text("❌ Havola topilmadi.")
        return
    q = query.data.replace("q_", "")
    await download_send(query, context, url, "video", q)

def _do_download(url, ydl_opts, out_path):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fname = ydl.prepare_filename(info)
            if os.path.exists(fname):
                return fname
            base = os.path.splitext(fname)[0]
            for ext in [".mp3", ".mp4", ".webm", ".m4a"]:
                if os.path.exists(base + ext):
                    return base + ext
    except Exception as e:
        logger.error(f"Download error: {e}")
    return None

async def download_send(query, context, url, mode, quality="720"):
    title = context.user_data.get("title", "video")
    uid = query.from_user.id
    out = os.path.join(DOWNLOAD_DIR, str(uid))
    os.makedirs(out, exist_ok=True)
    tmpl = os.path.join(out, "%(title).40s.%(ext)s")
    status = await query.message.edit_text("⬇️ Yuklanmoqda... Kuting...")
    if mode == "audio":
        opts = {
            "format": "bestaudio/best",
            "outtmpl": tmpl,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
            "quiet": True,
        }
    else:
        opts = {
            "format": f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]/best",
            "outtmpl": tmpl,
            "merge_output_format": "mp4",
            "quiet": True,
        }
    loop = asyncio.get_event_loop()
    fpath = await loop.run_in_executor(None, lambda: _do_download(url, opts, out))
    if not fpath:
        await status.edit_text("❌ Yuklashda xato. Qayta urinib ko'ring.")
        return
    fsize = os.path.getsize(fpath)
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
    app.add_handler(CallbackQueryHandler(handle_format, pattern="^format_"))
    app.add_handler(CallbackQueryHandler(handle_quality, pattern="^q_"))
    app.add_handler(CallbackQueryHandler(handle_format, pattern="^cancel$"))
    print("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
