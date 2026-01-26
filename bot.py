import logging
import time
import html
import threading
import os
import shutil
import json
import uuid
from urllib.parse import urlparse

import telebot
import yt_dlp
import requests
import yt_dlp
import requests
import speech_recognition as sr
from pydub import AudioSegment
import re

from config import Config
from services.downloader import download_video
from services.search_service import search_music
from services.yoshlar import Yoshlar
from utils.helpers import TimedCache, TempFileManager, validate_url
from utils import muznavo, muzofond
from utils.messages import get_text, save_user_language

# Ensure logs directory exists
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'bot.log')),
        logging.StreamHandler()
    ]
)

# AudD API Token (Get one from https://dashboard.audd.io/)
AUDD_API_TOKEN = Config.AUDD_API_TOKEN


TOKEN = Config.TOKEN
if not TOKEN:
    raise ValueError("Bot TOKEN topilmadi! .env faylini yarating va TELEGRAM_BOT_TOKEN ni kiriting.")

bot = telebot.TeleBot(TOKEN)

try:
    BOT_USERNAME = bot.get_me().username
except Exception as e:
    print(f"Error getting bot info: {e}")
    BOT_USERNAME = "universal_media_uz_bot"


FAVORITES_FILE = "favorites.json"
LANGUAGES_FILE = "user_languages.json"




# TEXTS removed

# Store user links temporarily
user_links = {}
# Store current titles for saving
user_current_titles = {}
# Store search results temporarily
user_search_results = {}
# Store current search page
user_search_page = {}
# Store search type (music/video)
user_search_type = {}

# Rate Limiting
user_last_message_time = {}

def check_rate_limit(chat_id):
    current_time = time.time()
    last_time = user_last_message_time.get(chat_id, 0)
    
    # Limit: 1 message per second
    if current_time - last_time < 1.0:
        return False
        
    user_last_message_time[chat_id] = current_time
    return True


# Store recognized songs for download (TimedCache for memory safety)
user_recognized_songs = TimedCache(ttl_seconds=3600)
# Store user user (target for stories)


def load_user_favorites(chat_id):
    if not os.path.exists(FAVORITES_FILE):
        return []
    try:
        with open(FAVORITES_FILE, 'r') as f:
            data = json.load(f)
            return data.get(str(chat_id), [])
    except:
        return []


# User language functions moved to utils/messages.py


# In top_music handler
@bot.message_handler(commands=['top'])
def top_music(msg):
    chat_id = msg.chat.id
    
    # Check arguments
    parts = msg.text.split(maxsplit=1)
    if len(parts) > 1:
        query = parts[1]
        msg_searching = bot.send_message(chat_id, get_text(chat_id, 'search_searching', {'query': query}))
        
        results = search_music(query, limit=30)
        
        if not results:
            bot.delete_message(chat_id, msg_searching.message_id)
            bot.send_message(chat_id, get_text(chat_id, 'search_not_found'))
            return

        user_search_results[chat_id] = results
        user_search_type[chat_id] = 'music'
        send_search_page(chat_id, results, 0, delete_msg_id=msg_searching.message_id)
    else:
        # Show Category Menu
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_uz'), callback_data="top_cat_uz"),
            telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_world'), callback_data="top_cat_world"),
            telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_trend'), callback_data="top_cat_trend"),
            telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_new'), callback_data="top_cat_new"),
            telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_bass'), callback_data="top_cat_bass"),
            telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_close'), callback_data="page_close")
        )
        bot.send_message(chat_id, get_text(chat_id, 'top_menu_text'), reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("top_cat_"))
def handle_top_category(call):
    chat_id = call.message.chat.id
    category = call.data.split("_")[2]
    
    # Use Muznavo for Top Charts
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
        
    msg_loading = bot.send_message(chat_id, get_text(chat_id, 'search_top_loading'))
    
    # Map categories to Muzofond keys
    # 'trend' -> world/popular (default)
    # 'uz' -> uzbek
    # 'new' -> new
    
    muz_cat = 'trend'
    if category == 'uz': muz_cat = 'uzbek'
    elif category == 'world': muz_cat = 'world'
    elif category == 'new': muz_cat = 'new'
    
    # Use Muzofond for Top
    results = muzofond.get_top_songs(muz_cat, limit=30)
    
    # Fallback to Muznavo if Muzofond empty
    if not results:
        results = muznavo.get_top_songs(muz_cat, limit=30)

    # Fallback to YouTube if both fail
    if not results:
        query_map = {
            'uz': "top uzbek music hits 2025",
            'world': "top global hits 2025 music",
            'trend': "tiktok trending songs 2025",
            'new': "new music releases 2025",
            'bass': "car music bass boosted 2025"
        }
        query = query_map.get(category, "top music 2025")
        results = search_music(query, limit=30)
    
    if not results:
        bot.delete_message(chat_id, msg_loading.message_id)
        bot.send_message(chat_id, get_text(chat_id, 'search_not_found'))
        return

    user_search_results[chat_id] = results
    user_search_type[chat_id] = 'music'
    send_search_page(chat_id, results, 0, delete_msg_id=msg_loading.message_id)

# In handle_message handler (Search)
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def handle_message(msg):
    chat_id = msg.chat.id
    
    if not check_rate_limit(chat_id):
        return

    text = msg.text.strip()
    logging.info(f"Received message from {chat_id}: {text}")
    
    # 0. Check User State


    # 1. Check if it's a URL
    is_url = validate_url(text)

    # 2. If it is a URL, process as before
    if is_url:
        user_links[chat_id] = text
        user_current_titles[chat_id] = "To'g'ridan-to'g'ri havola"
        
        # Check for various platforms
        simple_platforms = [
            "instagram.com", "tiktok.com", 
            "facebook.com", "fb.watch", 
            "pinterest.com", "pin.it",
            "snapchat.com", 
            "likee.video", 
            "threads.net",
            "bigo.tv", "bigo.video",
            "vk.com", "vk.ru",
            "t.me", "telegram.me"
        ]
        
        is_simple_platform = any(platform in text for platform in simple_platforms)

        if is_simple_platform:
            # Try to get info first to show menu (Video/Audio)
            # If it fails, the try/except block below will catch it and fallback to download_video
            download_video(chat_id, text, "best")
            return 

        # Unified URL handling (YouTube + others)
        bot.send_message(chat_id, get_text(chat_id, 'getting_info'))
        
        try:
            # Retry Strategy:
            # 1. Proxy + Cookies
            # 2. Proxy + No Cookies
            # 3. No Proxy + Cookies
            # 4. No Proxy + No Cookies

            # Base options
            base_opts = {
                'quiet': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }

            # Helper to run extraction
            def extract_with_opts(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(text, download=False)

            info = None
            last_error = None

            # Attempt 1: Full Config (Proxy? + Cookies)
            opts1 = base_opts.copy()
            if Config.PROXY: opts1['proxy'] = Config.PROXY
            opts1['cookiefile'] = 'cookies.txt'
            
            try:
                info = extract_with_opts(opts1)
            except Exception as e:
                last_error = e
                logging.warning(f"Attempt 1 failed: {e}")
                
                # Attempt 2: Proxy? + NO Cookies
                opts2 = opts1.copy()
                opts2.pop('cookiefile', None)
                try:
                    info = extract_with_opts(opts2)
                except Exception as e2:
                    last_error = e2
                    logging.warning(f"Attempt 2 failed: {e2}")

                    # Only try 3 & 4 if Proxy was actually used
                    if Config.PROXY:
                         # Attempt 3: NO Proxy + Cookies
                         opts3 = base_opts.copy()
                         opts3['cookiefile'] = 'cookies.txt'
                         # Explicitly remove proxy if it leaked somehow, though base_opts relies on fresh dict
                         try:
                             info = extract_with_opts(opts3)
                         except Exception as e3:
                             last_error = e3
                             logging.warning(f"Attempt 3 failed: {e3}")
                             
                             # Attempt 4: NO Proxy + NO Cookies
                             opts4 = opts3.copy()
                             opts4.pop('cookiefile', None)
                             try:
                                 info = extract_with_opts(opts4)
                             except Exception as e4:
                                 last_error = e4
                                 logging.warning(f"Attempt 4 failed: {e4}")
                                 
                                 # If all failed, raise the last relevant error
                                 # If "Sign in" was in any error, prefer that one? 
                                 # Actually the most restricted one (Proxy+Cookies) might give best error, 
                                 # but usually the last one is "I tried everything and failed".
                                 raise last_error
                    else:
                        raise last_error

            if not info:
                raise Exception("Could not extract info")

            title = info.get('title', 'Media')
            # Try uploader_id (handle) first, then uploader (name)
            uploader = info.get('uploader_id') or info.get('uploader') or 'Unknown'
            # If uploader is still Unknown or weird, handle gracefully
            
            thumbnail = info.get('thumbnail', '')
            extractor = info.get('extractor_key', 'Media')
            description = info.get('description', '')
            
            # Truncate description if too long
            if description and len(description) > 100:
                description = description[:100] + "..."
            elif not description:
                    description = title

            user_current_titles[chat_id] = title
            
            # Match Image 1 UI
            # Caption: Title + "Yuklab olish formatlari ↓"
            # Buttons: [Musiqani aniqlash], [MP3], [Guruhga qo'shish]
            
            kb = telebot.types.InlineKeyboardMarkup(row_width=2)
            
            # Row 1: Video | MP3
            btn_video = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_video'), callback_data="fmt_video")
            btn_mp3 = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_audio'), callback_data="mp3")
            kb.row(btn_video, btn_mp3)

            # Row 2: Musiqani aniqlash
            btn_find = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_find_music'), callback_data="find_music")
            kb.row(btn_find)

            # Row 3: Add Group
            btn_group = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url=f"https://t.me/{BOT_USERNAME}?startgroup=new")
            kb.row(btn_group)
            kb.row(telebot.types.InlineKeyboardButton("❌", callback_data="page_close"))
            
            # Caption
            caption_text = get_text(chat_id, 'video_caption', {'title': title})
            download_text = get_text(chat_id, 'download_formats')
            full_caption = f"{caption_text}\n\n{download_text}"
            
            if thumbnail:
                bot.send_photo(chat_id, thumbnail, caption=full_caption, reply_markup=kb, parse_mode="HTML")
            else:
                bot.send_message(chat_id, full_caption, reply_markup=kb, parse_mode="HTML")
                    
        except Exception as e:
            # Strip ANSI codes from error
            # Strip ANSI codes from error (Robust)
            error_message = str(e)
            ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
            error_message = ansi_escape.sub('', error_message)
            
            # Additional cleanup for common yt-dlp colors/tags
            error_message = error_message.replace('[0;31m', '').replace('[0m', '').replace('[0;32m', '').replace('[0;33m', '')
            error_message = error_message.replace('ERROR:', '').strip()
            
            logging.error(f"Search Error (Final): {error_message}")

            # Smart Quote check for "you're" vs "you’re"
            if "Sign in to confirm" in error_message and "bot" in error_message:
                bot.send_message(chat_id, "⚠️ <b>YouTube Xatoligi:</b>\nBot YouTube tomonidan bloklandi (Cookie eskirgan).\nAdmin bilan bog'laning.", parse_mode="HTML")
            elif "403" in error_message or "Forbidden" in error_message:
                 bot.send_message(chat_id, "⚠️ <b>Guruh/Kanal Xatoligi (403):</b>\nBot IP manzili bloklangan ёки прокси ишламаяпти.\n(YouTube/TikTok serveri ruxsat bermadi).", parse_mode="HTML")
            elif "Handshake status" in error_message or "EOF" in error_message or "Connection reset" in error_message or "timed out" in error_message.lower():
                 bot.send_message(chat_id, "⚠️ <b>Ulanish Xatoligi:</b>\nServer bilan ulanishda xatolik yuz berdi (SSL/Handshake). \nIltimos, birozdan so'ng qayta urinib ko'ring.", parse_mode="HTML")
            else:
                bot.send_message(chat_id, get_text(chat_id, 'error_general', {'error': error_message}))
            
            # Fallback to simple download if extraction fails
            # download_video(chat_id, text, "best") # Caution: loop? No, handled inside.
        return

    # 3. If NOT a URL, treat as Search Query
    msg_searching = bot.send_message(chat_id, get_text(chat_id, 'search_music_searching', {'query': text}))
    
    results = search_music(text, limit=30)
    
    if not results:
        bot.delete_message(chat_id, msg_searching.message_id)
        bot.send_message(chat_id, get_text(chat_id, 'nothing_found'))
        return

    # Store results for this user
    user_search_results[chat_id] = results
    user_search_type[chat_id] = 'video'
    send_search_page(chat_id, results, 0, delete_msg_id=msg_searching.message_id)


