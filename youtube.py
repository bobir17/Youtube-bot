import os
import re
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
MAX_FILE_SIZE_MB = 49

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YDL_BASE = {
    "quiet": True,
    "no_warnings": True,
    "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
}

def is_youtube_url(url):
    return any(d in url for d in ["youtube.com", "youtu.be", "m.youtube.com"])

def clean_url(url):
    url = url.strip()
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[1].split("?")[0].split("&")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    if "youtube.com/watch" in url:
        m = re.search(r'v=([^&]+)', url)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"
    return url

def get_video_info(url):
    try:
        with yt_dlp.YoutubeDL(dict(YDL_BASE)) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.error(f"Info error: {e}")
        return None

def format_duration(s):
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def _do_download(url, ydl_opts):
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
        logger.error(f"Download error: {e}")
    return None

async def start(update: Update, context):
    await update.message.reply_text(
        "👋 Salom! YouTube havolasini yuboring.\n\n"
        "🎥 Video (MP4) yoki 🎵 Audio yuklash mumkin.\n"
        "⚠️ 49MB gacha fayllar yuboriladi."
    )

async def handle_url(update: Update, context):
    msg_text = update.message.text or update.message.caption or ""
    urls = re.findall(r'https?://[^\s]+', msg_text)
    if not urls:
        await update.message.reply_text("❌ Havola topilmadi. YouTube havolasini yuboring.")
        return
    url = clean_url(urls[0])
    if not is_youtube_url(url):
        await update.message.reply_text("❌ Bu YouTube havolasi emas.")
        return
    msg = await update.message.reply_text("⏳ Ma'lumot olinmoqda...")
    info = get_video_info(url)
    if not info:
        await msg.edit_text("❌ Video topilmadi yoki yuklab bo'lmadi.")
        return
    context.user_data["url"] = url
    context.user_data["title"] = info.get("title", "Video")
    title = info.get("title", "Noma'lum")
    duration = info.get("duration", 0)
    uploader = info.get("uploader", "Noma'lum")
    keyboard = [
        [InlineKeyboardButton("🎥 Video (MP4)", callback_data="format_video"),
         InlineKeyboardButton("🎵 Audio", callback_data="format_audio")],
        [InlineKeyboardButton("❌ Bekor", callback_data="cancel")]
    ]
    await msg.edit_text(
        f"📹 *{title[:60]}*\n👤 {uploader}\n⏱ {format_duration(duration)}\n\nFormat tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_format(update: Update, context):
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
        await download_and_send(query, context, url, "audio")
    else:
        keyboard = [
            [InlineKeyboardButton("📱 360p", callback_data="q_360")],
            [InlineKeyboardButton("💻 720p HD", callback_data="q_720")],
            [InlineKeyboardButton("❌ Bekor", callback_data="cancel")]
        ]
        await query.message.edit_text("🎥 Sifat tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_quality(update: Update, context):
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
    await download_and_send(query, context, url, "video", q)

async def download_and_send(query, context, url,
