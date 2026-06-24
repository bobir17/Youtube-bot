import os
import re
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp
import imageio_ffmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DOWNLOAD_DIR = "./downloads"
MAX_FILE_SIZE_MB = 49

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YDL_BASE = {"quiet": True, "no_warnings": True, "ffmpeg_location": FFMPEG_PATH, "extractor_args": {"youtube": {"player_client": ["android", "web"]}}}

TEXTS = {
    "uz": {
        "start": "Salom! YouTube havolasini yuboring.\n\nVideo (MP4) yoki Audio (MP3) yuklash mumkin.\n49MB gacha fayllar yuboriladi.",
        "no_link": "Havola topilmadi. YouTube havolasini yuboring.",
        "not_youtube": "Bu YouTube havolasi emas.",
        "getting_info": "Ma'lumot olinmoqda...",
        "not_found": "Video topilmadi yoki yuklab bo'lmadi.",
        "choose_format": "Format tanlang:",
        "video": "Video (MP4)",
        "audio": "Audio (MP3)",
        "cancel": "Bekor",
        "cancelled": "Bekor qilindi.",
        "link_not_found": "Havola topilmadi. Qayta yuboring.",
        "choose_quality": "Sifat tanlang:",
        "downloading": "Yuklanmoqda... Kuting...",
        "download_error": "Yuklashda xato. Qayta urinib ko'ring.",
        "too_big": "Fayl juda katta (",
        "too_big_end": "MB).\nKichikroq sifat tanlang.",
        "sending": "Yuborilmoqda...",
        "lang_chosen": "Til tanlandi! Endi YouTube havolasini yuboring.",
    },
    "ru": {
        "start": "Привет! Отправьте ссылку на YouTube.\n\nМожно скачать Видео (MP4) или Аудио (MP3).\nФайлы до 49МБ.",
        "no_link": "Ссылка не найдена. Отправьте ссылку YouTube.",
        "not_youtube": "Это не ссылка YouTube.",
        "getting_info": "Получаю информацию...",
        "not_found": "Видео не найдено или не удалось загрузить.",
        "choose_format": "Выберите формат:",
        "video": "Видео (MP4)",
        "audio": "Аудио (MP3)",
        "cancel": "Отмена",
        "cancelled": "Отменено.",
        "link_not_found": "Ссылка не найдена. Отправьте снова.",
        "choose_quality": "Выберите качество:",
        "downloading": "Загрузка... Подождите...",
        "download_error": "Ошибка загрузки. Попробуйте снова.",
        "too_big": "Файл слишком большой (",
        "too_big_end": "МБ).\nВыберите качество ниже.",
        "sending": "Отправка...",
        "lang_chosen": "Язык выбран! Теперь отправьте ссылку YouTube.",
    },
    "en": {
        "start": "Hello! Send a YouTube link.\n\nYou can download Video (MP4) or Audio (MP3).\nFiles up to 49MB.",
        "no_link": "No link found. Send a YouTube link.",
        "not_youtube": "This is not a YouTube link.",
        "getting_info": "Getting info...",
        "not_found": "Video not found or could not be loaded.",
        "choose_format": "Choose format:",
        "video": "Video (MP4)",
        "audio": "Audio (MP3)",
        "cancel": "Cancel",
        "cancelled": "Cancelled.",
        "link_not_found": "Link not found. Send again.",
        "choose_quality": "Choose quality:",
        "downloading": "Downloading... Please wait...",
        "download_error": "Download error. Try again.",
        "too_big": "File too big (",
        "too_big_end": "MB).\nChoose lower quality.",
        "sending": "Sending...",
        "lang_chosen": "Language selected! Now send a YouTube link.",
    },
}

def t(context, key):
    lang = context.user_data.get("lang", "uz")
    return TEXTS[lang][key]

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
            for ext in [".mp3", ".m4a", ".webm", ".mp4"]:
                if os.path.exists(base + ext):
                    return base + ext
    except Exception as e:
        logger.error("Download error: " + str(e))
    return None