def save_user_favorite(chat_id, item):
    data = {}
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, 'r') as f:
                data = json.load(f)
        except:
            pass
    
    str_id = str(chat_id)
    if str_id not in data:
        data[str_id] = []
    
    # Check for duplicates
    for fav in data[str_id]:
        if fav['url'] == item['url']:
            return False # Already exists

    data[str_id].append(item)
    
    with open(FAVORITES_FILE, 'w') as f:
        json.dump(data, f)
    return True

def set_bot_commands():
    commands = [
        telebot.types.BotCommand("start", "Botni qayta ishga tushirish"),
        telebot.types.BotCommand("top", "Ommabop qo'shiqlarni qidirish"),
        telebot.types.BotCommand("my", "Saqlangan musiqalar"),
        telebot.types.BotCommand("lang", "Tilni o'zgartirish"),
        telebot.types.BotCommand("test", "Bot holatini tekshirish")
    ]
    bot.set_my_commands(commands)



@bot.message_handler(commands=['my'])
def my_favorites(msg):
    chat_id = msg.chat.id
    favs = load_user_favorites(chat_id)
    
    if not favs:
        bot.send_message(chat_id, get_text(chat_id, 'no_favorites'))
        return

    text = get_text(chat_id, 'favorites_header')
    kb = telebot.types.InlineKeyboardMarkup(row_width=5)
    
    buttons = []
    for idx, item in enumerate(favs):
        title = item.get('title', 'Untitled')
        text += f"{idx + 1}. {title}\n"
        buttons.append(telebot.types.InlineKeyboardButton(str(idx + 1), callback_data=f"fav_{idx}"))
    
    kb.add(*buttons)
    bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "save_fav")
def save_current_fav(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)
    title = user_current_titles.get(chat_id, "Saved Media")
    
    if not url:
        bot.answer_callback_query(call.id, get_text(chat_id, 'error_no_link'))
        return
        
    obj = {'url': url, 'title': title}
    saved = save_user_favorite(chat_id, obj)
    
    if saved:
        bot.answer_callback_query(call.id, get_text(chat_id, 'saved'))
        bot.send_message(chat_id, get_text(chat_id, 'saved_msg', {'title': title}))
    else:
        bot.answer_callback_query(call.id, get_text(chat_id, 'already_saved'))

@bot.callback_query_handler(func=lambda call: call.data.startswith("fav_"))
def handle_fav_selection(call):
    chat_id = call.message.chat.id
    try:
        idx = int(call.data.split("_")[1])
        favs = load_user_favorites(chat_id)
        
        if idx >= len(favs):
            bot.answer_callback_query(call.id, get_text(chat_id, 'error_item_not_found'))
            return
            
        item = favs[idx]
        url = item['url']
        title = item['title']
        
        # Set state
        user_links[chat_id] = url
        user_current_titles[chat_id] = title
        
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(
            telebot.types.InlineKeyboardButton("360p", callback_data="360"),
            telebot.types.InlineKeyboardButton("480p", callback_data="480"),
            telebot.types.InlineKeyboardButton("720p", callback_data="720"),
            telebot.types.InlineKeyboardButton("1080p", callback_data="1080"),
            telebot.types.InlineKeyboardButton("MP3", callback_data="mp3")
        )
        # Add Delete option? Or just Back. For now simple.
        bot.send_message(chat_id, get_text(chat_id, 'choose_quality', {'title': title}), reply_markup=kb)
        
    except Exception as e:
        bot.send_message(chat_id, f"Xatolik: {e}")

@bot.message_handler(commands=['lang'])
def change_language(msg):
    chat_id = msg.chat.id
    text = get_text(chat_id, 'lang_choose')
    
    # Check current lang to mark checkmark? 
    # Current design just shows buttons
    
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    b_uz = telebot.types.InlineKeyboardButton("O'zbekcha 🇺🇿", callback_data="lang_uz")
    b_cyrl = telebot.types.InlineKeyboardButton("Ўзбекча 🇺🇿", callback_data="lang_uz_cyrl")
    b_ru = telebot.types.InlineKeyboardButton("Русский 🇷🇺", callback_data="lang_ru")
    b_en = telebot.types.InlineKeyboardButton("English 🇺🇸", callback_data="lang_en")
    b_cancel = telebot.types.InlineKeyboardButton("Bekor qilish 🚫", callback_data="page_close")

    # Add checkmark logic visually if needed, but for now standard buttons
    curr = load_user_language(chat_id)
    if curr == 'uz': b_uz.text = "✅ " + b_uz.text
    elif curr == 'uz_cyrl': b_cyrl.text = "✅ " + b_cyrl.text
    elif curr == 'ru': b_ru.text = "✅ " + b_ru.text
    elif curr == 'en': b_en.text = "✅ " + b_en.text

    kb.add(b_uz, b_cyrl, b_ru, b_en)
    kb.row(b_cancel)
    
    bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def handle_language_selection(call):
    chat_id = call.message.chat.id
    lang_code = call.data.split("_", 1)[1] # lang_uz -> uz, lang_uz_cyrl -> uz_cyrl
    
    save_user_language(chat_id, lang_code)
    
    # Update text
    msg_text = ""
    if lang_code == 'uz': msg_text = "✅ Til o'zgartirildi: O'zbekcha 🇺🇿"
    elif lang_code == 'uz_cyrl': msg_text = "✅ Тил ўзгартирилди: Ўзбекча 🇺🇿"
    elif lang_code == 'ru': msg_text = "✅ Язык изменен: Русский 🇷🇺"
    elif lang_code == 'en': msg_text = "✅ Language changed: English 🇺🇸"
    
    bot.delete_message(chat_id, call.message.message_id)
    bot.send_message(chat_id, msg_text)



@bot.message_handler(commands=['test'])
def test_bot(msg):
    chat_id = msg.chat.id
    bot.send_message(chat_id, "✅ Bot ishlamoqda!")
    
    # FFmpeg test
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        bot.send_message(chat_id, f"FFmpeg versiyasi: {result.stdout.split()[2]}")
    except Exception as e:
        bot.send_message(chat_id, f"❌ FFmpeg topilmadi!\nXatolik: {e}")

@bot.message_handler(commands=['start'])
def start(msg):
    chat_id = msg.chat.id
    
    # InlineKeyboardMarkup matches user screenshot
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    
    # 1. Musiqani aniqlash
    # Use existing text key 'btn_find_music' -> 'Musiqani aniqlash 🔎'
    btn_find = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_find_music'), callback_data="find_music")
    
    # 2. MP3
    # Use existing text key 'btn_audio' -> '🎧 MP3'. 
    # Action: Show Top Music Menu (equivalent to /top command)
    btn_mp3 = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_audio'), callback_data="top_menu")
    
    # 3. Guruhga qo'shish
    # Use 'btn_add_group' -> "➕ Guruhga qo'shish ⤴️"
    # URL: https://t.me/universal_media_uz_bot?startgroup=true (or new)
    btn_group = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url=f"https://t.me/{BOT_USERNAME}?startgroup=new")

    markup.add(btn_find, btn_mp3, btn_group)
    
    bot.send_message(chat_id, get_text(chat_id, 'start_welcome'), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "top_menu")
def show_top_menu_callback(call):
    chat_id = call.message.chat.id
    # Re-use logic from /top command (no args)
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_uz'), callback_data="top_cat_uz"),
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_world'), callback_data="top_cat_world"),
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_trend'), callback_data="top_cat_trend"),
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_new'), callback_data="top_cat_new"),
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'cat_bass'), callback_data="top_cat_bass"),
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_close'), callback_data="page_close")
    )
    
    # Try to edit current message if possible, or send new one
    try:
        bot.edit_message_text(get_text(chat_id, 'top_menu_text'), chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        bot.send_message(chat_id, get_text(chat_id, 'top_menu_text'), reply_markup=kb, parse_mode="HTML")
    
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "top_cat_new")
def handle_top_new(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id, "🔄 Hozirgi yangi qo'shiqlar yuklanmoqda...")
    
    try:
        results = Yoshlar.get_new_songs()
        if results:
            user_search_results[chat_id] = results
            user_search_type[chat_id] = 'video' # Treat as video/song
            send_search_page(chat_id, results, 0)
        else:
            bot.send_message(chat_id, "⚠️ Yangi qo'shiqlar topilmadi.")
    except Exception as e:
         bot.send_message(chat_id, f"Xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "top_cat_trend")
def handle_top_trend(call):
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id, "🔄 Trenddagi qo'shiqlar yuklanmoqda...")
    
    try:
        results = Yoshlar.get_trending_songs()
        if results:
            user_search_results[chat_id] = results
            user_search_type[chat_id] = 'video'
            send_search_page(chat_id, results, 0)
        else:
            bot.send_message(chat_id, "⚠️ Trenddagi qo'shiqlar topilmadi.")
    except Exception as e:
         bot.send_message(chat_id, f"Xatolik: {e}")







