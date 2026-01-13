import logging
import telebot

# Configure logging
logging.basicConfig(
    filename='bot_debug.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

import yt_dlp
import os
import uuid
from urllib.parse import urlparse

import json
import speech_recognition as sr
from pydub import AudioSegment

TOKEN = "8248201167:AAET_I2UDloBjfbiJYbyPZIoMJ9EWbZ9VPg"
bot = telebot.TeleBot(TOKEN)

FAVORITES_FILE = "favorites.json"
LANGUAGES_FILE = "user_languages.json"

TEXTS = {
    'uz': {
        'start_welcome': "Assalomu aleykum Universal Media Bot ga\nxush kelibsiz\n@universal_media_uz_bot orqali quyidagilarni yuklab\nolishingiz mumkin\n\n●Instagram - post, stories, reels;\n●YouTube - video, shorts, audio;\n●Tik Tok - suv belgisiz video;\n●Facebook - reels\n●Pinterest-rasm, video\n●Snapchat-rasm, video\n●Likee - rasm, video\n●Threads -rasm, video\n●Bigo Live - video, efir\nMedia yuklashni boshlash uchun\nuning havolasini yuboring.",
        'search_searching': "🔥 '{query}' bo'yicha top musiqalar qidirilmoqda...",
        'search_top_loading': "🔥 Top o'zbek musiqalari qidirilmoqda...",
        'search_not_found': "Hozircha top musiqalar topilmadi.",
        'getting_info': "⏳ Ma'lumot olinmoqda...",
        'search_music_searching': "🔎 Muzika qidirilmoqda: {query}...",
        'nothing_found': "Hech narsa topilmadi 😔",
        'no_favorites': "❤️ Sizda hozircha saqlangan musiqalar yo'q.",
        'favorites_header': "❤️ <b>Sevimli Musiqalar:</b>\n\n",
        'saved': "❤️ Saqlandi!",
        'already_saved': "Allaqachon mavjud!",
        'saved_msg': "✅ Saqlandi: {title}",
        'error_no_link': "Saqlash uchun havola topilmadi.",
        'error_general': "Xatolik: {error}",
        'choose_quality': "❤️ Tanlandi: {title}\n\nSifatni tanlang:",
        'lang_choose': "💬 O'zgartirmoqchi bo'lgan tilni tanlang va siz tanlagan tilda bot ishlashni boshlaydi.\n\n(Interfeys tilini tanlash uchun, pastdagi tugmalardan birini bosishingiz mumkin)",
        'lang_selected': "✅ Til o'zgartirildi: O'zbekcha 🇺🇿",
        'downloading': "Yuklanmoqda... 0%",
        'downloading_percent': "Yuklanmoqda... {percent} ⏳",
        'finished_uploading': "Yuklab bo'lindi. Jonatilmoqda... 🚀",
        'video_caption': "🎵 <b>{title}</b>\n\nYuklab olish formatlari ↓",
        'video_only_caption': "🎵 <b>{title}</b>",
        'btn_video': "🎬 Video",
        'btn_audio': "🎧 MP3",
        'btn_save': "💾 Saqlash",
        'btn_download_song': "📥 Qo'shiqni yuklab olish",
        'btn_add_group': "➕ Guruhga qo'shish ⤴️",
        'btn_close': "❌ Yopish",
        'btn_back': "🔙 Orqaga",
        'voice_listening': "🎤 Ovozli xabar eshitilmoqda...",
        'voice_you_said': "🗣 Siz dedingiz: {text}",
        'voice_error': "🤷‍♂️ Uzr, nima deganingizni tushunmadim.",
        'file_too_large': "⚠️ Fayl hajmi juda katta ({size} MB). Telegram limiti 50 MB.\nIltimos, pastroq sifatni tanlang yoki boshqa havola yuboring.",
        'video_quality_select': "🎬 Video sifatini tanlang:", 
        'results_title': "🔎 Natijalar ({page}/{total}):\n\n",
        'download_error': "Yuklanmadi 😢",
        'search_results_expired': "Qidiruv natijalari eskirgan.",
        'error_item_not_found': "Xatolik: Element topilmadi",
        'error_link_expired': "Xatolik yuz berdi. Iltimos, qaytadan link yuboring.",
        'voice_convert_error': "⚠️ Ovoz formatini o'zgartirishda xatolik.\nFFmpeg o'rnatilganligini tekshiring.",
        'voice_google_error': "⚠️ Google Speech xizmatida xatolik: {error}",
        'menu_tg_anon': "Telegramda yashirincha 👀",
        'menu_insta_anon': "Instagramda yashirincha 👀",
        'feature_soon': "🛠 Bu funksiya tez orada ishga tushadi!",
        'insta_anon_instruction': "Instagram story havolasini yuboring.",
        'tg_anon_instruction': "Kimning telegramdagi hikoyasini yashirincha ko'rmoqchisiz?\nFoydalanuvchi nomi yoki kontaktini yuboring.",
        'btn_video_manual': "Video qo'llanma 🏷",
        'story_menu_today': "👀 Bugungi hikoyalarni ko'rish",
        'story_menu_old': "👀 Eski hikoyalarni ko'rish",
        'btn_8d': "🎧 8D",
        'btn_concert': "🏟 Concert Hall",
        'btn_slowed': "🐢 Slowed",
        'select_effect': "Iltimos, o'zingizga kerakli variantni tanlang 👇"
    },
    'uz_cyrl': {
        'start_welcome': "Ассалому алейкум Universal Media Bot га\nхуш келибсиз\n@universal_media_uz_bot орқали қуйидагиларни юклаб\nолишингиз мумкин\n\n●Instagram - post, stories, reels;\n●YouTube - video, shorts, audio;\n●Tik Tok - сув белгисиз видео;\n●Facebook - reels\n●Pinterest-расм, видео\n●Snapchat-расм, видео\n●Likee - расм, видео\n●Threads -расм, видео\n●Bigo Live - видео, эфир\nМедиа юклашни бошлаш учун\nунинг ҳаволасини юборинг.",
        'search_searching': "🔥 '{query}' бўйича топ мусиқалар қидирилмоқда...",
        'search_top_loading': "🔥 Топ ўзбек мусиқалари қидирилмоқда...",
        'search_not_found': "Ҳозирча топ мусиқалар топилмади.",
        'getting_info': "⏳ Маълумот олинмоқда...",
        'search_music_searching': "🔎 Музика қидирилмоқда: {query}...",
        'nothing_found': "Ҳеч нарса топилмади 😔",
        'no_favorites': "❤️ Сизда ҳозирча сақланган мусиқалар йўқ.",
        'favorites_header': "❤️ <b>Севимли Мусиқалар:</b>\n\n",
        'saved': "❤️ Сақланди!",
        'already_saved': "Аллақачон мавжуд!",
        'saved_msg': "✅ Сақланди: {title}",
        'error_no_link': "Сақлаш учун ҳавола топилмади.",
        'error_general': "Хатолик: {error}",
        'choose_quality': "❤️ Танланди: {title}\n\nСифатни танланг:",
        'lang_choose': "💬 Ўзгартирмоқчи бўлган тилни танланг ва сиз танлаган тилда бот ишлашни бошлайди.\n\n(Интерфейс тилини танлаш учун, пастдаги тугмалардан бирини босишингиз мумкин)",
        'lang_selected': "✅ Тил ўзгартирилди: Ўзбекча 🇺🇿",
        'downloading': "Юкланмоқда... 0%",
        'downloading_percent': "Юкланмоқда... {percent} ⏳",
        'finished_uploading': "Юклаб бўлинди. Жўнатилмоқда... 🚀",
        'video_caption': "🎵 <b>{title}</b>\n\nЮклаб олиш форматлари ↓",
        'video_only_caption': "🎵 <b>{title}</b>",
        'btn_video': "🎬 Видео",
        'btn_audio': "🎧 MP3",
        'btn_save': "💾 Сақлаш",
        'btn_download_song': "📥 Қўшиқни юклаб олиш",
        'btn_add_group': "➕ Гуруҳга қўшиш ⤴️",
        'btn_close': "❌ Ёпиш",
        'btn_back': "🔙 Орқага",
        'voice_listening': "🎤 Овозли хабар эшитилмоқда...",
        'voice_you_said': "🗣 Сиз дедингиз: {text}",
        'voice_error': "🤷‍♂️ Узр, нима деганингизни тушунмадим.",
        'file_too_large': "⚠️ Файл хажми жуда катта ({size} MB). Телеграм лимити 50 MB.\nИлтимос, пастроқ сифатни танланг ёки бошқа ҳавола юборинг.",
        'video_quality_select': "🎬 Видео сифатини танланг:",
        'results_title': "🔎 Натижалар ({page}/{total}):\n\n",
        'download_error': "Юкланмади 😢",
        'search_results_expired': "Қидирув натижалари эскирган.",
        'error_item_not_found': "Хатолик: Элемент топилмади",
        'error_link_expired': "Хатолик юз берди. Илтимос, қайтадан линк юборинг.",
        'voice_convert_error': "⚠️ Овоз форматини ўзгартиришда хатолик.\nFFmpeg ўрнатилганлигини текширинг.",
        'voice_google_error': "⚠️ Google Speech хизматида хатолик: {error}",
        'menu_tg_anon': "Телеграмда яширинча 👀",
        'menu_insta_anon': "Инстаграмда яширинча 👀",
        'feature_soon': "🛠 Бу функция тез орада ишга тушади!",
        'insta_anon_instruction': "Instagram story ҳаволасини юборинг.",
        'tg_anon_instruction': "Кимнинг телеграмдаги ҳикоясини яширинча кўрмоқчисиз?\nФойдаланувчи номи ёки контакдини юборинг.",
        'btn_video_manual': "Видео қўлланма 🏷",
        'story_menu_today': "👀 Бугунги ҳикояларни кўриш",
        'story_menu_old': "👀 Эски ҳикояларни кўриш",
        'btn_8d': "🎧 8D",
        'btn_concert': "🏟 Concert Hall",
        'btn_slowed': "🐢 Slowed",
        'select_effect': "Илтимос, ўзингизга керакли вариантни танланг 👇"
    },
    'ru': {
        'start_welcome': "Добро пожаловать в Universal Media Bot\n\nЧерез @universal_media_uz_bot вы можете скачать:\n\n●Instagram - посты, сторис, рилс;\n●YouTube - видео, шортс, аудио;\n●Tik Tok - видео без водяных знаков;\n●Facebook - рилс\n●Pinterest - фото, видео\n●Snapchat - фото, видео\n●Likee - фото, видео\n●Threads - фото, видео\n●Bigo Live - видео, эфир\nДля начала отправьте ссылку.",
        'search_searching': "🔥 Поиск топ музыки по '{query}'...",
        'search_top_loading': "🔥 Поиск топ узбекской музыки...",
        'search_not_found': "Топ музыка пока не найдена.",
        'getting_info': "⏳ Получение информации...",
        'search_music_searching': "🔎 Поиск музыки: {query}...",
        'nothing_found': "Ничего не найдено 😔",
        'no_favorites': "❤️ У вас пока нет сохраненной музыки.",
        'favorites_header': "❤️ <b>Избранная музыка:</b>\n\n",
        'saved': "❤️ Сохранено!",
        'already_saved': "Уже существует!",
        'saved_msg': "✅ Сохранено: {title}",
        'error_no_link': "Ссылка для сохранения не найдена.",
        'error_general': "Ошибка: {error}",
        'choose_quality': "❤️ Выбрано: {title}\n\nВыберите качество:",
        'lang_choose': "💬 Выберите язык, который хотите использовать, и бот начнет работать на выбранном вами языке.\n\n(Для выбора языка интерфейса нажмите одну из кнопок ниже)",
        'lang_selected': "✅ Язык изменен: Русский 🇷🇺",
        'downloading': "Загрузка... 0%",
        'downloading_percent': "Загрузка... {percent} ⏳",
        'finished_uploading': "Загружено. Отправка... 🚀",
        'video_caption': "🎵 <b>{title}</b>\n\nФорматы загрузки ↓",
        'video_only_caption': "🎵 <b>{title}</b>",
        'btn_video': "🎬 Видео",
        'btn_audio': "🎧 MP3",
        'btn_save': "💾 Сохранить",
        'btn_download_song': "📥 Скачать песню",
        'btn_add_group': "➕ Добавить в группу ⤴️",
        'btn_close': "❌ Закрыть",
        'btn_back': "🔙 Назад",
        'voice_listening': "🎤 Слушаю голосовое сообщение...",
        'voice_you_said': "🗣 Вы сказали: {text}",
        'voice_error': "🤷‍♂️ Извините, я не понял, что вы сказали.",
        'file_too_large': "⚠️ Размер файла слишком большой ({size} MB). Лимит Telegram 50 MB.\nПожалуйста, выберите качество ниже или отправьте другую ссылку.",
        'video_quality_select': "🎬 Выберите качество видео:",
        'results_title': "🔎 Результаты ({page}/{total}):\n\n",
        'download_error': "Не загружено 😢",
        'search_results_expired': "Результаты поиска устарели.",
        'error_item_not_found': "Ошибка: Элемент не найден",
        'error_link_expired': "Произошла ошибка. Пожалуйста, отправьте ссылку еще раз.",
        'voice_convert_error': "⚠️ Ошибка конвертации аудио.\nПроверьте установку FFmpeg.",
        'voice_google_error': "⚠️ Ошибка Google Speech: {error}",
        'menu_tg_anon': "Анонимно в Telegram 👀",
        'menu_insta_anon': "Анонимно в Instagram 👀",
        'feature_soon': "🛠 Эта функция скоро станет доступна!",
        'insta_anon_instruction': "Отправьте ссылку на Instagram story.",
        'tg_anon_instruction': "Чьи истории в Telegram вы хотите просмотреть тайно?\nОтправьте имя пользователя или контакт.",
        'btn_video_manual': "Видео инструкция 🏷",
        'story_menu_today': "👀 Посмотреть истории за сегодня",
        'story_menu_old': "👀 Посмотреть старые истории",
        'btn_8d': "🎧 8D",
        'btn_concert': "🏟 Concert Hall",
        'btn_slowed': "🐢 Slowed",
        'select_effect': "Пожалуйста, выберите нужный вариант 👇"
    },
    'en': {
        'start_welcome': "Welcome to Universal Media Bot\n\nYou can download from:\n\n●Instagram - posts, stories, reels;\n●YouTube - videos, shorts, audio;\n●Tik Tok - no watermark;\n●Facebook - reels\n●Pinterest - photos, videos\n●Snapchat - photos, videos\n●Likee - photos, videos\n●Threads - photos, videos\n●Bigo Live - videos, lives\nSend a link to start downloading.",
        'search_searching': "🔥 Searching top music for '{query}'...",
        'search_top_loading': "🔥 Searching top Uzbek music hits...",
        'search_not_found': "No top music found yet.",
        'getting_info': "⏳ Fetching info...",
        'search_music_searching': "🔎 Searching music: {query}...",
        'nothing_found': "Nothing found 😔",
        'no_favorites': "❤️ You don't have any saved music yet.",
        'favorites_header': "❤️ <b>Favorite Music:</b>\n\n",
        'saved': "❤️ Saved!",
        'already_saved': "Already exists!",
        'saved_msg': "✅ Saved: {title}",
        'error_no_link': "No link found to save.",
        'error_general': "Error: {error}",
        'choose_quality': "❤️ Selected: {title}\n\nChoose quality:",
        'lang_choose': "💬 Select the language you want to change, and the bot will start working in the language you selected.\n\n(To select the interface language, you can click one of the buttons below)",
        'lang_selected': "✅ Language changed: English 🇺🇸",
        'downloading': "Downloading... 0%",
        'downloading_percent': "Downloading... {percent} ⏳",
        'finished_uploading': "Downloaded. Sending... 🚀",
        'video_caption': "🎵 <b>{title}</b>\n\nDownload formats ↓",
        'video_only_caption': "🎵 <b>{title}</b>",
        'btn_video': "🎬 Video",
        'btn_audio': "🎧 MP3",
        'btn_save': "💾 Save",
        'btn_download_song': "📥 Download Song",
        'btn_add_group': "➕ Add to Group ⤴️",
        'btn_close': "❌ Close",
        'btn_back': "🔙 Back",
        'voice_listening': "🎤 Listening to voice message...",
        'voice_you_said': "🗣 You said: {text}",
        'voice_error': "🤷‍♂️ Sorry, I didn't understand that.",
        'file_too_large': "⚠️ File is too large ({size} MB). Telegram limit is 50 MB.\nPlease select lower quality or send another link.",
        'video_quality_select': "🎬 Select video quality:",
        'results_title': "🔎 Results ({page}/{total}):\n\n",
        'download_error': "Download failed 😢",
        'search_results_expired': "Search results expired.",
        'error_item_not_found': "Error: Item not found",
        'error_link_expired': "An error occurred. Please send the link again.",
        'voice_convert_error': "⚠️ Audio conversion error.\nCheck FFmpeg installation.",
        'voice_google_error': "⚠️ Google Speech error: {error}",
        'menu_tg_anon': "Secretly on Telegram 👀",
        'menu_insta_anon': "Secretly on Instagram 👀",
        'feature_soon': "🛠 This feature will be available soon!",
        'insta_anon_instruction': "Send the Instagram story link.",
        'tg_anon_instruction': "Whose Telegram stories do you want to view secretly?\nSend the username or contact.",
        'btn_video_manual': "Video tutorial 🏷",
        'story_menu_today': "👀 View today's stories",
        'story_menu_old': "👀 View old stories",
        'btn_8d': "🎧 8D",
        'btn_concert': "🏟 Concert Hall",
        'btn_slowed': "🐢 Slowed",
        'select_effect': "Please select the option you want 👇"
    }
}

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
# Store user states
user_states = {}

def load_user_favorites(chat_id):
    if not os.path.exists(FAVORITES_FILE):
        return []
    try:
        with open(FAVORITES_FILE, 'r') as f:
            data = json.load(f)
            return data.get(str(chat_id), [])
    except:
        return []


def load_user_language(chat_id):
    if not os.path.exists(LANGUAGES_FILE):
        return 'uz'
    try:
        with open(LANGUAGES_FILE, 'r') as f:
            data = json.load(f)
            return data.get(str(chat_id), 'uz')
    except:
        return 'uz'

def save_user_language(chat_id, lang_code):
    data = {}
    if os.path.exists(LANGUAGES_FILE):
        try:
            with open(LANGUAGES_FILE, 'r') as f:
                data = json.load(f)
        except:
            pass
    
    data[str(chat_id)] = lang_code
    with open(LANGUAGES_FILE, 'w') as f:
        json.dump(data, f)

def get_text(chat_id, key, format_args=None):
    lang = load_user_language(chat_id)
    text = TEXTS.get(lang, TEXTS['uz']).get(key, TEXTS['uz'].get(key, ""))
    if format_args:
        return text.format(**format_args)
    return text

# In top_music handler
@bot.message_handler(commands=['top'])
def top_music(msg):
    chat_id = msg.chat.id
    
    # Check arguments
    parts = msg.text.split(maxsplit=1)
    if len(parts) > 1:
        query = parts[1]
        bot.send_message(chat_id, get_text(chat_id, 'search_searching', {'query': query}))
    else:
        query = "top uzbek music hits 2025"
        bot.send_message(chat_id, get_text(chat_id, 'search_top_loading'))
    
    results = search_music(query, limit=30)
    
    if not results:
        bot.send_message(chat_id, get_text(chat_id, 'search_not_found'))
        return

    user_search_results[chat_id] = results
    user_search_type[chat_id] = 'music'
    send_search_page(chat_id, results, 0)

# In handle_message handler (Search)
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def handle_message(msg):
    chat_id = msg.chat.id
    text = msg.text.strip()
    
    # 0. Check User State
    state = user_states.get(chat_id)
    if state == 'awaiting_tg_username':
        # Clear state
        user_states[chat_id] = None
        
        # Assumption: User sent a username or contact
        # Here we should validate or process the username
        # For now, we mock the UI as requested
        
        # Mock Profile Photo (using a placeholder or request user's logic later)
        # Using a generic placeholder image
        profile_pic = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png" 
        
        kb = telebot.types.InlineKeyboardMarkup()
        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'story_menu_today'), callback_data="story_today"))
        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'story_menu_old'), callback_data="story_old"))
        
        # Send fake profile view
        bot.send_photo(
            chat_id, 
            profile_pic,
            caption=f"@{text}" if not text.startswith('@') else text, # Simple formatting
            reply_markup=kb
        )
        return

    # 1. Check if it's a URL
    is_url = False
    try:
        result = urlparse(text)
        if result.scheme and result.netloc:
            is_url = True
    except:
        pass

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
            "t.me", "telegram.me"
        ]
        
        is_simple_platform = any(platform in text for platform in simple_platforms)

        if is_simple_platform:
            # Try to get info first to show menu (Video/Audio)
            # If it fails, the try/except block below will catch it and fallback to download_video
            pass 

        # Unified URL handling (YouTube + others)
        bot.send_message(chat_id, get_text(chat_id, 'getting_info'))
        
        try:
            ydl_opts_info = {
                'quiet': True,
                'cookiefile': 'cookies.txt',  # Use cookies.txt
            }
            
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(text, download=False)
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
                
                # New UI: 2x2 Grid
                # Row 1: [Video] [Post by @user]
                # Row 2: [MP3] [Save]
                
                kb = telebot.types.InlineKeyboardMarkup()
                
                # Button Text
                if uploader and uploader != 'Unknown':
                    btn_text = f"Post by @{uploader}"
                else:
                    btn_text = "Post Link"

                # Row 1
                btn_post = telebot.types.InlineKeyboardButton(btn_text, url=text)
                btn_video = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_video'), callback_data="fmt_video")
                kb.row(btn_video, btn_post)
                
                # Row 2
                btn_mp3 = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_audio'), callback_data="mp3")
                btn_save = telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_save'), callback_data="save_fav")
                kb.row(btn_mp3, btn_save)
                
                caption = f"<b>{extractor}</b>\n@{uploader}\n{description}"
                
                if thumbnail:
                    bot.send_photo(chat_id, thumbnail, caption=caption, reply_markup=kb, parse_mode="HTML")
                else:
                    bot.send_message(chat_id, caption, reply_markup=kb, parse_mode="HTML")
                    
        except Exception as e:
            bot.send_message(chat_id, get_text(chat_id, 'error_general', {'error': str(e)}))
            # Fallback to simple download if extraction fails
            download_video(chat_id, text, "best")
        return

    # 3. If NOT a URL, treat as Search Query
    bot.send_message(chat_id, get_text(chat_id, 'search_music_searching', {'query': text}))
    
    results = search_music(text, limit=30)
    
    if not results:
        bot.send_message(chat_id, get_text(chat_id, 'nothing_found'))
        return

    # Store results for this user
    user_search_results[chat_id] = results
    user_search_type[chat_id] = 'video'
    send_search_page(chat_id, results, 0)


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
    bot.set_my_commands([
        telebot.types.BotCommand("start", "Qayta ishga tushirish"),
        telebot.types.BotCommand("top", "Ommabop qo'shiqlar"),
        telebot.types.BotCommand("my", "Sevimli musiqalar"),
        telebot.types.BotCommand("lang", "Tilni o'zgartirish")
    ])



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


