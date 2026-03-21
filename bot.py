import asyncio
import json
import os
import shutil
import subprocess
import threading
import time
from html import escape

import edge_tts
import requests
import telebot
from deep_translator import GoogleTranslator

TOKEN = "6217567864:AAE8-p94iEXRb6xItQsykxrpW5M_XaUsqec"
DEFAULT_VOICE_KEY = "male"
VOICE_OPTIONS = {
    "male": {
        "voice": "uz-UZ-SardorNeural",
        "title": "1. Erkak ovoz",
        "short": "Erkak",
    },
    "female": {
        "voice": "uz-UZ-MadinaNeural",
        "title": "2. Ayol ovoz",
        "short": "Ayol",
    },
    "female_alt": {
        "voice": "en-US-AvaMultilingualNeural",
        "title": "3. Ayol ovoz",
        "short": "Ayol 2",
    },
}
NETWORK_RETRIES = 3
PROCESSING_TEXT = "Kuting, matn tarjima qilinib ovoz tayyorlanmoqda... ⏳"
OCR_PROCESSING_TEXT = "Kuting, rasm ichidagi matn olinmoqda va ovoz tayyorlanmoqda... ⏳"
ERROR_TEXT = "O'zbekcha ovoz xizmati vaqtincha ishlamayapti. Iltimos, birozdan keyin qayta urinib ko'ring."
OCR_ERROR_TEXT = "Rasm ichidagi matnni olib bo'lmadi. Iltimos, boshqa rasm yuborib ko'ring."
OCR_NO_TEXT_TEXT = "Rasm ichidan matn topilmadi."
IMAGE_ONLY_TEXT = "Faqat rasm yuboring. Oddiy fayl emas, surat kerak."
OCR_API_URL = "https://api.ocr.space/parse/image"
OCR_API_KEY = os.getenv("OCR_SPACE_API_KEY", "helloworld")
MAX_MESSAGE_LENGTH = 4000
MAX_CAPTION_LENGTH = 1024
SETTINGS_FILE = "user_settings.json"
TEMP_FILE_PREFIXES = ("voice_", "ocr_")
TEMP_FILE_EXTENSIONS = {".mp3", ".ogg", ".jpg", ".jpeg", ".png", ".webp"}
TEMP_FILE_MAX_AGE_SECONDS = 3600
TEMP_CLEANUP_INTERVAL_SECONDS = 3600

bot = telebot.TeleBot(TOKEN)


def configure_bot_commands():
    bot.delete_my_commands()
    bot.set_my_commands([
        telebot.types.BotCommand("start", "Botni ishga tushirish"),
    ])


def load_user_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
            payload = json.load(settings_file)
            return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_user_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, ensure_ascii=False, indent=2)


def get_user_voice_key(user_id):
    settings = load_user_settings()
    voice_key = settings.get(str(user_id), {}).get("voice", DEFAULT_VOICE_KEY)
    return voice_key if voice_key in VOICE_OPTIONS else DEFAULT_VOICE_KEY


def get_user_voice(user_id):
    return VOICE_OPTIONS[get_user_voice_key(user_id)]["voice"]


def get_user_voice_title(user_id):
    return VOICE_OPTIONS[get_user_voice_key(user_id)]["title"]


def set_user_voice(user_id, voice_key):
    if voice_key not in VOICE_OPTIONS:
        return

    settings = load_user_settings()
    user_key = str(user_id)
    settings[user_key] = {"voice": voice_key}
    save_user_settings(settings)


def build_voice_keyboard():
    markup = telebot.types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        telebot.types.InlineKeyboardButton("1. Erkak", callback_data="voice:male"),
        telebot.types.InlineKeyboardButton("2. Ayol", callback_data="voice:female"),
        telebot.types.InlineKeyboardButton("3. Ayol", callback_data="voice:female_alt"),
    )
    return markup


def build_welcome_text(user_name, voice_title):
    safe_name = escape(user_name or "do'stim")
    safe_voice_title = escape(voice_title)
    return (
        f"<i>Assalomu alaykum, 🕊༺ {safe_name} ༻🕊</i>\n\n"
        f"<i>Ovoz tanlovi: {safe_voice_title}</i>\n\n"
        "<i>Menga matn yoki rasm yuboring</i>\n\n"
        "<i>Matnni o'qib beraman, rasm ichidan yozuvni ajratib beraman 🤫</i>"
    )


async def save_edge_tts(text, voice_name, file_name):
    communicate = edge_tts.Communicate(text=text, voice=voice_name)
    await communicate.save(file_name)