def search_music(query, limit=5, skip_muznavo=False):
    logging.info(f"Starting search_music for query: {query} (Skip Muznavo: {skip_muznavo})")
    # Normalize query
    query = query.replace("‘", "'").replace("’", "'").replace("`", "'")
    
    # 0. Try Yoshlar.com FIRST (User Request: "take from here")
    try:
        results = Yoshlar.search_music(query)
        if results:
            return results
    except Exception as e:
        logging.error(f"Yoshlar search error: {e}")

    # 1. Try Muzofond SECOND (Fallback)
    if not skip_muznavo:
        try:
            results = muzofond.search_songs(query, limit=limit)
            if results:
                return results
        except Exception as e:
            logging.error(f"Muzofond search error: {e}")

    # 1. Try Muznavo SECOND (Fallback)
    if not skip_muznavo:
        try:
            results = muznavo.search_songs(query, limit=limit)
            if results:
                return results
        except Exception as e:
            logging.error(f"Muznavo search error: {e}")
        
    results = []

    # 1. Try SoundCloud first (WITHOUT Cookies usually works better for public search)
    ydl_opts_sc = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'extract_flat': True,
        # 'cookiefile': 'cookies.txt',  # SoundCloud usually works better without generic cookies
        'check_certificate': False,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    logging.info("Searching SoundCloud...")
    results = []
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_sc) as ydl:
            # scsearch
            info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
            results = info.get('entries', [])
    except Exception as e:
        logging.error(f"SoundCloud search error: {e}")
        # print(f"SoundCloud search error: {e}") # Debug

    
    if results:
        return results
        
    # 2. YouTube Fallback Removed
    # return results
        


    return results



def send_search_page(chat_id, results, page, delete_msg_id=None):
    items_per_page = 10
    total_items = len(results)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    
    current_items = results[start_idx:end_idx]
    
    # Metadata for header
    first_item = current_items[0] if current_items else {}
    header = get_text(chat_id, 'results_title', {'page': page + 1, 'total': total_pages})
    
    response_text = header
    
    kb = telebot.types.InlineKeyboardMarkup(row_width=5)
    
    buttons = []
    for idx, entry in enumerate(current_items):
        abs_idx = start_idx + idx
        title = entry.get('title', 'No Title')
        duration = entry.get('duration_string', '')
        if not duration and 'duration' in entry:
             try:
                 dur_val = int(entry['duration'])
                 m, s = divmod(dur_val, 60)
                 duration = f"{int(m)}:{int(s):02d}"
             except:
                 duration = ""
        
        response_text += f"{abs_idx + 1}. {title} {duration}\n"
        buttons.append(telebot.types.InlineKeyboardButton(str(abs_idx + 1), callback_data=f"select_{abs_idx}"))
    
    # Add page info
    # Add page info (Already in header, but user might want it at bottom too. The 'results_title' includes it. So we remove it from bottom or keep simple.)
    # The 'results_title' format is "🔎 Results ({page}/{total}):\n\n". 
    # Let's REMOVE the redundant footer page info if it's already in header.
    # response_text += f"\n{page + 1}/{total_pages}"

    # Buttons 1-10
    kb.add(*buttons)
    
    # Navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(telebot.types.InlineKeyboardButton("⬅️", callback_data="page_prev"))
    
    nav_buttons.append(telebot.types.InlineKeyboardButton("❌", callback_data="page_close"))
    
    if page < total_pages - 1:
        nav_buttons.append(telebot.types.InlineKeyboardButton("➡️", callback_data="page_next"))
        
    kb.row(*nav_buttons)
    
    # Store current page
    user_search_page[chat_id] = page
    
    # Image handling
    thumbnail = "https://github.com/telegramdesktop/tdesktop/assets/10398327/9d5a7aee-9333-4da2-9b2c-686c1264c125" # Default placeholder
    if first_item.get('thumbnail'):
        thumbnail = first_item['thumbnail']
    
    # Send as Photo
    # Check if we assume it's a fresh send or should we try to edit?
    # Context usually implies new message for search results unless specified
    
    if delete_msg_id:
        try:
            bot.delete_message(chat_id, delete_msg_id)
        except Exception as e:
            print(f"Error deleting searching message: {e}")

    try:
        bot.send_photo(chat_id, thumbnail, caption=response_text, reply_markup=kb)
    except Exception as e:
        print(f"Error sending photo: {e}")
        bot.send_message(chat_id, response_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "lyrics_placeholder")