@bot.message_handler(commands=['start'])
def start(msg):
    chat_id = msg.chat.id
    
    # ReplyKeyboardMarkup
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_tg = telebot.types.KeyboardButton(get_text(chat_id, 'menu_tg_anon'))
    btn_insta = telebot.types.KeyboardButton(get_text(chat_id, 'menu_insta_anon'))
    markup.add(btn_tg)
    markup.add(btn_insta)
    
    bot.send_message(chat_id, get_text(chat_id, 'start_welcome'), reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in [
    TEXTS['uz']['menu_tg_anon'], TEXTS['uz_cyrl']['menu_tg_anon'], 
    TEXTS['ru']['menu_tg_anon'], TEXTS['en']['menu_tg_anon'],
    TEXTS['uz']['menu_insta_anon'], TEXTS['uz_cyrl']['menu_insta_anon'], 
    TEXTS['ru']['menu_insta_anon'], TEXTS['en']['menu_insta_anon']
])
def handle_menu_buttons(msg):
    text = msg.text
    chat_id = msg.chat.id
    
    # Identify type based on text
    is_tg = False
    is_insta = False
    
    for lang in TEXTS:
        if text == TEXTS[lang].get('menu_tg_anon'):
            is_tg = True
            break
        if text == TEXTS[lang].get('menu_insta_anon'):
            is_insta = True
            break
            
    if is_tg:
        user_states[chat_id] = 'awaiting_tg_username'
        
        # Create Inline Keyboard for "Video qo'llanma"
        kb = telebot.types.InlineKeyboardMarkup()
        # Placeholder URL, user needs to provide real one
        kb.add(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_video_manual'), url="https://t.me/universal_media_uz_bot")) 
        
        bot.send_message(chat_id, get_text(chat_id, 'tg_anon_instruction'), reply_markup=kb)
    elif is_insta:
        bot.send_message(chat_id, get_text(chat_id, 'insta_anon_instruction'))
    else:
        bot.send_message(chat_id, get_text(chat_id, 'feature_soon'))

def search_music(query, limit=5):
    # 1. Try SoundCloud first (WITHOUT Cookies usually works better for public search)
    ydl_opts_sc = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'extract_flat': True,
        # 'cookiefile': 'cookies.txt',  # SoundCloud usually works better without generic cookies
    }

    results = []
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts_sc) as ydl:
            # scsearch
            info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
            results = info.get('entries', [])
    except Exception as e:
        logging.error(f"SoundCloud search error: {e}")
        print(f"SoundCloud search error: {e}")
    
    if results:
        return results
        
    # 2. If no results, fallback to YouTube (WITH Cookies if needed)
    print("SoundCloud returned 0 results, falling back to YouTube...")
    
    ydl_opts_yt = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'extract_flat': True,
        'cookiefile': 'cookies.txt',  # Use cookies for YouTube
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_yt) as ydl:
            # ytsearch
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            results = info.get('entries', [])
    except Exception as e:
        logging.error(f"YouTube search error: {e}")
        print(f"YouTube search error: {e}")
        
    return results