async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
    ]
    await update.message.reply_text(
        "Tilni tanlang / Выберите язык / Choose language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_lang(update, context):
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("lang_", "")
    context.user_data["lang"] = lang
    await query.message.edit_text(TEXTS[lang]["lang_chosen"])

async def handle_url(update, context):
    msg_text = update.message.text or update.message.caption or ""
    urls = re.findall(r'https?://[^\s]+', msg_text)
    if not urls:
        await update.message.reply_text(t(context, "no_link"))
        return
    url = clean_url(urls[0])
    if not is_youtube_url(url):
        await update.message.reply_text(t(context, "not_youtube"))
        return
    msg = await update.message.reply_text(t(context, "getting_info"))
    info = get_video_info(url)
    if not info:
        await msg.edit_text(t(context, "not_found"))
        return
    context.user_data["url"] = url
    context.user_data["title"] = info.get("title", "Video")
    title = info.get("title", "Video")
    duration = info.get("duration", 0)
    uploader = info.get("uploader", "")
    keyboard = [
        [InlineKeyboardButton(t(context, "video"), callback_data="format_video"), InlineKeyboardButton(t(context, "audio"), callback_data="format_audio")],
        [InlineKeyboardButton(t(context, "cancel"), callback_data="cancel")]
    ]
    text = title[:60] + "\n" + uploader + "\n" + format_duration(duration) + "\n\n" + t(context, "choose_format")
    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_format(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.message.edit_text(t(context, "cancelled"))
        return
    url = context.user_data.get("url")
    if not url:
        await query.message.edit_text(t(context, "link_not_found"))
        return
    if query.data == "format_audio":
        await download_and_send(query, context, url, "audio")
    else:
        keyboard = [
            [InlineKeyboardButton("360p", callback_data="q_360")],
            [InlineKeyboardButton("720p HD", callback_data="q_720")],
            [InlineKeyboardButton(t(context, "cancel"), callback_data="cancel")]
        ]
        await query.message.edit_text(t(context, "choose_quality"), reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_quality(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.message.edit_text(t(context, "cancelled"))
        return
    url = context.user_data.get("url")
    if not url:
        await query.message.edit_text(t(context, "link_not_found"))
        return
    q = query.data.replace("q_", "")
    await download_and_send(query, context, url, "video", q)

async def download_and_send(query, context, url, mode, quality="360"):
    title = context.user_data.get("title", "video")
    uid = query.from_user.id
    out = os.path.join(DOWNLOAD_DIR, str(uid))
    os.makedirs(out, exist_ok=True)
    tmpl = os.path.join(out, "%(title).40s.%(ext)s")
    status = await query.message.edit_text(t(context, "downloading"))
    opts = dict(YDL_BASE)
    opts["outtmpl"] = tmpl
    if mode == "audio":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    else:
        opts["format"] = "best[height<=" + quality + "][ext=mp4]/best[height<=" + quality + "]/best"
    loop = asyncio.get_event_loop()
    fpath = await loop.run_in_executor(None, lambda: do_download(url, opts))
    if not fpath:
        await status.edit_text(t(context, "download_error"))
        return
    fsize = os.path.getsize(fpath)
    if fsize > MAX_FILE_SIZE_MB * 1024 * 1024:
        os.remove(fpath)
        await status.edit_text(t(context, "too_big") + str(fsize // 1024 // 1024) + t(context, "too_big_end"))
        return
    await status.edit_text(t(context, "sending"))
    try:
        with open(fpath, "rb") as f:
            if mode == "audio":
                await query.message.reply_audio(audio=f, title=title[:64], caption=title[:200])
            else:
                await query.message.reply_video(video=f, caption=title[:200], supports_streaming=True)
        try:
            await status.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error("Send error: " + str(e))
    finally:
        if os.path.exists(fpath):
            os.remove(fpath)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_lang, pattern="^lang_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_format, pattern="^format_"))
    app.add_handler(CallbackQueryHandler(handle_quality, pattern="^q_"))
    app.add_handler(CallbackQueryHandler(handle_format, pattern="^cancel$"))
    print("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