def lyrics_placeholder(call):
    bot.answer_callback_query(call.id, "So'zlar topilmadi (Bazaga ulanmagan)", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def handle_pagination(call):
    chat_id = call.message.chat.id
    action = call.data.split("_")[1]
    
    if action == "close":
        bot.delete_message(chat_id, call.message.message_id)
        return

    results = user_search_results.get(chat_id)
    if not results:
        bot.answer_callback_query(call.id, get_text(chat_id, 'search_results_expired'))
        return

    current_page = user_search_page.get(chat_id, 0)
    
    if action == "prev":
        new_page = max(0, current_page - 1)
    elif action == "next":
        new_page = current_page + 1
    else:
        return

    if new_page == current_page:
        return

    # Update message
    items_per_page = 10
    total_items = len(results)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    # Limit check
    if new_page >= total_pages:
        return

    start_idx = new_page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    current_items = results[start_idx:end_idx]
    
    header = get_text(chat_id, 'results_title', {'page': new_page + 1, 'total': total_pages})
    first_item = current_items[0] if current_items else {}
    response_text = header
    
    kb = telebot.types.InlineKeyboardMarkup(row_width=5)
    
    buttons = []
    for idx, entry in enumerate(current_items):
        abs_idx = start_idx + idx
        title = entry.get('title', 'No Title')
        duration = entry.get('duration_string', '')
        if not duration and 'duration' in entry:
             m, s = divmod(entry['duration'], 60)
             duration = f"{int(m)}:{int(s):02d}"
        
        response_text += f"{abs_idx + 1}. {title} {duration}\n"
        buttons.append(telebot.types.InlineKeyboardButton(str(abs_idx + 1), callback_data=f"select_{abs_idx}"))
    
    kb.add(*buttons)
    
    nav_buttons = []
    if new_page > 0:
        nav_buttons.append(telebot.types.InlineKeyboardButton("⬅️", callback_data="page_prev"))
    
    nav_buttons.append(telebot.types.InlineKeyboardButton("❌", callback_data="page_close"))
    
    if new_page < total_pages - 1:
        nav_buttons.append(telebot.types.InlineKeyboardButton("➡️", callback_data="page_next"))
        
    kb.row(*nav_buttons)
    
    user_search_page[chat_id] = new_page
    
    # Try to edit media if thumbnail is different, else just caption
    # However, for simplicity and ensuring image matches top result:
    thumbnail = "https://github.com/telegramdesktop/tdesktop/assets/10398327/9d5a7aee-9333-4da2-9b2c-686c1264c125"
    if first_item.get('thumbnail'):
        thumbnail = first_item['thumbnail']
        
    try:
        media = telebot.types.InputMediaPhoto(thumbnail, caption=response_text)
        bot.edit_message_media(media, chat_id, call.message.message_id, reply_markup=kb)
    except Exception as e:
        # Fallback if media edit fails (e.g. same media)
        try:
             bot.edit_message_caption(response_text, chat_id, call.message.message_id, reply_markup=kb)
        except:
             pass

from utils.helpers import TempFileManager, validate_url, check_disk_space, sanitize_filename, compress_video, compress_audio

def download_video(chat_id, url, quality):
    # Muznavo Special Handling
    if 'muznavo.tv' in url and not url.endswith('.mp3'):
        try:
            bot.send_message(chat_id, get_text(chat_id, 'getting_info'))
            resolved_url = muznavo.get_download_url(url, proxy=Config.PROXY)
            if resolved_url:
                url = resolved_url
                logging.info(f"Resolved Muznavo URL to: {url}")
            else:
                logging.warning(f"Could not resolve Muznavo URL: {url}")
                bot.send_message(chat_id, "⚠️ Muznavo havolasini ochib bo'lmadi.\n(Havola eskirgan yoki server ishlamayapti)")
                return
        except Exception as e:
            logging.error(f"Error resolving Muznavo URL: {e}")
            # Strip ANSI codes from error (Robust)
            error_message = str(e)
            ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
            error_message = ansi_escape.sub('', error_message)
            error_message = error_message.replace('[0;31m', '').replace('[0m', '').replace('[0;32m', '').replace('[0;33m', '').strip()
            
            bot.send_message(chat_id, f"⚠️ Xatolik: {error_message}")
            return

    # Disk joyini tekshirish (1.5GB file uchish uchun kamida 3GB bo'sh joy kerak)
    if not check_disk_space(3000):  # 3GB limit (requested 1.5 GB support)
        bot.send_message(chat_id, "⚠️ Server xotirasi to'lib qoldi! (3GB bo'sh joy kerak).")
        return

    status_msg = bot.send_message(chat_id, get_text(chat_id, 'downloading'))
    last_update_time = 0
    
    # Progress hook function
    def progress_hook(d):
        nonlocal last_update_time
        import time
        
        # DEBUG: Print status to console
        # print(f"DEBUG: Hook status: {d.get('status')} - {d.get('_percent_str', '')}")

        if d['status'] == 'downloading':
            current_time = time.time()
            # Update every 3 seconds to avoid Flood Wait
            if current_time - last_update_time > 3:
                percent = ""
                if d.get('total_bytes'):
                    p = d['downloaded_bytes'] / d['total_bytes'] * 100
                    percent = f"{p:.1f}%"
                elif d.get('total_bytes_estimate'):
                    p = d['downloaded_bytes'] / d['total_bytes_estimate'] * 100
                    percent = f"{p:.1f}%"
                
                # Fallback: if no percentage, show size
                if not percent:
                     downloaded_mb = d.get('downloaded_bytes', 0) / (1024 * 1024)
                     percent = f"{downloaded_mb:.1f} MB"
                
                try:
                    bot.edit_message_text(get_text(chat_id, 'downloading_percent', {'percent': percent}), chat_id, status_msg.message_id)
                    last_update_time = current_time
                except Exception as e:
                    # Ignore "Message is not modified" or other minor errors
                    # print(f"Progress update error: {e}")
                    pass
        elif d['status'] == 'finished':
            try:
                bot.edit_message_text(get_text(chat_id, 'processing'), chat_id, status_msg.message_id)
            except:
                pass

    # Generate unique ID for this download
    unique_id = str(uuid.uuid4())
    temp_filename_base = f"download_{unique_id}"
    
    # Use TempFileManager for robust cleanup
    with TempFileManager(cleanup_pattern=f"{temp_filename_base}*") as temp_files:
        try:
            # Explicitly find ffmpeg to avoid "Conversion failed" errors
            ffmpeg_path = shutil.which('ffmpeg')
            common_opts = {
                'ffmpeg_location': ffmpeg_path,
                'quiet': False,
                'verbose': True,
                'progress_hooks': [progress_hook],
                'cookiefile': 'cookies.txt',
                'no_warnings': True,
                'socket_timeout': 60,
                'retries': 10,
                'fragment_retries': 10,
                'file_access_retries': 5,
                'restrictfilenames': True,
                'windowsfilenames': True,
                'trim_file_name': 240,
                'check_certificate': False,
                'http_chunk_size': 10485760,
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                # 'source_address': '0.0.0.0', # Removed to allow IPv6/Default
            }
            
            # Add Proxy if configured
            if Config.PROXY:
                common_opts['proxy'] = Config.PROXY

                # Robust Retry Logic for Downloads (MP3/Video)
                
                # Helper for download attempt
                def download_with_opts(opts):
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(url, download=True)

                download_info = None
                last_error = None
                
                # Define Common Options Copy for mutation
                # MP3 specific
                if quality == "mp3":
                    ydl_opts_base = {
                        **common_opts,
                        'format': 'bestaudio/best',
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'outtmpl': f'{temp_filename_base}.%(ext)s',
                        'writethumbnail': True,
                    }
                else:
                    # Video specific
                    if quality == "best":
                        format_str = 'bestvideo+bestaudio/best'
                    else:
                         format_str = f'bv*[height<={quality}]+ba/b[height<={quality}]/b'

                    ydl_opts_base = {
                        **common_opts,
                        'format': format_str,
                        'outtmpl': f'{temp_filename_base}_%(id)s.%(ext)s', 
                        'writethumbnail': True,
                        'noplaylist': False,
                    }

                # Attempt 1: Full Config (Proxy? + Cookies)
                opts1 = ydl_opts_base.copy()
                if Config.PROXY: opts1['proxy'] = Config.PROXY
                
                try:
                    download_info = download_with_opts(opts1)
                except yt_dlp.utils.DownloadError as e:
                    last_error = e
                    logging.warning(f"Download Attempt 1 failed: {e}")
                    
                    # Attempt 2: Proxy? + NO Cookies
                    opts2 = opts1.copy()
                    opts2.pop('cookiefile', None)
                    try:
                        download_info = download_with_opts(opts2)
                    except yt_dlp.utils.DownloadError as e2:
                        last_error = e2
                        logging.warning(f"Download Attempt 2 failed: {e2}")

                        # Only try 3 & 4 if Proxy was actually used
                        if Config.PROXY:
                             # Attempt 3: NO Proxy + Cookies
                             opts3 = ydl_opts_base.copy()
                             if 'proxy' in opts3: del opts3['proxy'] # Ensure clean
                             try:
                                 download_info = download_with_opts(opts3)
                             except yt_dlp.utils.DownloadError as e3:
                                 last_error = e3
                                 logging.warning(f"Download Attempt 3 failed: {e3}")
                                 
                                 # Attempt 4: NO Proxy + NO Cookies
                                 opts4 = opts3.copy()
                                 opts4.pop('cookiefile', None)
                                 try:
                                     download_info = download_with_opts(opts4)
                                 except yt_dlp.utils.DownloadError as e4:
                                     last_error = e4
                                     logging.warning(f"Download Attempt 4 failed: {e4}")
                                     pass # Will be handled by check below
                        else:
                            pass

                if not download_info:
                    # Failed all attempts
                    if quality == "mp3":
                         bot.edit_message_text(get_text(chat_id, 'download_error'), chat_id, status_msg.message_id)
                         logging.error(f"❌ Audio Download failed (All attempts): {url} for user {chat_id}")
                         return
                    else:
                         # Video failure logic
                         # Since video logic continues below, we should return or skip if failed
                         # But the original code structure nested the video logic differently.
                         # Let's check below.
                         logging.error(f"❌ Video Download failed (All attempts): {url}")
                         bot.send_message(chat_id, get_text(chat_id, 'download_error'))
                         try: bot.delete_message(chat_id, status_msg.message_id)
                         except: pass
                         return

                info = download_info

                if quality == "mp3":
                    # MP3 Post-Processing Logic
                    final_filename = f"{temp_filename_base}.mp3"
                    
                    # Register generated files for cleanup
                    temp_files.add_file(final_filename)
                    
                    # Metadata extraction
                    duration = info.get('duration')
                    title = info.get('title', 'Audio')
                    artist = info.get('artist') or info.get('uploader') or "Universal Bot"
                    
                    # Find thumbnail
                    thumb_path = None
                    possible_exts = ['jpg', 'jpeg', 'png', 'webp']
                    for e in possible_exts:
                        if os.path.exists(f"{temp_filename_base}.{e}"):
                            thumb_path = f"{temp_filename_base}.{e}"
                            temp_files.add_file(thumb_path)
                            break
                    
                    if os.path.exists(final_filename):
                        # Check size
                        # Check sizeA
                        file_size = os.path.getsize(final_filename)
                        if file_size > 49 * 1024 * 1024:
                            size_mb = round(file_size / (1024 * 1024), 2)
                            
                            # Attempt Audio Compression
                            bot.send_message(chat_id, f"⚠️ Audio hajmi katta ({size_mb} MB). Telegram limiti 50MB.\nSiqishga harakat qilinmoqda... ⏳")
                            
                            compressed_audio_path = f"{temp_filename_base}_compressed.mp3"
                            temp_files.add_file(compressed_audio_path)
                            
                            if compress_audio(final_filename, compressed_audio_path, 48, ffmpeg_path):
                                final_filename = compressed_audio_path
                                # Recalculate size to be sure (optional, mostly for debug)
                                new_size = os.path.getsize(final_filename)
                                logging.info(f"Audio compressed successfully: {size_mb}MB -> {new_size/(1024*1024):.2f}MB")
                            else:
                                bot.send_message(chat_id, get_text(chat_id, 'file_too_large', {'size': size_mb}))
                                try:
                                    bot.delete_message(chat_id, status_msg.message_id)
                                except:
                                    pass
                                return

                        with open(final_filename, 'rb') as audio_file:
                            caption_text = get_text(chat_id, 'audio_caption', {'artist': artist, 'title': title})
                            
                            kb = telebot.types.InlineKeyboardMarkup()
                            kb.row(
                                telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_8d'), callback_data="effect_8d"),
                                telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_concert'), callback_data="effect_concert")
                            )
                            kb.row(
                                telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_slowed'), callback_data="effect_slowed"),
                                telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_bass'), callback_data="effect_bass")
                            )
                            kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url=f"https://t.me/{bot.get_me().username}?startgroup=true"))

                            if thumb_path:
                                with open(thumb_path, 'rb') as thumb_file:
                                    bot.send_audio(
                                        chat_id, 
                                        audio_file, 
                                        caption=caption_text,
                                        parse_mode="HTML",
                                        duration=duration,
                                        performer=artist,
                                        title=title,
                                        thumbnail=thumb_file,
                                        reply_markup=kb,
                                        timeout=600
                                    )
                            else:
                                bot.send_audio(
                                    chat_id, 
                                    audio_file, 
                                    caption=caption_text,
                                    parse_mode="HTML",
                                    duration=duration,
                                    performer=artist,
                                    title=title,
                                    reply_markup=kb,
                                    timeout=600
                                )
                            logging.info(f"✅ Downloaded Audio: {title} for user {chat_id}") # LOGGING

                        try:
                            bot.delete_message(chat_id, status_msg.message_id)
                        except:
                            pass
                    else:
                        bot.edit_message_text(get_text(chat_id, 'download_error'), chat_id, status_msg.message_id)
                        logging.error(f"❌ Audio Download failed (No file): {url} for user {chat_id}") # LOGGING
                    
                    return
                # Universal Media Download (Video/Image)
                # Strategy: Files are already downloaded by the robust retry logic above.
                # We now process the downloaded files (Convert to H.264 if needed) to ensure compatibility.
                
                # Extract meta
                title = info.get('title', 'Media')

                
                # 2. Logic: Find ALL Videos and separate Thumbnails from Content Images
                video_files = [] 
                processed_videos = [] # List of (filename, thumb_path/None, duration, width, height)
                standalone_images = []
                
                all_files = os.listdir('.')
                
                # 2a. Categorize files
                candidates_vid = []
                candidates_img = []
                
                for f in all_files:
                    if f.startswith(temp_filename_base):
                        ext = f.split('.')[-1].lower()
                        # Register for cleanup immediately
                        temp_files.add_file(f) 
                        
                        if ext in ['mp4', 'mkv', 'mov', 'webm', 'avi', 'flv']:
                            candidates_vid.append(f)
                        elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                            candidates_img.append(f)

                # 2b. Process Videos (Convert & Attach Thumb)
                import subprocess

                for vid_file in candidates_vid:
                    # Determine expected thumbnail filename (yt-dlp naming convention usually matches base)
                    # e.g. base_id.mp4 -> base_id.jpg
                    base_name = os.path.splitext(vid_file)[0]
                    thumb_candidate = None
                    
                    # Look for matching thumb in candidates_img
                    for img in candidates_img:
                        if os.path.splitext(img)[0] == base_name:
                            thumb_candidate = img
                            break
                    
                    # Conversion
                    converted_filename = f"{base_name}_fixed.mp4"
                    temp_files.add_file(converted_filename)

                    status_msg_2 = None
                    try:
                        # Only denote "converting" once or if list is short, to avoid spam? 
                        # Let's just log it or send one message if it's the first one
                        if len(processed_videos) == 0:
                             status_msg_2 = bot.send_message(chat_id, "⚙️ Videolar formatlanmoqda... (H.264)")
                    except: pass

                    cmd = [
                        ffmpeg_path,
                        '-i', vid_file,
                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '26', 
                        '-c:a', 'aac', '-b:a', '128k',
                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                        '-y', converted_filename
                    ]
                    
                    final_vid_path = vid_file # Default to source
                    
                    try:
                        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
                        if process.returncode == 0 and os.path.exists(converted_filename):
                            final_vid_path = converted_filename
                        else:
                            logging.error(f"FFmpeg failed for {vid_file}: {process.stderr}")
                    except Exception as e:
                        logging.error(f"FFmpeg internal error: {e}")

                    # Add to processed list
                    processed_videos.append({
                        'file': final_vid_path,
                        'thumb': thumb_candidate
                    })
                    
                    # Clean up stats msg
                    if status_msg_2:
                        try:
                            bot.delete_message(chat_id, status_msg_2.message_id)
                        except: pass

                # 2c. Identify Standalone Images (Images that were NOT used as thumbnails)
                # Note: If an image matched a video, we assume it's a thumb. 
                # If an image didn't match any video, it's standalone content.
                
                # Get set of used thumbs
                used_thumbs = {pv['thumb'] for pv in processed_videos if pv['thumb']}
                
                for img in candidates_img:
                    if img not in used_thumbs:
                        standalone_images.append(img)


                # 3. Construct Final Media Group
                media_group = []
                
                caption_text = get_text(chat_id, 'video_caption', {'title': title})
                download_text = get_text(chat_id, 'download_formats')
                caption = f"{caption_text}\n\n{download_text}"

                # Add Videos
                for pv in processed_videos:
                    try:
                        f_path = pv['file']
                        t_path = pv['thumb']
                        
                        # Resize if too large (Check for Media Group as well)
                        try:
                            f_size = os.path.getsize(f_path)
                            if f_size > 49 * 1024 * 1024:
                                s_mb = f_size / (1024 * 1024)
                                bot.send_message(chat_id, f"⚠️ Media guruhidagi video katta ({s_mb:.1f} MB). Siqilmoqda...")
                                
                                c_path = f_path.rsplit('.', 1)[0] + "_c.mp4"
                                temp_files.add_file(c_path)
                                
                                if compress_video(f_path, c_path, 48, ffmpeg_path):
                                    f_path = c_path
                                    pv['file'] = c_path # Update reference
                                else:
                                    bot.send_message(chat_id, f"⚠️ {s_mb:.1f} MB hajmli video siqilmadi va guruhdan olib tashlandi.")
                                    continue # Skip this video
                        except Exception as e:
                            logging.error(f"Error checking/compressing group video: {e}")

                        
                        # Open file handles (Note: telebot opens them, but we need 'open' objects)
                        # We won't pre-open here to avoid exhausting handles, we do it in InputMedia construction
                        
                        if t_path:
                            media_group.append(telebot.types.InputMediaVideo(
                                open(f_path, 'rb'), 
                                thumbnail=open(t_path, 'rb'),
                                caption=caption if len(media_group)==0 else "", # Caption only on first item
                                parse_mode="HTML",
                                supports_streaming=True
                            ))
                        else:
                             media_group.append(telebot.types.InputMediaVideo(
                                open(f_path, 'rb'), 
                                caption=caption if len(media_group)==0 else "",
                                parse_mode="HTML",
                                supports_streaming=True
                            ))
                    except Exception as e:
                        logging.error(f"Error adding video to group: {e}")

                # Add Standalone Images
                for img in standalone_images:
                    try:
                         media_group.append(telebot.types.InputMediaPhoto(
                            open(img, 'rb'), 
                            caption=caption if len(media_group)==0 else "",
                            parse_mode="HTML"
                        ))
                    except Exception as e:
                         logging.error(f"Error adding image to group: {e}")


                # 4. SEND logic
                if not media_group:
                     bot.send_message(chat_id, get_text(chat_id, 'download_error'))
                     return

                # Match Image 1 UI
                kb = telebot.types.InlineKeyboardMarkup(row_width=1)
                
                # 1. Musiqani aniqlash
                btn_find = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_find_music'), callback_data="find_music")
                
                # 2. MP3
                btn_mp3 = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_audio'), callback_data="mp3")
                
                # 3. Guruhga qo'shish
                btn_group = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url=f"https://t.me/{bot.get_me().username}?startgroup=new")
                
                kb.add(btn_find, btn_mp3, btn_group)



                # A. Single Video (and no standalone images) -> Send as Video with kb
                if len(media_group) == 1 and len(processed_videos) == 1 and not standalone_images:
                      pv = processed_videos[0]
                     
                      # Check file size (Telegram Bot API limit is 50MB)
                      file_path = pv['file']
                      try:
                          file_size = os.path.getsize(file_path)
                          if file_size > 49 * 1024 * 1024: # 49MB limit for safety
                               # AUTOMATIC COMPRESSION LOGIC
                               size_mb = file_size / (1024 * 1024)
                               
                               # Inform user
                               msg_compress = bot.send_message(chat_id, f"⚠️ Fayl hajmi katta ({size_mb:.1f} MB). Telegram limiti 50MB.\nSiqishga harakat qilinmoqda... ⏳")
                               
                               compressed_path = file_path.rsplit('.', 1)[0] + "_compressed.mp4"
                               temp_files.add_file(compressed_path)
                               
                               # Try to compress to 48MB
                               success = compress_video(file_path, compressed_path, 48, ffmpeg_path)
                               
                               if success:
                                   file_path = compressed_path
                                   # Update pv file path so it sends the depressed one
                                   pv['file'] = compressed_path 
                                   
                                   try:
                                       bot.edit_message_text("✅ Siqish muvaffaqiyatli yakunlandi! Yuborilmoqda...", chat_id, msg_compress.message_id)
                                   except: pass
                               else:
                                   logging.warning(f"File too large and compression failed: {file_size} bytes - {title}")
                                   
                                   # Fallback Strategy: Try lower quality
                                   new_quality = None
                                   if quality == 'best':
                                       new_quality = '720'
                                   elif quality == '1080':
                                       new_quality = '720'
                                   elif quality == '720':
                                       new_quality = '480'
                                   elif quality == '480':
                                       new_quality = '360'
                                   
                                   if new_quality:
                                        bot.send_message(chat_id, get_text(chat_id, 'retry_low_quality', {'quality': new_quality}))
                                        try:
                                            bot.delete_message(chat_id, status_msg.message_id)
                                        except:
                                            pass
                                        
                                        # Recursively call with lower quality
                                        download_video(chat_id, url, new_quality)
                                        return
                                   else:
                                        # 1.5GB Override: If compression failed but user wants 1.5GB support
                                        # Try to send anyway if < 1.5GB
                                        if file_size < 1536 * 1024 * 1024:
                                             bot.send_message(chat_id, "⚠️ Siqish muvaffaqiyatsiz, lekin fayl 1.5GB dan kichik. Yuborishga urinib ko'ramiz (Local Server 2GB gacha qo'llaydi)...")
                                             # Fall through to send logic
                                             # Update pv['file'] to original if not changed
                                             pass 
                                        else:
                                             bot.send_message(chat_id, get_text(chat_id, 'file_too_large', {'size': f"{size_mb:.1f}"}))
                                             return
                      except Exception as e:
                          logging.error(f"Error checking file size: {e}")

                      try:
                          with open(pv['file'], 'rb') as v:
                              if pv['thumb'] and os.path.exists(pv['thumb']):
                                  with open(pv['thumb'], 'rb') as t:
                                      bot.send_video(chat_id, v, thumbnail=t, caption=caption, parse_mode="HTML", reply_markup=kb, supports_streaming=True, timeout=300)
                              else:
                                  bot.send_video(chat_id, v, caption=caption, parse_mode="HTML", reply_markup=kb, supports_streaming=True, timeout=300)
                          logging.info(f"✅ Downloaded Single Video: {title}")
                      except Exception as e:
                          logging.error(f"Send Single Video Failed: {e}")
                          bot.send_message(chat_id, f"❌ Video yuborishda xatolik: {e}")
                
                # B. Single Photo (and no videos) -> Send as Photo with kb
                elif len(media_group) == 1 and len(standalone_images) == 1 and not processed_videos:
                     img = standalone_images[0]
                     try:
                         with open(img, 'rb') as p:
                             bot.send_photo(chat_id, p, caption=caption, parse_mode="HTML", reply_markup=kb)
                     except Exception as e:
                         logging.error(f"Send Single Photo Failed: {e}")

                # C. Mixed / Multiple -> Send Media Group (Telegram limit is 10)
                else:
                    # Truncate to 10
                    media_group = media_group[:10]
                    try:
                        bot.send_media_group(chat_id, media_group)
                        # Media Group cannot have Inline Keyboard attached to the group itself. 
                        # We send a separate message for the keyboard/caption if needed, or attach caption to first item (done above).
                        # Send KB separately
                        bot.send_message(chat_id, "Downloaded Media ☝️", reply_markup=kb)
                        logging.info(f"✅ Downloaded Group: {title}")
                    except Exception as e:
                        logging.error(f"Send Media Group Failed: {e}")
                        bot.send_message(chat_id, "❌ Media guruhini yuborishda xatolik.")


                try:
                    bot.delete_message(chat_id, status_msg.message_id)
                except Exception as e:
                    logging.warning(f"Could not delete status message {status_msg.message_id}: {e}")

        except yt_dlp.utils.DownloadError as e:
            error_id = str(uuid.uuid4())[:8]
            logging.error(f"❌ yt-dlp Download Error (ID: {error_id}): {e}", exc_info=True)
            
            # User-friendly error mapping
            err_str = str(e).lower()
            user_msg = ""
            
            if "sign in" in err_str:
                user_msg = "⚠️ Bu video yosh cheklovi yoki hisob talab qiladi. Hozircha yuklab bo'lmaydi."
            elif "video unavailable" in err_str:
                 user_msg = "⚠️ Video mavjud emas yoki o'chirilgan."
            elif "too many requests" in err_str:
                user_msg = "⚠️ YouTube serverlarida yuklama ko'p. Iltimos, keyinroq urining."
            elif "copyright" in err_str:
                 user_msg = "⚠️ Bu video mualliflik huquqi tufayli bloklangan."
            else:
                 user_msg = f"⚠️ Yuklashda xatolik yuz berdi. (Error ID: {error_id})"

            try:
                bot.edit_message_text(user_msg, chat_id, status_msg.message_id)
            except:
                bot.send_message(chat_id, user_msg)

        except Exception as e:
            error_id = str(uuid.uuid4())[:8]
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            error_message = ansi_escape.sub('', str(e))
            
            logging.error(f"❌ General Download Exception (ID: {error_id}): {e} - URL: {url}", exc_info=True)
            
            user_msg = get_text(chat_id, 'error_general', {'error': f"Internal Error {error_id}"})
            try:
                bot.edit_message_text(user_msg, chat_id, status_msg.message_id)
            except:
                bot.send_message(chat_id, user_msg)