def send_search_page(chat_id, results, page):
    items_per_page = 5 # Reduced to fit caption limits better if needed, but 10 is fine usually
    total_items = len(results)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    
    current_items = results[start_idx:end_idx]
    
    # Metadata for header (take from first item)
    first_item = current_items[0] if current_items else {}
    title_full = first_item.get('title', 'Unknown Title')
    artist = "Unknown Artist"
    track_name = title_full
    
    if " - " in title_full:
        parts = title_full.split(" - ", 1)
        artist = parts[0]
        track_name = parts[1]
    
    header = f"Ijrochi: <b>{artist}</b>\nQo'shiq nomi: <b>{track_name}</b>\n\n"
    
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
    
    # Add page info
    response_text += f"\n{page + 1}/{total_pages}"

    # Decoration buttons (Lyrics, Video)
    kb.row(
        telebot.types.InlineKeyboardButton("🗒 Qo'shiq so'zlari", callback_data="lyrics_placeholder"),
        telebot.types.InlineKeyboardButton("📹 Video", callback_data=f"select_{start_idx}") # Default to first video or placeholder
    )
    
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
    items_per_page = 5 # Match send_search_page
    total_items = len(results)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    
    # Limit check
    if new_page >= total_pages:
        return

    start_idx = new_page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    current_items = results[start_idx:end_idx]
    
    first_item = current_items[0] if current_items else {}
    title_full = first_item.get('title', 'Unknown Title')
    artist = "Unknown Artist"
    track_name = title_full
    
    if " - " in title_full:
        parts = title_full.split(" - ", 1)
        artist = parts[0]
        track_name = parts[1]
    
    header = f"Ijrochi: <b>{artist}</b>\nQo'shiq nomi: <b>{track_name}</b>\n\n"
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
    
    # Decoration buttons (Lyrics, Video)
    kb.row(
        telebot.types.InlineKeyboardButton("🗒 Qo'shiq so'zlari", callback_data="lyrics_placeholder"),
        telebot.types.InlineKeyboardButton("📹 Video", callback_data=f"select_{start_idx}")
    )
    
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

