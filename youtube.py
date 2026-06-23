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
        "start": "Salom! YouTube havolasini yuboring.",
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
        "start": "Привет! Отправьте ссылку на YouTube.",
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
        "start": "Hello! Send a YouTube link.",
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
    await update.message.reply_text("Tilni tanlang / Выберите язык / Choose language:", reply_markup=InlineKeyboardMarkup(keyboard))

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
    title =