@bot.callback_query_handler(func=lambda call: call.data.startswith("select_"))
def handle_search_selection(call):
    chat_id = call.message.chat.id
    logging.info(f"Selection callback received: {call.data} from {chat_id}")
    try:
        selection_index = int(call.data.split("_")[1])
        results = user_search_results.get(chat_id)
        
        if not results or selection_index >= len(results):
            logging.warning(f"Results expired or invalid index for {chat_id}")
            bot.answer_callback_query(call.id, get_text(chat_id, 'search_results_expired'))
            return

        selected_video = results[selection_index]
        video_url = selected_video.get('url') or selected_video.get('webpage_url')
        title = selected_video.get('title', 'Video')
        thumbnail = selected_video.get('thumbnail', '')
        
         
        # Custom handling for Yoshlar.com (New Source)
        if selected_video.get('source') == 'yoshlar':
             from services.yoshlar import Yoshlar
             try:
                 bot.answer_callback_query(call.id, get_text(chat_id, 'getting_info'))
                 final_url = Yoshlar.get_download_url(video_url)
                 if final_url:
                     video_url = final_url
                 else:
                     bot.send_message(chat_id, "Yoshlar.com saytidan yuklab bo'lmadi.")
                     return
             except Exception as e:
                 logging.error(f"Yoshlar resolution error: {e}")
                 bot.send_message(chat_id, f"Xatolik: {e}")
                 return

        # Custom handling for Muzofond
        elif selected_video.get('source') == 'muzofond':
             # URL is already direct, but we verify it or format it
             # It worked in tests without headers
             pass 

        # Custom handling for Muznavo
        elif selected_video.get('source') == 'muznavo':
             try:
                 bot.answer_callback_query(call.id, get_text(chat_id, 'getting_info'))
                 final_url = muznavo.get_download_url(video_url)
                 if final_url:
                     video_url = final_url
                 else:
                     logging.warning(f"Muznavo resolution failed for {title}. Fallback to YouTube.")
                     # Fallback to YouTube Search
                     yt_results = search_music(title, limit=1, skip_muznavo=True)
                     if yt_results and len(yt_results) > 0:
                         fallback = yt_results[0]
                         video_url = fallback.get('url') or fallback.get('webpage_url')
                         title = fallback.get('title', title)
                         thumbnail = fallback.get('thumbnail', thumbnail)
                         logging.info(f"Fallback successful: {title} ({video_url})")
                     else:
                         bot.send_message(chat_id, "Muznavo linkini olib bo'lmadi va muqobil topilmadi.")
                         return
             except Exception as e:
                 logging.error(f"Muznavo resolution error: {e}")
                 bot.send_message(chat_id, "Xatolik yuz berdi.")
                 return
        
        # Save state
        
        # Save state
        user_links[chat_id] = video_url
        user_current_titles[chat_id] = title
        
        # New UI Logic: Show Menu (Video/MP3/Save/Close)
        
        # Match Image 1 UI
        # Match Image 1 UI
        kb = telebot.types.InlineKeyboardMarkup(row_width=2)
        
        # Row 1: Video | MP3
        btn_video = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_video'), callback_data="fmt_video")
        btn_mp3 = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_audio'), callback_data="mp3")
        kb.row(btn_video, btn_mp3)

        # Row 2: Musiqani aniqlash
        btn_find = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_find_music'), callback_data="find_music")
        kb.row(btn_find)

        # Row 3: Add Group
        btn_group = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url=f"https://t.me/{bot.get_me().username}?startgroup=new")
        kb.row(btn_group)
        kb.row(telebot.types.InlineKeyboardButton("❌", callback_data="page_close"))
        
        # Prepare display title with Artist if available
        display_title = title
        artist = selected_video.get('artist')
        if artist and artist != "Muznavo" and artist != "Unknown":
            # Avoid duplication if title already contains artist
            if artist.lower() not in title.lower():
                display_title = f"{artist} - {title}"
        
        caption = get_text(chat_id, 'video_caption', {'title': display_title})
        
        try:
            if thumbnail:
                media = telebot.types.InputMediaPhoto(thumbnail, caption=caption, parse_mode="HTML")
                bot.edit_message_media(media, chat_id, call.message.message_id, reply_markup=kb)
            else:
                 bot.edit_message_caption(caption, chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Media edit failed: {e}. Trying caption edit...")
             # Retry with just caption if media edit fails
            try:
                bot.edit_message_caption(caption, chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
            except Exception as e2:
                logging.error(f"Caption edit failed: {e2}. Trying text edit...")
                try:
                    # Final fallback: If it was a text message, edit the text
                    bot.edit_message_text(caption, chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
                except Exception as e3:
                    logging.error(f"All edit attempts failed: {e3}")
                    pass

        bot.answer_callback_query(call.id)

    except Exception as e:
        # Strip ANSI codes from error (Robust)
        error_message = str(e)
        ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
        error_message = ansi_escape.sub('', error_message)
        error_message = error_message.replace('[0;31m', '').replace('[0m', '').replace('[0;32m', '').replace('[0;33m', '').strip()

        if "Handshake status" in error_message or "EOF" in error_message or "Connection reset" in error_message or "timed out" in error_message.lower():
             bot.send_message(chat_id, "⚠️ <b>Ulanish Xatoligi:</b>\nServer bilan ulanishda xatolik yuz berdi. \n(Proxy yoki Internet muammosi). Qayta urinib ko'ring.", parse_mode="HTML")
        elif "403" in error_message or "Forbidden" in error_message:
             bot.send_message(chat_id, "⚠️ <b>Ruxsat Xatoligi (403):</b>\nBot IP manzili bloklangan bo'lishi mumkin.", parse_mode="HTML")
        else:
             bot.send_message(chat_id, f"Xatolik: {error_message}")

@bot.callback_query_handler(func=lambda call: call.data == "fmt_video")
def show_video_qualities(call):
    chat_id = call.message.chat.id
    kb = telebot.types.InlineKeyboardMarkup()
    
    # Quality buttons
    kb.row(
        telebot.types.InlineKeyboardButton("360p", callback_data="360"),
        telebot.types.InlineKeyboardButton("480p", callback_data="480")
    )
    kb.row(
        telebot.types.InlineKeyboardButton("720p", callback_data="720"),
        telebot.types.InlineKeyboardButton("1080p", callback_data="1080")
    )
    kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_back'), callback_data="back_to_main"))
    
    try:
        # Edit caption to show we are in video mode
        # Note: Depending on if it's a photo or message, use edit_message_caption or edit_message_text
        if call.message.content_type == 'photo':
            bot.edit_message_caption(get_text(chat_id, 'video_quality_select'), chat_id, call.message.message_id, reply_markup=kb)
        else:
            bot.edit_message_text(get_text(chat_id, 'video_quality_select'), chat_id, call.message.message_id, reply_markup=kb)
    except Exception as e:
        print(f"Error editing message: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main_menu(call):
    chat_id = call.message.chat.id
    title = user_current_titles.get(chat_id, "Video")
    
    # Match Image 1 UI
    # Match Image 1 UI
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    
    # Row 1: Video | MP3
    btn_video = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_video'), callback_data="fmt_video")
    btn_mp3 = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_audio'), callback_data="mp3")
    kb.row(btn_video, btn_mp3)

    # Row 2: Musiqani aniqlash
    btn_find = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_find_music'), callback_data="find_music")
    kb.row(btn_find)
    
    # Row 3: Add Group
    btn_group = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url=f"https://t.me/{bot.get_me().username}?startgroup=new")
    kb.row(btn_group)
    kb.row(telebot.types.InlineKeyboardButton("❌", callback_data="page_close"))
    
    try:
        # Restore caption
        if call.message.content_type == 'photo':
             bot.edit_message_caption(get_text(chat_id, 'video_caption', {'title': title}), chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        else:
             bot.edit_message_text(get_text(chat_id, 'video_only_caption', {'title': title}), chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        print(f"Error editing message: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ['360', '480', '720', '1080', 'mp3'])
def download(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)
    quality = call.data
    
    if not url:
        bot.send_message(chat_id, get_text(chat_id, 'error_link_expired'))
        return

    # Call the helper function
    download_video(chat_id, url, quality)

@bot.callback_query_handler(func=lambda call: call.data == "find_music")
def handle_find_music(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)
    
    if not url:
        bot.answer_callback_query(call.id, get_text(chat_id, 'error_link_expired'))
        return

    # Inform user
    # bot.answer_callback_query(call.id, get_text(chat_id, 'recognition_processing'))
    # Use send_message for better visibility as processing takes time
    status_msg = bot.send_message(chat_id, get_text(chat_id, 'recognition_processing'))
    
    unique_id = str(uuid.uuid4())
    temp_filename = f"rec_{unique_id}.mp3"
    
    try:
        with TempFileManager(temp_filename) as temp_files:
            # Download Audio from URL
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'rec_{unique_id}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'cookiefile': 'cookies.txt',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
                
            # Recognize
            if os.path.exists(temp_filename):
                music_info = recognize_music(temp_filename)
                
                # Use shared logic or practically copy-paste for robustness
                if music_info and music_info.get('status') == 'success' and music_info.get('result'):
                    result = music_info['result']
                    artist = result.get('artist')
                    title = result.get('title')
                    links = result.get('song_link')
                    
                    spotify_link = None
                    if 'spotify' in result and result['spotify']:
                        spotify_link = result['spotify'].get('external_urls', {}).get('spotify')
                    
                    youtube_link = None
                    if 'youtube' in result and result['youtube']:
                         youtube_link = result['youtube'].get('link')
                    
                    response_text = get_text(chat_id, 'music_recognized')
                    response_text += get_text(chat_id, 'music_artist', {'artist': artist})
                    response_text += get_text(chat_id, 'music_title', {'title': title})
                    
                    # Button for DL
                    search_query_formatted = f"{artist} - {title}"
                    dl_callback = ""
                    if len(search_query_formatted.encode('utf-8')) < 60:
                         dl_callback = f"dl|{search_query_formatted}"
                    else:
                         dl_id = str(uuid.uuid4())[:8]
                         user_recognized_songs[dl_id] = search_query_formatted
                         dl_callback = f"dl_id|{dl_id}"
                    
                    kb = telebot.types.InlineKeyboardMarkup()
                    kb.add(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_telegram_search'), callback_data=dl_callback))
                    
                    if spotify_link:
                        kb.add(telebot.types.InlineKeyboardButton("Spotify 💚", url=spotify_link))
                    if youtube_link:
                        kb.add(telebot.types.InlineKeyboardButton("YouTube 📺", url=youtube_link))
                    
                    bot.send_message(chat_id, response_text, parse_mode="HTML", reply_markup=kb)
                else:
                     bot.send_message(chat_id, get_text(chat_id, 'music_not_found'))
            else:
                 bot.send_message(chat_id, "Audio yuklashda xatolik.")
                 
        bot.delete_message(chat_id, status_msg.message_id)

    except Exception as e:
        logging.error(f"Xatolik (handle_find_music): {e}", exc_info=True)
        bot.send_message(chat_id, get_text(chat_id, 'error_general', {'error': str(e)}))
        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except:
            pass

@bot.message_handler(content_types=['voice'])
def handle_voice(msg):
    chat_id = msg.chat.id
    
    if not check_rate_limit(chat_id):
        return

    try:
        # Create temp files context
        with TempFileManager() as temp_files:
            bot.send_message(chat_id, get_text(chat_id, 'voice_listening'))
            
            # 1. Download voice file
            file_info = bot.get_file(msg.voice.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            unique_id = str(uuid.uuid4())
            ogg_filename = f"voice_{unique_id}.ogg"
            temp_files.add_file(ogg_filename)
            
            with open(ogg_filename, 'wb') as new_file:
                new_file.write(downloaded_file)
                
            # 2. Try AudD Music Recognition FIRST
            music_info = recognize_music(ogg_filename)
            
            if music_info and music_info.get('track'):
                result = music_info['track']
                artist = result.get('subtitle')
                title = result.get('title')
                album = None # Shazam result might not have album easily
                links = result.get('url')
                
                # Additional links
                spotify_link = None
                youtube_link = None
                
                if result.get('sections'):
                    for section in result['sections']:
                        if section.get('type') == 'VIDEO':
                            if section.get('youtubeurl'):
                                youtube_link = section['youtubeurl'].get('actions', [{}])[0].get('uri')
                
                # Construct response
                response_text = get_text(chat_id, 'music_recognized')
                response_text += get_text(chat_id, 'music_artist', {'artist': artist})
                response_text += get_text(chat_id, 'music_title', {'title': title})
                
                # Save for download
                search_query_formatted = f"{artist} - {title}"
                
                # Smart Callback Data
                dl_callback = ""
                if len(search_query_formatted.encode('utf-8')) < 60:
                     dl_callback = f"dl|{search_query_formatted}"
                else:
                     # Fallback to memory
                     dl_id = str(uuid.uuid4())[:8]
                     user_recognized_songs[dl_id] = search_query_formatted
                     dl_callback = f"dl_id|{dl_id}"
                
                kb = telebot.types.InlineKeyboardMarkup()
                # Add Telegram Download button FIRST
                kb.add(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_telegram_search'), callback_data=dl_callback))
                
                if spotify_link:
                    kb.add(telebot.types.InlineKeyboardButton("Spotify 💚", url=spotify_link))
                if youtube_link:
                    kb.add(telebot.types.InlineKeyboardButton("YouTube 📺", url=youtube_link))
                if links:
                     kb.add(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_more_links'), url=links))
                
                bot.send_message(chat_id, response_text, parse_mode="HTML", reply_markup=kb)
                
                # Cleanup handled by context manager on exit
                return

            # 3. Fallback: Speech to Text (Original Logic)
            wav_filename = f"voice_{unique_id}.wav"
            temp_files.add_file(wav_filename)
            
            # Convert OGG to WAV (pydub requires ffmpeg)
            try:
                audio = AudioSegment.from_ogg(ogg_filename)
                audio.export(wav_filename, format="wav")
            except Exception as e:
                bot.send_message(chat_id, get_text(chat_id, 'voice_convert_error'))
                print(f"Converter error: {e}")
                return

            # Recognize Speech
            r = sr.Recognizer()
            with sr.AudioFile(wav_filename) as source:
                audio_data = r.record(source)
                try:
                    # Try Uzbek first, maybe fallback to Russian/English if needed
                    text = r.recognize_google(audio_data, language='uz-UZ')
                    safe_text = html.escape(text)
                    bot.send_message(chat_id, get_text(chat_id, 'voice_you_said', {'text': safe_text}))
                    
                    # Check for music search intent or just search
                    bot.send_message(chat_id, get_text(chat_id, 'search_music_searching', {'query': text}))
                    results = search_music(text, limit=30)
                    
                    if not results:
                        bot.send_message(chat_id, get_text(chat_id, 'nothing_found'))
                    else:
                        user_search_results[chat_id] = results
                        user_search_type[chat_id] = 'video'
                        send_search_page(chat_id, results, 0)
                        
                except sr.UnknownValueError:
                    bot.send_message(chat_id, get_text(chat_id, 'voice_error'))
                except sr.RequestError as e:
                    bot.send_message(chat_id, get_text(chat_id, 'voice_google_error', {'error': e}))

    except Exception as e:
        bot.send_message(chat_id, f"Xatolik: {e}")

@bot.message_handler(content_types=['audio', 'video', 'video_note'])
def handle_media_recognition(msg):
    chat_id = msg.chat.id
    
    status_msg = bot.send_message(chat_id, get_text(chat_id, 'recognition_processing'))
    
    try:
        file_id = None
        file_size = 0
        if msg.audio:
            file_id = msg.audio.file_id
            file_size = msg.audio.file_size
        elif msg.video:
            file_id = msg.video.file_id
            file_size = msg.video.file_size
        elif msg.video_note:
            file_id = msg.video_note.file_id
            file_size = msg.video_note.file_size
            
        if not file_id:
            bot.delete_message(chat_id, status_msg.message_id)
            return

        music_info = None
        
        # Telegram Bot API limit for download is 20MB (approx)
        if file_size and file_size < 20 * 1024 * 1024:
            # Use TempFileManager for cleanup
            with TempFileManager() as temp_files:
                file_info = bot.get_file(file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                
                unique_id = str(uuid.uuid4())
                
                # Determine extension text
                ext = 'tmp'
                is_video = False
                if msg.audio:
                    ext = 'mp3' 
                elif msg.video:
                    ext = 'mp4'
                    is_video = True
                elif msg.video_note:
                    ext = 'mp4'
                    is_video = True
                    
                input_filename = f"media_{unique_id}.{ext}"
                temp_files.add_file(input_filename)
                
                with open(input_filename, 'wb') as new_file:
                    new_file.write(downloaded_file)

                # Recognition Target File
                target_file = input_filename

                # Conversions if Video
                if is_video:
                    extracted_audio = f"extracted_{unique_id}.mp3"
                    temp_files.add_file(extracted_audio)
                    
                    try:
                        import subprocess
                        ffmpeg_path = shutil.which('ffmpeg')
                        if ffmpeg_path:
                            cmd = [
                                ffmpeg_path,
                                '-i', input_filename,
                                '-vn', # No video
                                '-acodec', 'libmp3lame', 
                                '-q:a', '4',
                                '-y', extracted_audio
                            ]
                            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                            if os.path.exists(extracted_audio):
                                target_file = extracted_audio
                            else:
                                logging.warning("Audio extraction failed, using original file.")
                        else:
                             logging.warning("FFmpeg not found for audio extraction.")
                    except Exception as e:
                        logging.error(f"Error extracting audio: {e}")

                # Recognize
                music_info = recognize_music(target_file)
                
                # Delete processing message
                try:
                     bot.delete_message(chat_id, status_msg.message_id)
                except:
                     pass
                
                if music_info and music_info.get('track'):
                    result = music_info['track']
                    artist = result.get('subtitle')
                    title = result.get('title')
                    links = result.get('url')
                    
                    # Additional links (Shazam)
                    spotify_link = None
                    # Shazam typically doesn't give direct Spotify links easily in the same structure, 
                    # but it gives a Shazam URL.
                    # We can check sections if available.
                    
                    youtube_link = None
                    if result.get('sections'):
                        for section in result['sections']:
                            if section.get('type') == 'VIDEO':
                                if section.get('youtubeurl'):
                                     youtube_link = section['youtubeurl'].get('actions', [{}])[0].get('uri')
                    
                    response_text = get_text(chat_id, 'music_recognized')
                    response_text += get_text(chat_id, 'music_artist', {'artist': artist})
                    response_text += get_text(chat_id, 'music_title', {'title': title})
                    
                    # Save for download
                    search_query_formatted = f"{artist} - {title}"
                    
                    # Smart Callback Data
                    dl_callback = ""
                    if len(search_query_formatted.encode('utf-8')) < 60:
                         dl_callback = f"dl|{search_query_formatted}"
                    else:
                         dl_id = str(uuid.uuid4())[:8]
                         user_recognized_songs[dl_id] = search_query_formatted
                         dl_callback = f"dl_id|{dl_id}"
                    
                    kb = telebot.types.InlineKeyboardMarkup()
                    kb.add(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_telegram_search'), callback_data=dl_callback))
                    
                    if spotify_link:
                        kb.add(telebot.types.InlineKeyboardButton("Spotify 💚", url=spotify_link))
                    if youtube_link:
                        kb.add(telebot.types.InlineKeyboardButton("YouTube 📺", url=youtube_link))
                    if links:
                         kb.add(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_more_links'), url=links))
                         
                    bot.send_message(chat_id, response_text, parse_mode="HTML", reply_markup=kb)
                else:
                    # Fallback to Filename/Metadata Search
                    search_query = None
                    
                    # 1. Try Metadata (Performer - Title) - Best Source
                    if msg.audio and (msg.audio.performer or msg.audio.title):
                         parts = []
                         if msg.audio.performer: parts.append(msg.audio.performer)
                         if msg.audio.title: parts.append(msg.audio.title)
                         if parts:
                             search_query = " - ".join(parts)

                    # 2. Try Caption
                    elif msg.caption:
                        clean_caption = msg.caption.split('\n')[0]
                        if len(clean_caption) < 80:
                            search_query = clean_caption

                    # 3. Try Filename (Last Resort)
                    elif msg.audio and msg.audio.file_name:
                         fn = msg.audio.file_name
                         if not fn.startswith("download") and not fn.startswith("audio_") and not "music.mp3" in fn:
                             search_query = fn
                    elif msg.video and hasattr(msg.video, 'file_name') and msg.video.file_name:
                         fn = msg.video.file_name
                         if not fn.startswith("download"):
                             search_query = fn

                    if search_query:
                        # Clean up query
                        search_query = os.path.splitext(search_query)[0]
                        search_query = search_query.replace('_', ' ').replace('-', ' ')
                        
                        garbage = [
                            'Universal Bot', 'www.', '.com', '@', 
                            'Official Video', 'Official Audio', 'Official Clip', 'Video Clip', 
                            'Official', 'Lyric Video', 'mv', 'M/V',
                            'Muzikalar', 'UzMuz', 'UzMir', 'Muzik', 'Music', 
                            'Premyera', 'New', 'Yangi', '2024', '2025', '2023',
                            'Мyзикалар', 'УзМуз', 'УзМир', 'Музик', 'Музыка', 'Премьера',
                            'skachat', 'yuklab olish'
                        ]
                        
                        search_query_lower = search_query.lower()
                        for g in garbage:
                             pattern = re.compile(re.escape(g), re.IGNORECASE)
                             search_query = pattern.sub('', search_query)
                        
                        search_query = " ".join(search_query.split())
                    
                    if search_query:
                         bot.send_message(chat_id, get_text(chat_id, 'music_fallback_search', {'query': search_query}))
                         results = search_music(search_query, limit=30)
                         
                         if not results and len(search_query.split()) > 3:
                              short_query = " ".join(search_query.split()[:3])
                              bot.send_message(chat_id, f"🔍 Kengaytirilgan qidiruv: {short_query}")
                              results = search_music(short_query, limit=30)

                         if results:
                            user_search_results[chat_id] = results
                            user_search_type[chat_id] = 'video'
                            send_search_page(chat_id, results, 0)
                         else:
                            bot.send_message(chat_id, get_text(chat_id, 'music_fallback_failed'))
                    else:
                         bot.send_message(chat_id, get_text(chat_id, 'music_not_found'))
        else:
             bot.send_message(chat_id, "⚠️ Fayl juda katta (20MB+), Telegram orqali yuklab bo'lmadi.")
             try:
                 bot.delete_message(chat_id, status_msg.message_id)
             except:
                 pass
            
    except Exception as e:
        bot.send_message(chat_id, f"Xatolik: {e}")
        try:
             bot.delete_message(chat_id, status_msg.message_id)
        except:
             pass

@bot.callback_query_handler(func=lambda call: call.data == "rec_dl" or call.data.startswith("dl|") or call.data.startswith("dl_id|"))
def handle_rec_download(call):
    chat_id = call.message.chat.id
    
    query = None
    if call.data == "rec_dl":
        # Handle legacy/fallback
        query = user_recognized_songs.get(chat_id)
    elif call.data.startswith("dl|"):
        try:
            query = call.data.split("|", 1)[1]
        except:
            pass
    elif call.data.startswith("dl_id|"):
        try:
            dl_id = call.data.split("|", 1)[1]
            query = user_recognized_songs.get(dl_id)
        except:
            pass
    
    if not query:
        bot.answer_callback_query(call.id, get_text(chat_id, 'error_link_expired'))
        return
        
    bot.answer_callback_query(call.id, get_text(chat_id, 'search_music_searching', {'query': query}))
    
    results = search_music(query, limit=30)
    
    if not results:
        bot.send_message(chat_id, get_text(chat_id, 'nothing_found'))
        return

    # Store results for this user
    user_search_results[chat_id] = results
    user_search_type[chat_id] = 'video'
    send_search_page(chat_id, results, 0)



import asyncio
from shazamio import Shazam

async def recognize_music_async(file_path):
    try:
        shazam = Shazam()
        out = await shazam.recognize(file_path)
        return out
    except Exception as e:
        logging.error(f"ShazamIO Error: {e}")
        return None

def recognize_music(file_path):
    try:
        # Run async function in sync context
        # Check if an event loop is already running? 
        # Since telebot is sync, usually there is no loop, but let's be safe.
        try:
             loop = asyncio.get_event_loop()
             if loop.is_running():
                 # Should not happen in pure sync bot, but just in case
                 pass
        except:
             pass
             
        # Simple run
        return asyncio.run(recognize_music_async(file_path))
    except Exception as e:
        logging.exception(f"Music Recognition Error: {e}")
        return None

@bot.callback_query_handler(func=lambda call: call.data.startswith("effect_"))
def handle_audio_effect(call):
    chat_id = call.message.chat.id
    effect = call.data.split("_")[1]
    
    # Needs to reply to an audio message or have context
    # Usually the message above the buttons has the audio?
    # Or the user replies to the audio?
    # In our flow, we sent a separate message with buttons.
    # But usually, it's better if the buttons are attached to the audio.
    # However, if we attached to audio, `call.message.audio` would be valid.
    # If we sent a separate message, we need to find the audio.
    
    # Assumption: The user clicked the button on the message.
    # If button was separate, we need link/file info.
    # Let's hope logic allows us to assume `user_links[chat_id]` is still valid or context is there.
    # But for a reliable "Edit this file" feature, we need the file_id.
    
    bot.answer_callback_query(call.id, get_text(chat_id, 'getting_info')) # reusing string
    
    try:
        # Use TempFileManager
        with TempFileManager() as temp_files:
            # We need the original file. 
            # If the buttons are attached to a text message "Select option" (as per code above), 
            # we don't have the audio directly in `call.message`.
            # Ideally, we should have attached buttons to the audio itself OR the logic relies on `user_links`.
            
            # Let's try downloading from `user_links[chat_id]` again? No, that's inefficient.
            # Better: Re-download? Or use file_id from history?
            # Simplest consistent way: Download from URL again (as we delete temp files).
            # OR: Check if `call.message.reply_to_message` has audio?
            
            url = user_links.get(chat_id)
            if not url:
                bot.send_message(chat_id, get_text(chat_id, 'error_link_expired'))
                return
    
            status_msg = bot.send_message(chat_id, "⏳ Audio qayta ishlanyapti...")
            
            # Download Original
            unique_id = str(uuid.uuid4())
            input_file = f"temp_{unique_id}.mp3"
            output_file = f"out_{unique_id}.mp3"
            
            # Register files for cleanup
            temp_files.add_file(input_file)
            temp_files.add_file(output_file)
            
            # Use yt-dlp to get fresh mp3
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'temp_{unique_id}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'quiet': True,
                'cookiefile': 'cookies.txt',  # Use cookies.txt
            }
            
            title = "Audio"
            artist = "Bot"
            duration = 0
            
            # Add Proxy if configured
            if Config.PROXY:
                ydl_opts['proxy'] = Config.PROXY

            # Robust Retry Logic (Similar to download_video)
            def download_with_opts(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=True)

            info = None
            last_error = None

            # Attempt 1: Configured Options (Proxy? + Cookies)
            opts1 = ydl_opts.copy()
            if Config.PROXY: opts1['proxy'] = Config.PROXY
            
            try:
                info = download_with_opts(opts1)
            except Exception as e:
                logging.warning(f"Audio Effect Download Attempt 1 failed: {e}")
                
                # Attempt 2: Proxy? + NO Cookies
                opts2 = opts1.copy()
                opts2.pop('cookiefile', None)
                try:
                    info = download_with_opts(opts2)
                except Exception as e2:
                    logging.warning(f"Audio Effect Download Attempt 2 failed: {e2}")

                    if Config.PROXY:
                            # Attempt 3: NO Proxy + Cookies
                            opts3 = ydl_opts.copy()
                            if 'proxy' in opts3: del opts3['proxy']
                            try:
                                info = download_with_opts(opts3)
                            except Exception as e3:
                                logging.warning(f"Audio Effect Download Attempt 3 failed: {e3}")
                                
                                # Attempt 4: NO Proxy + NO Cookies
                                opts4 = opts3.copy()
                                opts4.pop('cookiefile', None)
                                try:
                                    info = download_with_opts(opts4)
                                except Exception as e4:
                                    logging.warning(f"Audio Effect Download Attempt 4 failed: {e4}")
                                    raise e4 # Raise last error
                    else:
                        raise e2

            if not info:
                 raise Exception("Download failed after retries")
            title = info.get('title', 'Audio')
            artist = info.get('artist') or info.get('uploader') or "Bot"
            duration = info.get('duration', 0)
                
                # Find the file
            # Find the file
            if os.path.exists(f"temp_{unique_id}.mp3"):
                input_file = f"temp_{unique_id}.mp3"
            else:
                # Should not happen
                pass
    
            # Apply Effect
            audio = AudioSegment.from_mp3(input_file)
            
            if effect == '8d':
                # 8D Panning Logic
                # Split into chunks (e.g., 100ms) and pan them sine-wave style
                import math
                pan_amount = 0
                chunk_len = 200 # ms
                chunks = []
                
                # Add some reverb feel (overlay slightly delayed) before panning?
                # Simple reverb
                reverb = audio - 10 # lower volume
                audio = audio.overlay(reverb, position=50) # 50ms delay
                
                for i, chunk in enumerate(audio[::chunk_len]):
                    # Sine wave from -1.0 to 1.0
                    # Complete cycle every ~10 seconds?
                    cycle_len = 50 # chunks (50 * 200ms = 10s)
                    pan = math.sin(2 * math.pi * i / cycle_len)
                    chunks.append(chunk.pan(pan))
                
                processed = sum(chunks)
                title += " (8D Audio)"
                
            elif effect == 'slowed':
                # Slowed + Reverb
                # Slow down
                speed = 0.85
                # Manually change frame rate to pitch down
                new_rate = int(audio.frame_rate * speed)
                processed = audio._spawn(audio.raw_data, overrides={'frame_rate': new_rate})
                processed = processed.set_frame_rate(audio.frame_rate)
                
                # Add Reverb
                reverb = processed - 5
                processed = processed.overlay(reverb, position=100)
                
                title += " (Slowed & Reverb)"
                
            elif effect == 'concert':
                # Concert Hall (Reverb)
                # Multiple delays
                delay1 = audio - 5
                delay2 = audio - 10
                
                processed = audio.overlay(delay1, position=50).overlay(delay2, position=100)
                title += " (Concert Hall)"
            elif effect == 'bass':
                # Bass Boost
                # Low pass filter to isolate bass frequencies (below 150Hz)
                bass = audio.low_pass_filter(150)
                # Boost the bass (gain in dB) - e.g. +8dB
                bass = bass + 8
                # Overlay (mix) the boosted bass back onto the original track
                # reduce original slightly to prevent clipping?
                processed = audio.overlay(bass)
                title += " (Bass Boosted)"
            else:
                processed = audio
                
            # Export
            processed.export(output_file, format="mp3")
            
            # Send back
            with open(output_file, 'rb') as f:
                 bot.send_audio(
                    chat_id, 
                    f, 
                    title=title, 
                    performer=artist, 
                    duration=int(len(processed)/1000),
                    caption=f"🎧 Effect: {effect}"
                )
                
            bot.delete_message(chat_id, status_msg.message_id)
            
    except Exception as e:
        # Strip ANSI codes from error (Robust)
        error_message = str(e)
        ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
        error_message = ansi_escape.sub('', error_message)
        error_message = error_message.replace('[0;31m', '').replace('[0m', '').replace('[0;32m', '').replace('[0;33m', '').strip()

        if "Handshake status" in error_message or "EOF" in error_message or "Connection reset" in error_message or "timed out" in error_message.lower():
             bot.send_message(chat_id, "⚠️ <b>Ulanish Xatoligi:</b>\nServer bilan ulanishda xatolik yuz berdi. \n(Proxy yoki Internet muammosi). Qayta urinib ko'ring.", parse_mode="HTML")
        elif "403" in error_message or "Forbidden" in error_message:
             bot.send_message(chat_id, "⚠️ <b>Ruxsat Xatoligi (403):</b>\nBot IP manzili bloklangan bo'lishi mumkin.", parse_mode="HTML")
        else:
             bot.send_message(chat_id, f"Xatolik: {error_message}")


def cleanup_temp_files():
    """Startup cleanup of temporary files."""
    print("[INFO] Vaqtinchalik fayllar tozalanmoqda...")
    count = 0
    try:
        for f in os.listdir('.'):
            if f.startswith(('download_', 'voice_', 'rec_', 'media_', 'temp_')):
                try:
                    os.remove(f)
                    count += 1
                except Exception as e:
                    print(f"Fayl o'chirishda xatolik {f}: {e}")
        print(f"✨ Tozalandi: {count} ta fayl.")
    except Exception as e:
        print(f"Tozalashda xatolik: {e}")

def periodic_cleanup():
    """Har 30 daqiqada eski fayllarni tozalash"""
    while True:
        time.sleep(1800)  # 30 daqiqa
        cleanup_temp_files()

if __name__ == "__main__":
    try:
        cleanup_temp_files() # Run cleanup at startup
        
        # Start periodic cleanup
        cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
        cleanup_thread.start()
        
        print("Bot ishga tushmoqda...")  
        set_bot_commands()
        print("Menyu buyruqlari o'rnatildi.")
        
        # Start Userbot
        # try:
        #      print("Userbot ishga tushmoqda...")
        #      story_client.start()
        #      print("Userbot tayyor (yoki fon rejimida ishga tushirildi).")
        # except Exception as e:
        #      print(f"Userbot xatoligi: {e}")

    except Exception as e:
        logging.critical(f"Buyruqlarni o'rnatishda xatolik: {e}", exc_info=True)
    
    bot.infinity_polling()