def download_video(chat_id, url, quality):
    status_msg = bot.send_message(chat_id, get_text(chat_id, 'downloading'))
    last_update_time = 0
    
    # Progress hook function
    def progress_hook(d):
        nonlocal last_update_time
        import time
        
        if d['status'] == 'downloading':
            current_time = time.time()
            # Update only every 3 seconds to avoid rate limits
            if current_time - last_update_time > 3:
                percent = d.get('_percent_str', 'N/A')
                try:
                    bot.edit_message_text(get_text(chat_id, 'downloading_percent', {'percent': percent}), chat_id, status_msg.message_id)
                    last_update_time = current_time
                except:
                    pass
        elif d['status'] == 'finished':
            try:
                bot.edit_message_text(get_text(chat_id, 'finished_uploading'), chat_id, status_msg.message_id)
            except:
                pass

    # Generate unique ID for this download to avoid collisions
    unique_id = str(uuid.uuid4())
    temp_filename_base = f"download_{unique_id}"
    
    final_filename = None

    try:
        common_opts = {
            'quiet': True,
            'progress_hooks': [progress_hook],
            'cookiefile': 'cookies.txt',  # Use cookies.txt
        }

        if quality == "mp3":
            ydl_opts = {
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
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_filename = f"{temp_filename_base}.mp3"
                
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
                        break
                
                if os.path.exists(final_filename):
                    with open(final_filename, 'rb') as audio_file:
                        caption_text = get_text(chat_id, 'video_caption', {'title': title})
                        
                        # Effects Keyboard
                        kb = telebot.types.InlineKeyboardMarkup()
                        kb.row(
                            telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_8d'), callback_data="effect_8d"),
                            telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_concert'), callback_data="effect_concert")
                        )
                        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_slowed'), callback_data="effect_slowed"))
                        
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
                                    reply_markup=kb
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
                                reply_markup=kb
                            )
                        
                        # Send the "Please select..." message separately or as reply_markup?
                        # User screenshot shows a separate message or caption updates.
                        # Usually user expects the controls on the file.
                        bot.send_message(chat_id, get_text(chat_id, 'select_effect'), reply_markup=kb)
                            
                    bot.delete_message(chat_id, status_msg.message_id)
                else:
                    bot.edit_message_text(get_text(chat_id, 'download_error'), chat_id, status_msg.message_id)
        
        else:
            if quality == "best":
                format_str = 'bv+ba/b'
            else:
                format_str = f'bv*[height<={quality}]+ba/b'

            ydl_opts = {
                **common_opts,
                'format': format_str,
                'outtmpl': f'{temp_filename_base}.%(ext)s',
                'writethumbnail': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                ext = info.get('ext', 'mp4')
                final_filename = f"{temp_filename_base}.{ext}"
                
                # Metadata extraction
                width = info.get('width')
                height = info.get('height')
                duration = info.get('duration')
                title = info.get('title', 'Video')
                
                # Find thumbnail
                thumb_path = None
                possible_exts = ['jpg', 'jpeg', 'png', 'webp']
                for e in possible_exts:
                    if os.path.exists(f"{temp_filename_base}.{e}"):
                        thumb_path = f"{temp_filename_base}.{e}"
                        break
                
                if not os.path.exists(final_filename):
                    for f in os.listdir('.'):
                        if f.startswith(temp_filename_base) and not f == thumb_path:
                            final_filename = f
                            break


                if final_filename and os.path.exists(final_filename):
                    # Check file size (50MB limit = 50 * 1024 * 1024 bytes)
                    file_size = os.path.getsize(final_filename)
                    if file_size > 50 * 1024 * 1024:
                        size_mb = round(file_size / (1024 * 1024), 2)
                        bot.send_message(chat_id, get_text(chat_id, 'file_too_large', {'size': size_mb}))
                        bot.delete_message(chat_id, status_msg.message_id)
                        return # Skip sending

                    with open(final_filename, 'rb') as video_file:
                        # Action Buttons matching screenshot
                        kb = telebot.types.InlineKeyboardMarkup()
                        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_save'), callback_data="save_fav"))
                        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_download_song'), callback_data="mp3"))
                        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url="https://t.me/universal_media_uz_bot?startgroup=on"))

                        if thumb_path:
                            with open(thumb_path, 'rb') as thumb_file:
                                bot.send_video(
                                    chat_id, 
                                    video_file, 
                                    caption=get_text(chat_id, 'video_caption', {'title': title}),
                                    parse_mode="HTML",
                                    width=width, 
                                    height=height, 
                                    duration=duration, 
                                    thumbnail=thumb_file,
                                    supports_streaming=True,
                                    reply_markup=kb
                                )
                        else:
                            bot.send_video(
                                chat_id, 
                                video_file, 
                                caption=get_text(chat_id, 'video_caption', {'title': title}),
                                parse_mode="HTML",
                                width=width, 
                                height=height, 
                                duration=duration,
                                supports_streaming=True,
                                reply_markup=kb
                            )
                            
                    bot.delete_message(chat_id, status_msg.message_id)
                else:
                    bot.edit_message_text(get_text(chat_id, 'download_error'), chat_id, status_msg.message_id)
    
    except Exception as e:
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        error_message = ansi_escape.sub('', str(e))
        try:
            bot.edit_message_text(get_text(chat_id, 'error_general', {'error': error_message}), chat_id, status_msg.message_id)
        except:
            bot.send_message(chat_id, get_text(chat_id, 'error_general', {'error': error_message}))
    
    finally:
        try:
            for f in os.listdir('.'):
                if f.startswith(temp_filename_base):
                    try:
                        os.remove(f)
                    except:
                        pass
        except Exception:
            pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_"))
