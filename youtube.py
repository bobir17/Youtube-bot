import os
import re
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DOWNLOAD_DIR = "./downloads"
MAX_FILE_SIZE_MB = 49

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YDL_BASE = {"quiet": True, "no_warnings": True, "extractor_args": {"youtube": {"player_client": ["tv", "ios", "android", "web"]}}, "http_headers": {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"}}

def is_youtube_url(url):
    return any(d in url for d in ["youtube.com", "youtu.be", "m.youtube.com"])

def clean_url(url):
    url = url.strip()
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[1].split("?")[0].split("&")[0]
        return "https://www.youtube.com/watch?v=" + vid
    if "youtube.com/watch" in url:
        m = re.search(r'v=([^&]+)', url)
        if m:
            return "https://www.youtube.com/watch?v=" + m.group(1)
    return url

def get_video_info(url):
    try:
        with yt_dlp.YoutubeDL(dict(YDL_BASE)) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.error("Info error: " + str(e))
        return None

def format_duration(s):
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return str(h) + ":" + str(m).zfill(2) + ":" + str(s).zfill(2)
    return str(m) + ":" + str(s).zfill(2)

def do_download(url, ydl_opts):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fname = ydl.prepare_filename(info)
            if os.path.exists(fname):
                return fname
            base = os.path.splitext(fname)[0]
            for ext in [".m4a", ".webm", ".mp3", ".mp4"]:
                if os.path.exists(base + ext):
                    return base + ext
    except Exception as e:
        logger.error("Download error: " + str(e))
    return None

async def start(update, context):
    await update.message.reply_text("Salom! YouTube havolasini yuboring.\n\nVideo (MP4) yoki Audio yuklash mumkin.\n49MB gacha fayllar yuboriladi.")

async def handle_url(update, context):
    msg_text = update.message.text or update.message.caption or ""
    urls = re.findall(r'https?://[^\s]+', msg_text)
    if not urls:
        await update.message.reply_text("Havola topilmadi. YouTube havolasini yuboring.")
        return
    url = clean_url(urls[0])
    if not is_youtube_url(url):
        await update.message.reply_text("Bu YouTube havolasi emas.")
        return
    msg = await update.message.reply_text("Ma'lumot olinmoqda...")
    info = get_video_info(url)
    if not info:
        await msg.edit_text("Video topilmadi yoki yuklab bo'lmadi.")
        return
    context.user_data["url"] = url
    context.user_data["title"] = info.get("title", "Video")
    title = info.get("title", "Nomalum")
    duration = info.get("duration", 0)
    uploader = info.get("uploader", "Nomalum")
    keyboard = [
        [InlineKeyboardButton("Video (MP4)", callback_data="format_video"), InlineKeyboardButton("Audio", callback_data="format_audio")],
        [InlineKeyboardButton("Bekor", callback_data="cancel")]
    ]
    text = title[:60] + "\n" + uploader + "\n" + format_duration(duration) + "\n\nFormat tanlang:"
    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_format(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.message.edit_text("Bekor qilindi.")
        return
    url = context.user_data.get("url")
    if not url:
        await query.message.edit_text("Havola topilmadi. Qayta yuboring.")
        return
    if query.data == "format_audio":
        await download_and_send(query, context, url, "audio")
    else:
        keyboard = [
            [InlineKeyboardButton("360p", callback_data="q_360")],
            [InlineKeyboardButton("720p HD", callback_data="q_720")],
            [InlineKeyboardButton("Bekor", callback_data="cancel")]
        ]
        await query.message.edit_text("Sifat tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_quality(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.message.edit_text("Bekor qilindi.")
        return
    url = context.user_data.get("url")
    if not url:
        await query.message.edit_text("Havola topilmadi.")
        return
    q = query.data.replace("q_", "")
    await download_and_send(query, context, url, "video", q)

async def download_and_send(query, context, url, mode, quality="360"):
    title = context.user_data.get("title", "video")
    uid = query.from_user.id
    out = os.path.join(DOWNLOAD_DIR, str(uid))
    os.makedirs(out, exist_ok=True)
    tmpl = os.path.join(out, "%(title).40s.%(ext)s")
    status = await query.message.edit_text("Yuklanmoqda... Kuting...")
    opts = dict(YDL_BASE)
    opts["outtmpl"] = tmpl
    if mode == "audio":
        opts["format"] = "bestaudio[ext=m4a]/bestaudio"
    else:
        opts["format"] = "best[height<=" + quality + "][ext=mp4]/best[height<=" + quality + "]/best"
    loop = asyncio.get_event_loop()
    fpath = await loop.run_in_executor(None, lambda: do_download(url, opts))
    if not fpath:
        await status.edit_text("Yuklashda xato. Qayta urinib ko'ring.")
        return
    fsize = os.path.getsize(fpath)
    if fsize > MAX_FILE_SIZE_MB * 1024 * 1024:
        os.remove(fpath)
        await status.edit_text("Fayl juda katta (" + str(fsize // 1024 // 1024) + "MB).\nKichikroq sifat tanlang.")
        return
    await status.edit_text("Yuborilmoqda...")
    try:
        with open(fpath, "rb") as f:
            if mode == "audio":
                await query.message.reply_audio(audio=f, title=title[:64], caption=title[:200])
            else:
                await query.message.reply_video(video=f, caption=title[:200], supports_streaming=True)
        await status.delete()
    except Exception as e:
        logger.error("Send error: " + str(e))
        await status.edit_text("Yuborishda xato yuz berdi.")
    finally:
        if os.path.exists(fpath):
            os.remove(fpath)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_format, pattern="^format_"))
    app.add_handler(CallbackQueryHandler(handle_quality, pattern="^q_"))
    app.add_handler(CallbackQueryHandler(handle_format, pattern="^cancel$"))
    print("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