def retry_call(action_name, func, *args, **kwargs):
    last_error = None
    for attempt in range(1, NETWORK_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            print(f"{action_name} xatoligi, urinish {attempt}/{NETWORK_RETRIES}: {exc}")
            if attempt == NETWORK_RETRIES:
                raise
            time.sleep(attempt)
    raise last_error


def save_audio(text, voice_name, file_name):
    def generate_audio():
        asyncio.run(save_edge_tts(text, voice_name, file_name))

    try:
        retry_call("edge_tts", generate_audio)
    except Exception:
        if os.path.exists(file_name):
            os.remove(file_name)
        raise


def get_ffmpeg_exe():
    ffmpeg_exe = shutil.which("ffmpeg")
    if ffmpeg_exe:
        return ffmpeg_exe

    windows_ffmpeg = r"C:\ffmpeg\bin\ffmpeg.exe"
    if os.path.exists(windows_ffmpeg):
        return windows_ffmpeg

    raise FileNotFoundError("ffmpeg topilmadi. Iltimos, ffmpeg o'rnatilganini tekshiring.")


def convert_to_voice(input_file, output_file):
    ffmpeg_exe = get_ffmpeg_exe()
    command = [
        ffmpeg_exe,
        "-y",
        "-i",
        input_file,
        "-vn",
        "-c:a",
        "libopus",
        "-b:a",
        "48k",
        "-ar",
        "48000",
        "-ac",
        "1",
        output_file,
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def split_text(text, max_length=MAX_MESSAGE_LENGTH):
    chunks = []
    remaining = text.strip()

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, max_length)
        if split_at == -1:
            split_at = max_length

        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    return chunks


def build_caption_chunks(text):
    prefix = "🇺🇿 Tarjima:\n\n"
    first_chunk_limit = MAX_CAPTION_LENGTH - len(prefix)
    chunks = split_text(text)

    if not chunks:
        return "", []

    first_text = chunks[0]
    extra_chunks = chunks[1:]

    if len(first_text) > first_chunk_limit:
        overflow = first_text[first_chunk_limit:].strip()
        first_text = first_text[:first_chunk_limit].rstrip()
        if overflow:
            extra_chunks = split_text(overflow) + extra_chunks

    return f"{prefix}{first_text}", extra_chunks


def download_telegram_file(file_id, destination):
    file_info = retry_call("get_file", bot.get_file, file_id)
    file_data = retry_call("download_file", bot.download_file, file_info.file_path)
    with open(destination, "wb") as output_file:
        output_file.write(file_data)


def extract_text_from_image(image_path):
    with open(image_path, "rb") as image_file:
        response = retry_call(
            "ocr_request",
            requests.post,
            OCR_API_URL,
            headers={"apikey": OCR_API_KEY},
            files={"file": (os.path.basename(image_path), image_file)},
            data={
                "language": "auto",
                "OCREngine": "2",
                "scale": "true",
                "detectOrientation": "true",
            },
            timeout=60,
        )

    response.raise_for_status()
    payload = response.json()

    if payload.get("IsErroredOnProcessing"):
        errors = payload.get("ErrorMessage") or ["OCR xizmati xato qaytardi."]
        raise RuntimeError(" ".join(errors))

    parsed_results = payload.get("ParsedResults") or []
    extracted_text = "\n".join(
        (item.get("ParsedText") or "").strip()
        for item in parsed_results
        if (item.get("ParsedText") or "").strip()
    ).strip()

    if not extracted_text:
        raise ValueError(OCR_NO_TEXT_TEXT)

    return extracted_text


def translate_to_uzbek(text):
    return GoogleTranslator(source="auto", target="uz").translate(text)


def cleanup_temp_files():
    removed_count = 0
    now = time.time()

    for file_name in os.listdir("."):
        if not os.path.isfile(file_name):
            continue
        if not file_name.startswith(TEMP_FILE_PREFIXES):
            continue
        if os.path.splitext(file_name)[1].lower() not in TEMP_FILE_EXTENSIONS:
            continue

        try:
            file_age = now - os.path.getmtime(file_name)
        except OSError:
            continue

        if file_age < TEMP_FILE_MAX_AGE_SECONDS:
            continue

        try:
            os.remove(file_name)
            removed_count += 1
        except OSError as cleanup_error:
            print(f"Temp faylni o'chirishda xatolik ({file_name}): {cleanup_error}")

    if removed_count:
        print(f"Tozalandi: {removed_count} ta temp fayl.")


def periodic_cleanup():
    while True:
        time.sleep(TEMP_CLEANUP_INTERVAL_SECONDS)
        cleanup_temp_files()


def send_translated_voice(chat_id, user_id, message_id, source_text):
    translated_text = translate_to_uzbek(source_text)
    caption_text, extra_chunks = build_caption_chunks(translated_text)
    send_voice_response(
        chat_id,
        user_id,
        message_id,
        translated_text,
        caption_text=caption_text,
        translate=False,
    )
    return extra_chunks


def send_voice_response(chat_id, user_id, message_id, source_text, caption_text=None, translate=True):
    temp_audio = f"voice_{chat_id}_{message_id}.mp3"
    voice_file = f"voice_{chat_id}_{message_id}.ogg"

    try:
        voice_text = translate_to_uzbek(source_text) if translate else source_text
        save_audio(voice_text, get_user_voice(user_id), temp_audio)
        convert_to_voice(temp_audio, voice_file)

        with open(voice_file, "rb") as voice:
            if caption_text:
                retry_call("send_voice", bot.send_voice, chat_id, voice, caption=caption_text)
            else:
                retry_call("send_voice", bot.send_voice, chat_id, voice)
    finally:
        for file_name in (temp_audio, voice_file):
            if os.path.exists(file_name):
                os.remove(file_name)


@bot.message_handler(commands=["start"])
def send_welcome(message):
    retry_call(
        "reply_to",
        bot.reply_to,
        message,
        build_welcome_text(message.from_user.first_name, get_user_voice_title(message.from_user.id)),
        parse_mode="HTML",
        reply_markup=build_voice_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("voice:"))
def handle_voice_selection(call):
    voice_key = call.data.split(":", 1)[1]
    if voice_key not in VOICE_OPTIONS:
        retry_call("answer_callback_query", bot.answer_callback_query, call.id, "Noma'lum ovoz.")
        return

    set_user_voice(call.from_user.id, voice_key)
    retry_call(
        "answer_callback_query",
        bot.answer_callback_query,
        call.id,
        f"Tanlandi: {VOICE_OPTIONS[voice_key]['short']}",
    )
    retry_call(
        "edit_message_text",
        bot.edit_message_text,
        build_welcome_text(call.from_user.first_name, VOICE_OPTIONS[voice_key]["title"]),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="HTML",
        reply_markup=build_voice_keyboard(),
    )


@bot.message_handler(content_types=["text"])
def text_to_speech(message):
    if not message.text:
        return

    waiting_message = None

    try:
        waiting_message = retry_call(
            "send_message",
            bot.send_message,
            message.chat.id,
            PROCESSING_TEXT,
        )
        extra_chunks = send_translated_voice(
            message.chat.id,
            message.from_user.id,
            message.message_id,
            message.text,
        )

        for chunk in extra_chunks:
            retry_call("send_message", bot.send_message, message.chat.id, chunk)

        if waiting_message:
            try:
                retry_call("delete_message", bot.delete_message, message.chat.id, waiting_message.message_id)
            except Exception as delete_error:
                print(f"delete_message xatoligi: {delete_error}")
    except Exception as exc:
        try:
            retry_call(
                "reply_to",
                bot.reply_to,
                message,
                f"{ERROR_TEXT}\nTexnik xatolik: {str(exc)}",
            )
        except Exception as reply_error:
            print(f"reply_to xatoligi: {reply_error}")


@bot.message_handler(content_types=["photo", "document"])
def image_to_text(message):
    if message.content_type == "document":
        mime_type = message.document.mime_type or ""
        if not mime_type.startswith("image/"):
            retry_call("reply_to", bot.reply_to, message, IMAGE_ONLY_TEXT)
            return
        file_id = message.document.file_id
        extension = os.path.splitext(message.document.file_name or "")[1] or ".jpg"
    else:
        file_id = message.photo[-1].file_id
        extension = ".jpg"

    image_file = f"ocr_{message.chat.id}_{message.message_id}{extension}"
    waiting_message = None

    try:
        waiting_message = retry_call(
            "send_message",
            bot.send_message,
            message.chat.id,
            OCR_PROCESSING_TEXT,
        )

        download_telegram_file(file_id, image_file)
        extracted_text = extract_text_from_image(image_file)
        extra_chunks = send_translated_voice(
            message.chat.id,
            message.from_user.id,
            message.message_id,
            extracted_text,
        )

        for chunk in extra_chunks:
            retry_call("send_message", bot.send_message, message.chat.id, chunk)

        if waiting_message:
            try:
                retry_call("delete_message", bot.delete_message, message.chat.id, waiting_message.message_id)
            except Exception as delete_error:
                print(f"delete_message xatoligi: {delete_error}")
    except ValueError as exc:
        retry_call("reply_to", bot.reply_to, message, str(exc))
    except Exception as exc:
        retry_call(
            "reply_to",
            bot.reply_to,
            message,
            f"{OCR_ERROR_TEXT}\nTexnik xatolik: {str(exc)}",
        )
    finally:
        if os.path.exists(image_file):
            os.remove(image_file)


if __name__ == "__main__":
    configure_bot_commands()
    cleanup_temp_files()
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()
    print("Bot ishga tushdi... Telegram orqali xabar yuborib tekshirib ko'ring!")
    bot.infinity_polling()