def handle_search_selection(call):
    chat_id = call.message.chat.id
    try:
        selection_index = int(call.data.split("_")[1])
        results = user_search_results.get(chat_id)
        
        if not results or selection_index >= len(results):
            bot.answer_callback_query(call.id, get_text(chat_id, 'search_results_expired'))
            return

        selected_video = results[selection_index]
        video_url = selected_video.get('url') or selected_video.get('webpage_url')
        title = selected_video.get('title', 'Video')
        thumbnail = selected_video.get('thumbnail', '')
        
        # Save state
        user_links[chat_id] = video_url
        user_current_titles[chat_id] = title
        
        # Main simplified menu for Music
        kb = telebot.types.InlineKeyboardMarkup()
        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_save'), callback_data="save_fav"))
        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_download_song'), callback_data="mp3"))
        kb.row(telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_add_group'), url="https://t.me/universal_media_uz_bot?startgroup=on"))
        
        # Send Photo if available, otherwise Message
        # SoundCloud usually provides a thumbnail
        if thumbnail:
            bot.send_photo(chat_id, thumbnail, caption=get_text(chat_id, 'video_caption', {'title': title}), reply_markup=kb, parse_mode="HTML")
        else:
            bot.send_message(chat_id, get_text(chat_id, 'video_only_caption', {'title': title}), reply_markup=kb, parse_mode="HTML")

    except Exception as e:
        bot.send_message(chat_id, f"Xatolik: {e}")

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
    
    kb = telebot.types.InlineKeyboardMarkup()
    kb.row(
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_video'), callback_data="fmt_video"),
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_audio'), callback_data="mp3")
    )
    kb.row(
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_save'), callback_data="save_fav"),
        telebot.types.InlineKeyboardButton(get_text(chat_id, 'btn_close'), callback_data="page_close")
    )
    
    try:
        # Restore caption
        if call.message.content_type == 'photo':
             bot.edit_message_caption(get_text(chat_id, 'video_caption', {'title': title}), chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        else:
             bot.edit_message_text(get_text(chat_id, 'video_only_caption', {'title': title}), chat_id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        print(f"Error editing message: {e}")

@bot.callback_query_handler(func=lambda call: True)
def download(call):
    chat_id = call.message.chat.id
    url = user_links.get(chat_id)
    quality = call.data
    
    if not url:
        bot.send_message(chat_id, get_text(chat_id, 'error_link_expired'))
        return

    # Call the helper function
    download_video(chat_id, url, quality)

@bot.message_handler(content_types=['voice'])
def handle_voice(msg):
    chat_id = msg.chat.id
    try:
        bot.send_message(chat_id, get_text(chat_id, 'voice_listening'))
        
        # 1. Download voice file
        file_info = bot.get_file(msg.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Create temp files
        unique_id = str(uuid.uuid4())
        ogg_filename = f"voice_{unique_id}.ogg"
        wav_filename = f"voice_{unique_id}.wav"
        
        with open(ogg_filename, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        # 2. Convert OGG to WAV (pydub requires ffmpeg)
        try:
            audio = AudioSegment.from_ogg(ogg_filename)
            audio.export(wav_filename, format="wav")
        except Exception as e:
            bot.send_message(chat_id, get_text(chat_id, 'voice_convert_error'))
            print(f"Converter error: {e}")
            return

        # 3. Recognize Speech
        r = sr.Recognizer()
        with sr.AudioFile(wav_filename) as source:
            audio_data = r.record(source)
            try:
                # Try Uzbek first, maybe fallback to Russian/English if needed
                text = r.recognize_google(audio_data, language='uz-UZ')
                bot.send_message(chat_id, get_text(chat_id, 'voice_you_said', {'text': text}))
                
                # 4. Search logic (duplicate of handle_message part)
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
        
    finally:
        # Cleanup
        if os.path.exists(ogg_filename):
            os.remove(ogg_filename)
        if os.path.exists(wav_filename):
            os.remove(wav_filename)

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
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Audio')
            artist = info.get('artist') or info.get('uploader') or "Bot"
            duration = info.get('duration', 0)
            
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
        bot.send_message(chat_id, f"Xatolik: {e}")
        
    finally:
        # Cleanup
        try:
             import glob
             for f in glob.glob(f"*{unique_id}*"):
                 os.remove(f)
        except:
             pass

if __name__ == "__main__":
    try:
        print("Bot ishga tushmoqda...")
        set_bot_commands()
        print("Menyu buyruqlari o'rnatildi.")
    except Exception as e:
        print(f"Buyruqlarni o'rnatishda xatolik: {e}")
    
    bot.infinity_polling()
